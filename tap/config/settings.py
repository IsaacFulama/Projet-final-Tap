import json
import sys
from pathlib import Path

DEFAULT_DB_CONFIG = {
    "host": "localhost",
    "database": "gestion_loyers",
    "user": "root",
    "password": "",
}


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def load_db_config() -> dict:
    base_dir = get_base_dir()
    search_paths = [
        Path.cwd() / "config.json",
        base_dir / "CLIENT_FINAL" / "config.json",
        base_dir / "config.json",
        Path(getattr(sys, "_MEIPASS", "")) / "config.json" if getattr(sys, "_MEIPASS", None) else None,
    ]

    for path in search_paths:
        if not path:
            continue
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                db_data = data.get("database", {})
                return {
                    "host": db_data.get("host", DEFAULT_DB_CONFIG["host"]),
                    "database": db_data.get("database", DEFAULT_DB_CONFIG["database"]),
                    "user": db_data.get("user", DEFAULT_DB_CONFIG["user"]),
                    "password": db_data.get("password", DEFAULT_DB_CONFIG["password"]),
                }
        except Exception:
            continue

    return DEFAULT_DB_CONFIG.copy()
