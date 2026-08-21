import json
import os
import sys
from pathlib import Path

DEFAULT_DB_CONFIG = {
    "host": "localhost",
    "database": "gestion_loyers",
    "user": "root",
    "password": "",
    "port": 3306,
}


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def load_db_config() -> dict:
    base_dir = get_base_dir()
    search_paths = _config_search_paths(base_dir)

    for path in search_paths:
        if not path:
            continue
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                db_data = data.get("database", {})
                port = db_data.get("port", DEFAULT_DB_CONFIG["port"])
                try:
                    port = int(port)
                except (TypeError, ValueError):
                    port = DEFAULT_DB_CONFIG["port"]
                return {
                    "host": db_data.get("host", DEFAULT_DB_CONFIG["host"]),
                    "database": db_data.get("database", DEFAULT_DB_CONFIG["database"]),
                    "user": db_data.get("user", DEFAULT_DB_CONFIG["user"]),
                    "password": db_data.get("password", DEFAULT_DB_CONFIG["password"]),
                    "port": port,
                }
        except Exception:
            continue

    return DEFAULT_DB_CONFIG.copy()


def load_app_config() -> dict:
    base_dir = get_base_dir()
    search_paths = _config_search_paths(base_dir)

    for path in search_paths:
        if not path:
            continue
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    return json.load(handle)
        except Exception:
            continue

    return {}


def _config_search_paths(base_dir: Path) -> list[Path]:
    """Retourne les emplacements fiables de configuration.

    Le répertoire courant n'est pas fiable pour une application Windows : un
    raccourci peut définir un autre dossier de travail ou y laisser un ancien
    ``config.json``. Le fichier situé à côté de l'exécutable est prioritaire.
    ``TAP_CONFIG`` permet de choisir explicitement un fichier administré.
    """
    paths = []
    configured_path = os.environ.get("TAP_CONFIG")
    if configured_path:
        paths.append(Path(configured_path).expanduser())

    paths.append(base_dir / "config.json")
    if getattr(sys, "_MEIPASS", None):
        paths.append(Path(sys._MEIPASS) / "config.json")

    # Fallback utile pour le lancement depuis les sources, mais seulement
    # après la configuration de livraison.
    cwd_config = Path.cwd() / "config.json"
    if cwd_config.parent.resolve() != base_dir.resolve():
        paths.append(cwd_config)

    return list(dict.fromkeys(paths))
