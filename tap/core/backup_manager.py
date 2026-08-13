import os
import shutil
import zipfile
import subprocess
import threading
import glob
from datetime import datetime
from pathlib import Path
import logging

from tap.config.settings import load_db_config

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


def executer_backup():
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
        return

    # Création du répertoire de sauvegarde
    # On le place dans les données de l'application locale de l'utilisateur pour être sûr d'avoir les droits
    app_data_dir = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "TAP_Gestion_Loyers" / "Backups"
    app_data_dir.mkdir(parents=True, exist_ok=True)

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

        # Compression ZIP
        with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(sql_file, arcname=sql_file.name)
        
        # Nettoyage du fichier SQL original
        sql_file.unlink()
        
        logger.info(f"Sauvegarde réussie: {zip_file}")

        # Rotation : garder uniquement les MAX_BACKUPS les plus récents
        _rotation_backups(app_data_dir, db_name)

    except Exception as e:
        logger.error(f"Erreur inattendue lors du backup: {e}")


def _rotation_backups(backup_dir: Path, db_name: str):
    """Supprime les anciennes sauvegardes si le nombre dépasse MAX_BACKUPS."""
    try:
        # Chercher tous les zips de cette base de données
        pattern = f"backup_{db_name}_*.zip"
        backups = list(backup_dir.glob(pattern))
        
        if len(backups) <= MAX_BACKUPS:
            return

        # Trier par date de modification (le plus récent en premier)
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Supprimer ceux qui sont en trop
        for old_backup in backups[MAX_BACKUPS:]:
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
