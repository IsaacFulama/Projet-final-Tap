"""Démarrage guidé pour un utilisateur non informaticien."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from tap.config.settings import get_base_dir, load_db_config
from tap.infrastructure.database.connection import obtenir_connexion
from tap.infrastructure.database.migrations import run_migrations

logger = logging.getLogger("tap.startup")


def _find_executable(names: tuple[str, ...]) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def ensure_startup_ready() -> dict:
    """Prépare l'application et renvoie un état compréhensible par l'UI."""
    result = {
        "ok": False,
        "database": "unknown",
        "migrations": None,
        "backup": "not_requested",
        "message": "",
        "actions": [],
    }
    try:
        config = load_db_config()
        conn = obtenir_connexion()
        if conn is None or not conn.is_connected():
            result["database"] = "offline"
            result["message"] = (
                "La base de données n'est pas accessible. "
                "Démarrez MariaDB/XAMPP puis cliquez sur Réessayer."
            )
            result["actions"] = ["Démarrer MariaDB/XAMPP", "Vérifier config.json"]
            return result
        conn.close()
        result["database"] = "connected"

        result["migrations"] = run_migrations()
        result["ok"] = True
        result["message"] = "Base de données prête."
        return result
    except Exception as exc:
        logger.exception("Échec de préparation au démarrage")
        result["message"] = f"Préparation impossible : {exc}"
        result["actions"] = ["Vérifier MariaDB/XAMPP", "Vérifier config.json", "Contacter l'administrateur"]
        return result


def start_mobile_server_if_configured() -> bool:
    """Lance le serveur mobile si l'utilisateur l'a activé dans config.json."""
    config_path = get_base_dir() / "config.json"
    try:
        import json
        config = json.loads(config_path.read_text(encoding="utf-8"))
        mobile = config.get("mobile_portal", {})
        if not mobile.get("enabled", False):
            return False
        if os.getenv("TAP_MOBILE_API_KEY"):
            return False
        # Le serveur mobile reste un composant séparé dans cette version ;
        # l'activation automatique sera effectuée par le lanceur client.
        return False
    except Exception:
        return False

