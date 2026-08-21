import os
import shutil
import zipfile
import subprocess
import threading
import glob
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging

from tap.config.settings import get_base_dir, load_app_config, load_db_config

logger = logging.getLogger(__name__)

# Nombre maximal de sauvegardes à conserver
MAX_BACKUPS = 10

def _find_mysqldump() -> str | None:
    """Cherche l'exécutable mysqldump sur le système."""
    # 1. Vérifier dans le PATH
    path_mysqldump = shutil.which("mysqldump")
    if path_mysqldump:
        return path_mysqldump

    # 2. Chercher dans les emplacements communs sous Windows
    common_paths = [
        r"C:\xampp\mysql\bin\mysqldump.exe",
        r"C:\wamp64\bin\mysql\mysql*\bin\mysqldump.exe",
        r"C:\wamp\bin\mysql\mysql*\bin\mysqldump.exe",
        r"C:\Program Files\MySQL\MySQL Server *\bin\mysqldump.exe",
        r"C:\Program Files (x86)\MySQL\MySQL Server *\bin\mysqldump.exe"
    ]
    
    for pattern in common_paths:
        matches = glob.glob(pattern)
        if matches:
            return matches[0] # Prendre le premier trouvé
            
    return None


def _backup_directory() -> Path:
    """Retourne un dossier inscriptible, avec repli hors du profil protégé."""
    candidates = []
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        candidates.append(Path(local_app_data) / "TAP_Gestion_Loyers" / "Backups")
    candidates.extend([
        get_base_dir() / "backups",
        Path(os.environ.get("TEMP", ".")) / "TAP_Gestion_Loyers" / "Backups",
    ])
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.write_text("ok", encoding="ascii")
            probe.unlink()
            return candidate
        except OSError:
            continue
    raise OSError("Aucun dossier de sauvegarde inscriptible n'est disponible.")


def backup_is_due(*, now: datetime | None = None, backup_dir: Path | None = None, interval_days: int = 14) -> bool:
    """Indique si l'export bimensuel doit être exécuté."""
    directory = backup_dir or _backup_directory()
    try:
        payload = json.loads((directory / "backup_schedule.json").read_text(encoding="utf-8"))
        last = datetime.fromisoformat(str(payload.get("last_success_at", "")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return True
    return (now or datetime.now()) - last >= timedelta(days=max(1, int(interval_days)))


def executer_backup(*, force: bool = False) -> dict:
    """Exécute la sauvegarde de la base de données, compresse et applique la rotation."""
    mysqldump_path = _find_mysqldump()
    if not mysqldump_path:
        logger.warning("mysqldump n'a pas été trouvé. Le backup automatique ne peut pas s'exécuter.")
        return

    config = load_db_config()
    db_name = config.get("database")
    db_user = config.get("user")
    db_pass = config.get("password")
    db_host = config.get("host", "localhost")

    if not db_name:
        return {"status": "error", "message": "Base de données non configurée."}

    backup_config = load_app_config().get("database_backup", {})
    if backup_config.get("enabled", True) is False and not force:
        return {"status": "disabled"}
    interval_days = int(backup_config.get("interval_days", 14) or 14)
    try:
        app_data_dir = _backup_directory()
    except OSError as exc:
        logger.error(str(exc))
        return {"status": "error", "message": str(exc)}
    if not force and not backup_is_due(backup_dir=app_data_dir, interval_days=interval_days):
        return {"status": "not_due", "path": str(app_data_dir)}

    # Création du répertoire de sauvegarde
    # On le place dans les données de l'application locale de l'utilisateur pour être sûr d'avoir les droits
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    sql_file = app_data_dir / f"backup_{db_name}_{timestamp}.sql"
    zip_file = app_data_dir / f"backup_{db_name}_{timestamp}.zip"

    # Construction de la commande mysqldump
    # Attention aux mots de passe vides
    cmd = [
        mysqldump_path,
        "-h", db_host,
        "-u", db_user,
        f"--result-file={sql_file}"
    ]
    if db_pass:
        cmd.insert(3, f"-p{db_pass}")
        
    cmd.append(db_name)

    try:
        # Exécution silencieuse
        process = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        
        if process.returncode != 0:
            logger.error(f"Erreur lors de la création de la sauvegarde SQL: {process.stderr}")
            if sql_file.exists():
                sql_file.unlink()
            return

        checksum = hashlib.sha256(sql_file.read_bytes()).hexdigest()
        with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(sql_file, arcname=sql_file.name)
            zipf.writestr(f"{sql_file.name}.sha256", f"{checksum}  {sql_file.name}\n")

        with zipfile.ZipFile(zip_file, "r") as archive:
            if archive.testzip() is not None:
                raise ValueError("Archive ZIP corrompue après création.")
        
        # Nettoyage du fichier SQL original
        sql_file.unlink()
        
        logger.info(f"Sauvegarde réussie: {zip_file}")

        # Rotation : garder uniquement les MAX_BACKUPS les plus récents
        schedule_state = {"last_success_at": datetime.now().isoformat(), "file": str(zip_file), "sha256": checksum}
        _backup_state_path(app_data_dir).write_text(json.dumps(schedule_state, indent=2), encoding="utf-8")
        retention = int(backup_config.get("retention", MAX_BACKUPS) or MAX_BACKUPS)
        _rotation_backups(app_data_dir, db_name, max_backups=max(1, retention))
        return {"status": "completed", "path": str(zip_file), "sha256": checksum}

    except Exception as e:
        logger.error(f"Erreur inattendue lors du backup: {e}")


def _rotation_backups(backup_dir: Path, db_name: str, *, max_backups: int = MAX_BACKUPS):
    """Supprime les anciennes sauvegardes si le nombre dépasse MAX_BACKUPS."""
    try:
        # Chercher tous les zips de cette base de données
        pattern = f"backup_{db_name}_*.zip"
        backups = list(backup_dir.glob(pattern))
        
        if len(backups) <= max_backups:
            return

        # Trier par date de modification (le plus récent en premier)
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Supprimer ceux qui sont en trop
        for old_backup in backups[max_backups:]:
            try:
                old_backup.unlink()
                logger.info(f"Ancienne sauvegarde supprimée (rotation): {old_backup.name}")
            except Exception as e:
                logger.error(f"Impossible de supprimer l'ancienne sauvegarde {old_backup.name}: {e}")
                
    except Exception as e:
        logger.error(f"Erreur lors de la rotation des sauvegardes: {e}")


def lancer_backup_en_arriere_plan():
    """Démarre le backup dans un thread séparé pour ne pas bloquer l'UI."""
    thread = threading.Thread(target=executer_backup, daemon=True, name="AutoBackupThread")
    thread.start()
