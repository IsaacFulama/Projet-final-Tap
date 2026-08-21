"""Configuration automatique du portail mobile pour une livraison Windows."""

from __future__ import annotations

import json
import os
import secrets
import socket
from pathlib import Path

from tap.config.settings import get_base_dir, load_app_config


def _secrets_path() -> Path:
    configured = os.getenv("TAP_MOBILE_SECRETS_FILE", "").strip()
    if configured:
        return Path(configured).expanduser()
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / "TAP_Gestion_Loyers" / "mobile_secrets.json"
    return get_base_dir() / "mobile_secrets.json"


def _load_or_create_secrets() -> dict[str, str]:
    path = _secrets_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("api_key") and data.get("token_pepper"):
            return {"api_key": str(data["api_key"]), "token_pepper": str(data["token_pepper"])}
    except (OSError, ValueError, TypeError):
        pass

    data = {
        "api_key": secrets.token_urlsafe(32),
        "token_pepper": secrets.token_urlsafe(32),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        # Le portail locataire fonctionne sans l'API de synchronisation ; le
        # secret reste en mémoire si le dossier est protégé en écriture.
        pass
    return data


def detect_lan_ip() -> str:
    """Retourne l'adresse IPv4 utilisable par un téléphone sur le Wi-Fi."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Aucun paquet n'est envoyé par connect() pour une socket UDP.
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
        if address and not address.startswith("127."):
            return address
    except OSError:
        pass
    finally:
        sock.close()
    return "127.0.0.1"


def configure_mobile_environment() -> dict[str, str | int]:
    """Prépare les variables nécessaires et renvoie la configuration active."""
    app_config = load_app_config()
    mobile = app_config.get("mobile_portal", {}) if isinstance(app_config, dict) else {}
    mobile = mobile if isinstance(mobile, dict) else {}
    generated = _load_or_create_secrets()

    api_key = os.getenv("TAP_MOBILE_API_KEY", "").strip() or generated["api_key"]
    pepper = os.getenv("TAP_PORTAL_TOKEN_PEPPER", "").strip() or generated["token_pepper"]
    host = os.getenv("TAP_MOBILE_HOST", "").strip() or str(mobile.get("host", "0.0.0.0"))
    public_host = (
        os.getenv("TAP_MOBILE_HOST_PUBLIC", "").strip()
        or str(mobile.get("public_host", "")).strip()
        or detect_lan_ip()
    )
    if host in {"localhost", "127.0.0.1"} and public_host not in {"", "localhost", "127.0.0.1"}:
        host = "0.0.0.0"
    try:
        port = int(os.getenv("TAP_MOBILE_PORT", str(mobile.get("port", 8765))))
    except (TypeError, ValueError):
        port = 8765
    port = max(1024, min(port, 65535))

    os.environ["TAP_MOBILE_API_KEY"] = api_key
    os.environ["TAP_PORTAL_TOKEN_PEPPER"] = pepper
    os.environ["TAP_MOBILE_HOST"] = host
    os.environ["TAP_MOBILE_HOST_PUBLIC"] = public_host
    os.environ["TAP_MOBILE_PORT"] = str(port)
    return {
        "host": host,
        "public_host": public_host,
        "port": port,
        "api_key": api_key,
    }


def portal_url(token: str, *, public_host: str | None = None, port: int | None = None) -> str:
    config = configure_mobile_environment()
    host = public_host or str(config["public_host"])
    active_port = int(port or config["port"])
    return f"http://{host}:{active_port}/portal/{token}"


def receipt_url(token: str, payment_id: int, *, base_url: str | None = None) -> str:
    root = (base_url or portal_url(token)).rstrip("/")
    if "/portal/" in root:
        root = root.split("/portal/", 1)[0]
    return f"{root}/portal/{token}/payments/{int(payment_id)}/receipt"


def payment_link_url(token: str, *, public_host: str | None = None, port: int | None = None) -> str:
    config = configure_mobile_environment()
    host = public_host or str(config["public_host"])
    active_port = int(port or config["port"])
    return f"http://{host}:{active_port}/pay/{token}"


def should_autostart() -> bool:
    config = load_app_config()
    mobile = config.get("mobile_portal", {}) if isinstance(config, dict) else {}
    if not isinstance(mobile, dict):
        return True
    value = mobile.get("enabled", True)
    return value is not False
