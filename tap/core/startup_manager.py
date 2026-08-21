"""Démarrage guidé pour un utilisateur non informaticien."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from tap.config.settings import get_base_dir, load_db_config
from tap.infrastructure.database.connection import connexion_prete, obtenir_connexion
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
        "database_host": "unknown",
        "database_name": "unknown",
        "database_port": None,
        "record_count": None,
        "migrations": None,
        "backup": "not_requested",
        "message": "",
        "actions": [],
    }
    try:
        config = load_db_config()
        result["database_host"] = config.get("host", "localhost")
        result["database_name"] = config.get("database", "gestion_loyers")
        result["database_port"] = config.get("port", 3306)
        conn = obtenir_connexion()
        if not connexion_prete(conn):
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

        # Le schéma peut être créé par les migrations lors du premier
        # démarrage : le comptage doit donc être effectué après celles-ci.
        conn = obtenir_connexion()
        if not connexion_prete(conn):
            result["database"] = "offline"
            result["message"] = (
                "La base de données n'est plus accessible après les migrations. "
                "Démarrez MariaDB/XAMPP puis cliquez sur Réessayer."
            )
            result["actions"] = ["Démarrer MariaDB/XAMPP", "Vérifier config.json"]
            return result
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM paiements")
            result["record_count"] = int(cursor.fetchone()[0])
        finally:
            cursor.close()
            conn.close()

        result["ok"] = True
        result["message"] = (
            f"Base de données prête ({result['record_count']} enregistrement(s) "
            f"dans {result['database_name']})."
        )
        logger.info(
            "Base prête: host=%s port=%s database=%s records=%s",
            result["database_host"],
            result["database_port"],
            result["database_name"],
            result["record_count"],
        )
        return result
    except Exception as exc:
        logger.exception("Échec de préparation au démarrage")
        result["message"] = f"Préparation impossible : {exc}"
        result["actions"] = ["Vérifier MariaDB/XAMPP", "Vérifier config.json", "Contacter l'administrateur"]
        return result


def start_mobile_server_if_configured() -> bool:
    """Lance discrètement le serveur mobile configuré pour la livraison."""
    try:
        from tap.mobile.runtime import configure_mobile_environment, should_autostart

        if not should_autostart():
            return False
        runtime = configure_mobile_environment()
        # Ne pas créer une seconde instance si le port répond déjà.
        import socket
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(0.15)
        try:
            if probe.connect_ex(("127.0.0.1", int(runtime["port"]))) == 0:
                return False
        finally:
            probe.close()

        base_dir = get_base_dir()
        server_exe = base_dir / "TAP_Mobile_Server.exe"
        if server_exe.exists():
            command = [str(server_exe)]
            cwd = server_exe.parent
        else:
            server_script = base_dir / "mobile_server.py"
            if not server_script.exists():
                return False
            command = [sys.executable, str(server_script)]
            cwd = base_dir
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        subprocess.Popen(
            command,
            cwd=str(cwd),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
        logger.info("Serveur mobile démarré sur http://%s:%s", runtime["public_host"], runtime["port"])
        return True
    except Exception:
        logger.exception("Impossible de démarrer automatiquement le serveur mobile")
        return False
