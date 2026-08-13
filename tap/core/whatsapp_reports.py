from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import webbrowser
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from tap.infrastructure.database.connection import obtenir_connexion


@dataclass(frozen=True)
class WhatsAppConfig:
    """Configuration de l'envoi WhatsApp, totalement optionnelle."""

    enabled: bool = False
    mode: str = "disabled"
    recipient: str = ""
    token: str = ""
    phone_number_id: str = ""
    api_base_url: str = "https://graph.facebook.com/v20.0"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from: str = ""
    webhook_url: str = ""
    webhook_token: str = ""

    def with_recipient(self, recipient: str) -> "WhatsAppConfig":
        """Retourne une copie de la configuration avec un destinataire différent."""
        return replace(self, recipient=recipient)


def check_internet_connection(host: str = "8.8.8.8", port: int = 53, timeout: float = 3.0) -> bool:
    """Vérifie Internet avec HTTP, sans dépendre du DNS sortant sur le port 53."""
    del host, port
    probes = (
        "https://www.google.com/generate_204",
        "https://graph.facebook.com",
        "https://api.twilio.com",
    )
    for url in probes:
        try:
            request = Request(url, method="HEAD")
            with urlopen(request, timeout=timeout):
                return True
        except (HTTPError, URLError, TimeoutError, OSError):
            continue
    return False


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


def load_config_from_json(config_path: Path = Path("config.json")) -> dict[str, Any]:
    """Charge la configuration depuis le fichier config.json."""
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def load_whatsapp_config() -> WhatsAppConfig:
    """Charge la configuration WhatsApp depuis les variables d'environnement."""
    mode = _env("TAP_WHATSAPP_MODE", "disabled").lower()
    enabled = _env("TAP_WHATSAPP_ENABLED", "0").lower() in {"1", "true", "yes", "on"}

    return WhatsAppConfig(
        enabled=enabled and mode != "disabled",
        mode=mode,
        recipient=_env("TAP_WHATSAPP_TO"),
        token=_env("TAP_WHATSAPP_TOKEN"),
        phone_number_id=_env("TAP_WHATSAPP_PHONE_NUMBER_ID"),
        api_base_url=_env("TAP_WHATSAPP_API_BASE_URL", "https://graph.facebook.com/v20.0"),
        twilio_account_sid=_env("TAP_WHATSAPP_TWILIO_SID"),
        twilio_auth_token=_env("TAP_WHATSAPP_TWILIO_TOKEN"),
        twilio_from=_env("TAP_WHATSAPP_TWILIO_FROM"),
        webhook_url=_env("TAP_WHATSAPP_WEBHOOK_URL"),
        webhook_token=_env("TAP_WHATSAPP_WEBHOOK_TOKEN"),
    )


def _encode_multipart_formdata(fields: dict[str, str], files: list[tuple[str, str, str, bytes]]) -> tuple[bytes, str]:
    boundary = "----TAPBoundary" + hashlib.sha256(os.urandom(16)).hexdigest()[:24]
    boundary_bytes = boundary.encode("ascii")
    body = bytearray()

    for name, value in fields.items():
        body.extend(b"--" + boundary_bytes + b"\r\n")
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    for field_name, filename, content_type, file_data in files:
        body.extend(b"--" + boundary_bytes + b"\r\n")
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(file_data)
        body.extend(b"\r\n")

    body.extend(b"--" + boundary_bytes + b"--\r\n")
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _upload_whatsapp_media_to_cloud(config: WhatsAppConfig, filepath: Path) -> str:
    if not filepath.is_file() or not config.token or not config.phone_number_id:
        return ""

    try:
        with filepath.open("rb") as handle:
            file_bytes = handle.read()

        url = f"{config.api_base_url.rstrip('/')}/{config.phone_number_id}/media"
        payload, content_type = _encode_multipart_formdata(
            {"messaging_product": "whatsapp"},
            [("file", filepath.name, "application/pdf", file_bytes)],
        )
        request = Request(
            url,
            data=payload,
            headers={"Authorization": f"Bearer {config.token}", "Content-Type": content_type},
            method="POST",
        )
        with urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            return str(parsed.get("id", ""))
    except Exception:
        return ""


def _attachment_to_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    attachments = report.get("attachments") or []
    normalized: list[dict[str, Any]] = []
    for attachment in attachments:
        if isinstance(attachment, dict) and attachment.get("type") == "document":
            normalized.append({
                "type": "document",
                "path": str(attachment.get("path") or ""),
                "url": str(attachment.get("url") or ""),
                "filename": str(attachment.get("filename") or Path(attachment.get("path", "")).name),
            })
    return normalized


def _attachment_payload_for_webhook(attachment: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": attachment.get("type", "document"),
        "filename": attachment.get("filename", "attachment.pdf"),
    }
    path = attachment.get("path")
    if path and Path(path).is_file():
        try:
            with Path(path).open("rb") as handle:
                data["content_base64"] = base64.b64encode(handle.read()).decode("ascii")
        except Exception:
            data["path"] = path
    elif attachment.get("url"):
        data["url"] = attachment["url"]
    return data


def build_whatsapp_report_message(report: dict[str, Any]) -> str:
    """Construit un message WhatsApp court et lisible pour la maintenance."""
    period = (
        report.get("month")
        or report.get("period")
        or report.get("date")
        or report.get("period_key")
        or "période inconnue"
    )
    lines = [
        "TAP - Rapport automatique",
        f"Période: {period}",
    ]

    rollover_status = str(report.get("rollover_special_status", "")).lower()
    if rollover_status in {"done", "already_done"} or any(
        key in report for key in ("creations_speciales", "rollover_overdue_updates", "rollover_errors", "overdue_updates")
    ):
        created = int(report.get("creations_speciales", 0) or 0)
        overdue_updates = int(report.get("rollover_overdue_updates", report.get("overdue_updates", 0)) or 0)
        errors = int(report.get("rollover_errors", 0) or 0)
        lines.append(
            f"Clôture mensuelle: {created} création(s), {overdue_updates} passage(s) en Litigieux, {errors} erreur(s)."
        )

    reminder_status = str(report.get("litigieux_reminder_status", "")).lower()
    reminder_count = int(report.get("litigieux_reminder_count", 0) or 0)
    if reminder_status in {"done", "already_done"} or reminder_count > 0:
        lines.append(f"Rappel litigieux: {reminder_count} paiement(s) en retard.")

    mis_a_jour = report.get("mis_a_jour")
    erreurs = report.get("erreurs")
    if mis_a_jour is not None or erreurs is not None:
        lines.append(
            f"Contrôles: {int(mis_a_jour or 0)} mise(s) à jour, {int(erreurs or 0)} erreur(s)."
        )

    message_statut = report.get("message")
    if message_statut:
        lines.append(f"Statut: {message_statut}")

    return "\n".join(lines).strip()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_latest_maintenance_report() -> dict[str, Any] | None:
    """
    Reconstitue le dernier rapport de maintenance depuis la base,
    sans dépendre de l'interface graphique.
    """
    conn = None
    cursor = None
    try:
        conn = obtenir_connexion()
        if not conn or not conn.is_connected():
            return None

        cursor = conn.cursor()
        cursor.execute(
            """
                SELECT MAX(period_key)
                FROM maintenance_journal
                WHERE status = 'done'
            """
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            return None

        period_key = str(row[0])
        cursor.execute(
            """
                SELECT operation_key, details_json, completed_at
                FROM maintenance_journal
                WHERE status = 'done' AND period_key = %s
                ORDER BY completed_at ASC
            """,
            (period_key,),
        )
        rows = cursor.fetchall() or []
        if not rows:
            return None

        merged: dict[str, Any] = {
            "period_key": period_key,
            "month": period_key,
        }
        for operation_key, details_json, completed_at in rows:
            details = {}
            if details_json:
                try:
                    details = json.loads(details_json) if isinstance(details_json, str) else dict(details_json)
                except Exception:
                    details = {}
            if operation_key == "special_monthly_rollover":
                merged.update(
                    {
                        "rollover_special_status": "done",
                        "creations_speciales": details.get("created", details.get("creations", 0)),
                        "rollover_overdue_updates": details.get("overdue_updates", 0),
                        "rollover_errors": details.get("errors", 0),
                        "rollover_special_message": details.get("message", ""),
                    }
                )
            elif operation_key == "litigieux_monthly_reminder":
                merged.update(
                    {
                        "litigieux_reminder_status": "done",
                        "litigieux_reminder_count": details.get("count", 0),
                        "litigieux_reminder_message": details.get("message", ""),
                    }
                )
            if completed_at:
                merged["completed_at"] = str(completed_at)

        merged["message"] = build_whatsapp_report_message(merged)
        return merged
    except Exception:
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def _state_file(default_name: str = "whatsapp_report_state.json") -> Path:
    base = Path("error_reports")
    base.mkdir(parents=True, exist_ok=True)
    return base / default_name


def _signature(message: str, period: str) -> str:
    digest = hashlib.sha256(f"{period}\n{message}".encode("utf-8")).hexdigest()
    return digest[:16]


def has_already_sent(report: dict[str, Any], state_path: Path | None = None) -> bool:
    state_path = state_path or _state_file()
    if not state_path.exists():
        return False

    try:
        state = _read_json(state_path)
    except Exception:
        return False

    period = str(report.get("period_key") or report.get("month") or "")
    message = str(report.get("message") or build_whatsapp_report_message(report))
    return state.get("period") == period and state.get("signature") == _signature(message, period)


def mark_as_sent(report: dict[str, Any], state_path: Path | None = None) -> None:
    state_path = state_path or _state_file()
    period = str(report.get("period_key") or report.get("month") or "")
    message = str(report.get("message") or build_whatsapp_report_message(report))
    payload = {
        "period": period,
        "signature": _signature(message, period),
        "sent_at": report.get("completed_at") or report.get("date") or "",
    }
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _http_post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers={**headers, "Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body


def _http_post_form(url: str, data: dict[str, Any], headers: dict[str, str]) -> tuple[int, str]:
    encoded = urlencode(data).encode("utf-8")
    request = Request(url, data=encoded, headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body


def get_monthly_data_by_status(status: str, month: str | None = None) -> list[tuple]:
    """Récupère les données du mois donné filtrées par statut."""
    conn = None
    cursor = None
    try:
        conn = obtenir_connexion()
        if not conn or not conn.is_connected():
            return []

        cursor = conn.cursor()
        target_month = month or datetime.now().strftime("%Y-%m")
        
        query = """
            SELECT 
                l.nom, 
                l.prenom, 
                p.mois,
                p.montant,
                p.devise,
                p.statut_souscription,
                p.statut
            FROM paiements p
            LEFT JOIN locataires l ON p.locataire_id = l.id
            WHERE p.mois LIKE %s AND p.statut = %s
            ORDER BY UPPER(l.nom) ASC, UPPER(l.prenom) ASC
        """
        
        cursor.execute(query, (f"{target_month}%", status))
        return cursor.fetchall() or []
    except Exception:
        return []
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def generate_monthly_pdf_reports(
    output_dir: Path = Path("error_reports"),
    month: str | None = None,
    report_types: list[str] | None = None,
) -> dict[str, Path]:
    """Génère des rapports PDF mensuels filtrés par statut."""
    from tap.presentation.dialogs.export_pdf import PDFReportService
    
    valid_types = ["en_regle", "litigieux"]
    requested_types = [rt for rt in (report_types or valid_types) if rt in valid_types]
    if not requested_types:
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)
    report_month = month or datetime.now().strftime("%Y-%m")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    
    reports: dict[str, Path] = {}
    
    if "en_regle" in requested_types:
        en_regle_data = get_monthly_data_by_status("En règle", month=report_month)
        if en_regle_data:
            en_regle_path = output_dir / f"rapport_en_regle_{report_month}_{timestamp}.pdf"
            if PDFReportService.generate_pdf_report(
                en_regle_data,
                str(en_regle_path),
                filter_summary=f"Mois: {report_month}, Statut: En règle",
                title="TAP - Rapport Mensuel (En règle)"
            ):
                reports["en_regle"] = en_regle_path
    
    if "litigieux" in requested_types:
        litigieux_data = get_monthly_data_by_status("Litigieux", month=report_month)
        if litigieux_data:
            litigieux_path = output_dir / f"rapport_litigieux_{report_month}_{timestamp}.pdf"
            if PDFReportService.generate_pdf_report(
                litigieux_data,
                str(litigieux_path),
                filter_summary=f"Mois: {report_month}, Statut: Litigieux",
                title="TAP - Rapport Mensuel (Litigieux)"
            ):
                reports["litigieux"] = litigieux_path
    
    return reports


def send_whatsapp_report(report: dict[str, Any], config: WhatsAppConfig | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    """
    Envoie un rapport WhatsApp via le mode configuré.

    Modes supportés:
    - `cloud` : WhatsApp Cloud API de Meta
    - `twilio` : API Twilio WhatsApp
    - `webhook` : relais HTTP externe, utile pour Make/Zapier/n8n
    - `disabled` : aucun envoi
    """
    config = config or load_whatsapp_config()
    message = str(report.get("message") or build_whatsapp_report_message(report))
    period = str(report.get("period_key") or report.get("month") or "")
    attachments = _attachment_to_report(report)

    if dry_run:
        return {
            "status": "dry_run",
            "mode": config.mode,
            "period": period,
            "message": message,
            "attachments": attachments,
        }

    if not config.enabled or config.mode == "disabled":
        return {
            "status": "disabled",
            "mode": config.mode,
            "period": period,
            "message": message,
            "attachments": attachments,
        }

    if not config.recipient:
        return {
            "status": "error",
            "mode": config.mode,
            "period": period,
            "message": "Le destinataire WhatsApp TAP_WHATSAPP_TO est manquant.",
            "attachments": attachments,
        }

    try:
        if config.mode == "cloud":
            if not config.token or not config.phone_number_id:
                return {
                    "status": "error",
                    "mode": config.mode,
                    "period": period,
                    "message": "Configuration Cloud API incomplète.",
                    "attachments": attachments,
                }

            payload: dict[str, Any]
            if attachments:
                attachment = attachments[0]
                document_payload: dict[str, Any] = {
                    "filename": attachment["filename"],
                }
                if attachment.get("url"):
                    document_payload["link"] = attachment["url"]
                else:
                    media_id = _upload_whatsapp_media_to_cloud(config, Path(attachment["path"]))
                    if not media_id:
                        return {
                            "status": "error",
                            "mode": config.mode,
                            "period": period,
                            "message": "Impossible de charger le PDF sur WhatsApp Cloud API.",
                            "attachments": attachments,
                        }
                    document_payload["id"] = media_id

                payload = {
                    "messaging_product": "whatsapp",
                    "to": config.recipient,
                    "type": "document",
                    "document": {
                        **document_payload,
                        "caption": message,
                    },
                }
            else:
                payload = {
                    "messaging_product": "whatsapp",
                    "to": config.recipient,
                    "type": "text",
                    "text": {"preview_url": False, "body": message},
                }

            url = f"{config.api_base_url.rstrip('/')}/{config.phone_number_id}/messages"
            status_code, response_body = _http_post_json(
                url,
                payload,
                {"Authorization": f"Bearer {config.token}"},
            )
            return {
                "status": "sent",
                "mode": config.mode,
                "period": period,
                "http_status": status_code,
                "response": response_body,
                "message": message,
                "attachments": attachments,
            }

        if config.mode == "twilio":
            if not config.twilio_account_sid or not config.twilio_auth_token or not config.twilio_from:
                return {
                    "status": "error",
                    "mode": config.mode,
                    "period": period,
                    "message": "Configuration Twilio incomplète.",
                    "attachments": attachments,
                }

            has_media_url = False
            data: dict[str, Any] = {
                "From": config.twilio_from if config.twilio_from.startswith("whatsapp:") else f"whatsapp:{config.twilio_from}",
                "To": config.recipient if config.recipient.startswith("whatsapp:") else f"whatsapp:{config.recipient}",
                "Body": message,
            }
            if attachments:
                attachment = attachments[0]
                if attachment.get("url"):
                    data["MediaUrl"] = attachment["url"]
                    has_media_url = True
                else:
                    return {
                        "status": "error",
                        "mode": config.mode,
                        "period": period,
                        "message": "Envoi de fichiers locaux non pris en charge pour Twilio sans URL publique.",
                        "attachments": attachments,
                    }

            if attachments and not has_media_url:
                return {
                    "status": "error",
                    "mode": config.mode,
                    "period": period,
                    "message": "Aucun URL de média disponible pour l'attachement Twilio.",
                    "attachments": attachments,
                }

            url = f"https://api.twilio.com/2010-04-01/Accounts/{config.twilio_account_sid}/Messages.json"
            auth = base64.b64encode(f"{config.twilio_account_sid}:{config.twilio_auth_token}".encode("utf-8")).decode("ascii")
            status_code, response_body = _http_post_form(
                url,
                data,
                {"Authorization": f"Basic {auth}"},
            )
            return {
                "status": "sent",
                "mode": config.mode,
                "period": period,
                "http_status": status_code,
                "response": response_body,
                "message": message,
                "attachments": attachments,
            }

        if config.mode == "webhook":
            if not config.webhook_url:
                return {
                    "status": "error",
                    "mode": config.mode,
                    "period": period,
                    "message": "URL webhook manquante.",
                    "attachments": attachments,
                }
            headers = {}
            if config.webhook_token:
                headers["Authorization"] = f"Bearer {config.webhook_token}"

            payload = {
                "channel": "whatsapp",
                "to": config.recipient,
                "message": message,
                "report": report,
                "attachments": [_attachment_payload_for_webhook(attachment) for attachment in attachments],
            }
            status_code, response_body = _http_post_json(
                config.webhook_url,
                payload,
                headers,
            )
            return {
                "status": "sent",
                "mode": config.mode,
                "period": period,
                "http_status": status_code,
                "response": response_body,
                "message": message,
                "attachments": attachments,
            }

        return {
            "status": "error",
            "mode": config.mode,
            "period": period,
            "message": f"Mode WhatsApp inconnu: {config.mode}",
            "attachments": attachments,
        }
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return {
            "status": "error",
            "mode": config.mode,
            "period": period,
            "message": str(exc),
            "attachments": attachments,
        }


def send_monthly_pdf_reports(
    recipients: list[str] | None = None,
    *,
    month: str | None = None,
    report_types: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Envoie les rapports PDF mensuels filtrés vers les destinataires configurés.

    Cette fonction vérifie d'abord la configuration et la connexion internet, génère
    les PDFs demandés pour le mois spécifié, puis les transmet via WhatsApp.
    """
    config_json = load_config_from_json()
    whatsapp_config = load_whatsapp_config()
    
    # Vérifier si la fonctionnalité est activée dans config.json
    whatsapp_settings = config_json.get("whatsapp_reports", {})
    if not whatsapp_settings.get("enabled", False):
        return {
            "status": "disabled",
            "message": "L'envoi automatique de rapports PDF est désactivé dans config.json",
        }

    if not whatsapp_settings.get("send_monthly_pdf", True):
        return {
            "status": "disabled",
            "message": "L'envoi des rapports PDF mensuels est désactivé (whatsapp_reports.send_monthly_pdf)",
        }
    
    # Déterminer le mois et les types de rapports demandés
    report_month = month or whatsapp_settings.get("report_month")
    requested_types = report_types or whatsapp_settings.get("report_types")
    if requested_types is None:
        requested_types = ["en_regle", "litigieux"]

    valid_types = {"en_regle", "litigieux"}
    requested_types = [rt for rt in requested_types if rt in valid_types]
    if not requested_types:
        return {
            "status": "error",
            "message": "Aucun type de rapport valide n'a été demandé. Utilisez en_regle et/ou litigieux.",
        }

    # Utiliser les destinataires du config.json si non spécifiés
    if recipients is None:
        recipients = whatsapp_settings.get("recipients", [])

    if not recipients and whatsapp_config.recipient:
        recipients = [whatsapp_config.recipient]
    
    if not recipients:
        return {
            "status": "error",
            "message": "Aucun destinataire configuré dans config.json (whatsapp_reports.recipients) ou via TAP_WHATSAPP_TO.",
        }

    # Un destinataire dans config.json ne suffit pas à envoyer un fichier :
    # il faut également un fournisseur configuré dans l'environnement
    # (Cloud API, Twilio ou webhook). Éviter de retourner "completed" alors
    # que send_whatsapp_report ne peut que répondre "disabled".
    if not dry_run and not _whatsapp_provider_ready(whatsapp_config):
        return {
            "status": "not_configured",
            "message": (
                "WhatsApp est activé dans config.json, mais aucun fournisseur "
                "API n'est configuré dans les variables TAP_WHATSAPP_."
            ),
        }

    # Vérifier la connexion uniquement lorsque l'envoi réel est possible.
    # Cela permet de retourner une erreur de configuration explicite au lieu
    # de masquer l'absence de fournisseur derrière un échec réseau.
    if not dry_run and whatsapp_settings.get("check_internet", True):
        if not check_internet_connection():
            return {
                "status": "no_internet",
                "message": "Pas de connexion internet. Les rapports n'ont pas été envoyés.",
            }
    
    current_month = report_month or datetime.now().strftime("%Y-%m")
    pdf_reports = generate_monthly_pdf_reports(month=current_month, report_types=requested_types)
    
    if not pdf_reports:
        return {
            "status": "no_data",
            "message": "Aucune donnée disponible pour générer les rapports PDF pour ce mois.",
            "month": current_month,
        }

    send_state = {
        "period_key": current_month,
        "message": f"Rapports PDF mensuels: {', '.join(requested_types)}",
    }
    if not dry_run and has_already_sent(send_state):
        return {
            "status": "already_sent",
            "message": "Les rapports PDF mensuels ont déjà été envoyés pour ce mois.",
            "month": current_month,
            "report_types": requested_types,
        }
    
    results: list[dict[str, Any]] = []
    all_sent = True
    
    for recipient in recipients:
        recipient_config = whatsapp_config.with_recipient(recipient)
        for report_type, pdf_path in pdf_reports.items():
            status_label = "En règle" if report_type == "en_regle" else "Litigieux"
            message = (
                f"TAP - Rapport mensuel {status_label}\nMois: {current_month}\n\n"
                "Veuillez trouver ci-joint le rapport PDF."
            )
            report_payload = {
                "month": current_month,
                "report_type": report_type,
                "status_label": status_label,
                "message": message,
                "attachments": [
                    {
                        "type": "document",
                        "path": str(pdf_path),
                        "filename": pdf_path.name,
                    }
                ],
            }
            result = send_whatsapp_report(report_payload, config=recipient_config, dry_run=dry_run)
            results.append({
                "recipient": recipient,
                "report_type": report_type,
                "pdf_path": str(pdf_path),
                **result,
            })
            if result.get("status") not in {"sent", "dry_run"}:
                all_sent = False

    if all_sent and not dry_run:
        mark_as_sent(send_state)

    status = "completed" if all_sent else "partial_failure"
    if dry_run:
        status = "dry_run"

    return {
        "status": status,
        "month": current_month,
        "reports_generated": list(pdf_reports.keys()),
        "report_types": requested_types,
        "recipients_count": len(recipients),
        "results": results,
    }


def send_sms_message(
    message: str,
    recipient: str,
    config: WhatsAppConfig | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Envoie un SMS via Twilio lorsque le canal SMS est configuré."""
    config = config or load_whatsapp_config()
    if dry_run:
        return {"status": "dry_run", "mode": "sms", "recipient": recipient, "message": message}
    if not config.enabled or config.mode == "disabled":
        return {"status": "disabled", "mode": "sms", "recipient": recipient, "message": message}
    if config.mode not in {"twilio", "sms_twilio"}:
        return {
            "status": "error",
            "mode": "sms",
            "recipient": recipient,
            "message": "Le canal SMS nécessite TAP_WHATSAPP_MODE=twilio.",
        }
    if not config.twilio_account_sid or not config.twilio_auth_token or not config.twilio_from:
        return {
            "status": "error",
            "mode": "sms",
            "recipient": recipient,
            "message": "Configuration Twilio SMS incomplète.",
        }

    try:
        from_number = config.twilio_from.replace("whatsapp:", "", 1)
        to_number = recipient.replace("whatsapp:", "", 1)
        data = {"From": from_number, "To": to_number, "Body": message}
        url = f"https://api.twilio.com/2010-04-01/Accounts/{config.twilio_account_sid}/Messages.json"
        auth = base64.b64encode(
            f"{config.twilio_account_sid}:{config.twilio_auth_token}".encode("utf-8")
        ).decode("ascii")
        status_code, response_body = _http_post_form(
            url,
            data,
            {"Authorization": f"Basic {auth}"},
        )
        return {
            "status": "sent",
            "mode": "sms",
            "recipient": recipient,
            "http_status": status_code,
            "response": response_body,
            "message": message,
        }
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return {
            "status": "error",
            "mode": "sms",
            "recipient": recipient,
            "message": f"Erreur d'envoi SMS: {exc}",
        }


def build_whatsapp_web_url(message: str, recipient: str) -> str:
    """Construit un lien WhatsApp Web avec le message déjà prérempli."""
    phone = "".join(char for char in str(recipient or "") if char.isdigit())
    if not phone:
        return ""
    return f"https://wa.me/{phone}?text={quote(message, safe='')}"


def open_whatsapp_web_reminder(message: str, recipient: str) -> dict[str, Any]:
    """Ouvre un rappel prêt à envoyer quand aucune API automatique n'est configurée."""
    url = build_whatsapp_web_url(message, recipient)
    if not url:
        return {"status": "error", "message": "Numéro de téléphone invalide."}
    try:
        opened = webbrowser.open(url)
        return {
            "status": "manual_opened" if opened else "manual_ready",
            "url": url,
            "recipient": recipient,
            "message": "Message WhatsApp préparé. Cliquez sur Envoyer dans WhatsApp Web.",
        }
    except Exception as exc:
        return {"status": "error", "url": url, "recipient": recipient, "message": str(exc)}


def _whatsapp_provider_ready(config: WhatsAppConfig) -> bool:
    """Vérifie si le mode automatique possède les identifiants nécessaires."""
    if not config.enabled or config.mode == "disabled":
        return False
    if config.mode == "cloud":
        return bool(config.token and config.phone_number_id)
    if config.mode in {"twilio", "sms_twilio"}:
        return bool(config.twilio_account_sid and config.twilio_auth_token and config.twilio_from)
    if config.mode == "webhook":
        return bool(config.webhook_url)
    return False


def get_overdue_reminder_candidates(reference_date: date | None = None) -> list[dict[str, Any]]:
    """Regroupe les paiements litigieux par locataire pour les rappels."""
    conn = None
    cursor = None
    date_reference = reference_date or date.today()
    mois_reference = date_reference.replace(day=1)
    grouped: dict[int, dict[str, Any]] = {}
    try:
        conn = obtenir_connexion()
        if not conn or not conn.is_connected():
            return []
        cursor = conn.cursor()
        cursor.execute(
            """
                SELECT p.locataire_id, l.nom, l.prenom, l.telephone,
                       p.mois, p.reste_a_payer, p.devise
                FROM paiements p
                JOIN locataires l ON l.id = p.locataire_id
                WHERE p.statut = 'Litigieux'
                  AND p.mois <= %s
                  AND COALESCE(p.reste_a_payer, 0) > 0
                ORDER BY l.nom ASC, l.prenom ASC, p.mois ASC, p.id ASC
            """,
            (mois_reference,),
        )
        for locataire_id, nom, prenom, telephone, mois, reste, devise in cursor.fetchall() or []:
            candidate = grouped.setdefault(
                int(locataire_id),
                {
                    "locataire_id": int(locataire_id),
                    "nom": str(nom or "").strip(),
                    "prenom": str(prenom or "").strip(),
                    "telephone": str(telephone or "").strip(),
                    "items": [],
                },
            )
            candidate["items"].append(
                {"mois": mois, "reste_a_payer": reste, "devise": str(devise or "").strip()}
            )
        return list(grouped.values())
    except Exception:
        return []
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def _build_overdue_reminder_message(candidate: dict[str, Any]) -> str:
    lines = [
        f"Bonjour {candidate['prenom']} {candidate['nom']},",
        "Votre compte présente un paiement de loyer en retard :",
    ]
    for item in candidate["items"]:
        mois = item["mois"].strftime("%m/%Y") if hasattr(item["mois"], "strftime") else str(item["mois"])
        montant = f"{float(item['reste_a_payer'] or 0):,.0f}".replace(",", " ")
        lines.append(f"- {mois} : {montant} {item['devise']}")
    lines.extend(
        [
            "Merci de régulariser votre situation ou de contacter la gestion.",
            "TAP - Gestion des Loyers",
        ]
    )
    return "\n".join(lines)


def send_overdue_payment_reminders(
    reference_date: date | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Envoie un rappel par locataire, une seule fois par mois et par canal."""
    settings = load_config_from_json().get("overdue_reminders", {})
    if not settings.get("enabled", False) and not dry_run:
        return {
            "status": "disabled",
            "sent": 0,
            "skipped": 0,
            "errors": 0,
            "message": "Les rappels d'impayés sont désactivés dans config.json.",
        }

    channel = str(settings.get("channel", "whatsapp")).strip().lower()
    if channel not in {"whatsapp", "sms"}:
        return {"status": "error", "sent": 0, "skipped": 0, "errors": 1, "message": "Canal de rappel invalide."}

    date_reference = reference_date or date.today()
    period = date_reference.strftime("%Y-%m")
    candidates = get_overdue_reminder_candidates(date_reference)
    if not candidates:
        return {"status": "no_data", "sent": 0, "skipped": 0, "errors": 0, "message": "Aucun paiement en retard avec téléphone renseigné."}

    whatsapp_config = load_whatsapp_config()
    use_whatsapp_web_fallback = (
        channel == "whatsapp"
        and not _whatsapp_provider_ready(whatsapp_config)
        and str(settings.get("fallback", "whatsapp_web")).lower() == "whatsapp_web"
        and not dry_run
    )
    conn = None
    cursor = None
    sent = skipped = opened = errors = 0
    results = []
    try:
        if not dry_run:
            conn = obtenir_connexion()
            cursor = conn.cursor()
            cursor.execute(
                """
                    CREATE TABLE IF NOT EXISTS maintenance_journal (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        operation_key VARCHAR(64) NOT NULL,
                        period_key VARCHAR(16) NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'running',
                        created_count INT NOT NULL DEFAULT 0,
                        error_count INT NOT NULL DEFAULT 0,
                        details_json TEXT NULL,
                        started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        completed_at DATETIME NULL,
                        UNIQUE KEY uq_operation_period (operation_key, period_key)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            conn.commit()

        for candidate in candidates:
            if not candidate["telephone"]:
                skipped += 1
                results.append(
                    {
                        "locataire_id": candidate["locataire_id"],
                        "status": "skipped",
                        "message": "Aucun numéro de téléphone renseigné.",
                    }
                )
                continue

            operation_key = f"overdue_reminder_{channel}_{candidate['locataire_id']}"
            if cursor:
                cursor.execute(
                    "SELECT status FROM maintenance_journal WHERE operation_key = %s AND period_key = %s",
                    (operation_key, period),
                )
                journal = cursor.fetchone()
                if journal and str(journal[0]).lower() == "done":
                    skipped += 1
                    continue

            message = _build_overdue_reminder_message(candidate)
            if use_whatsapp_web_fallback:
                result = open_whatsapp_web_reminder(message, candidate["telephone"])
            elif channel == "sms":
                recipient_config = whatsapp_config.with_recipient(candidate["telephone"])
                result = send_sms_message(message, candidate["telephone"], recipient_config, dry_run=dry_run)
            else:
                recipient_config = whatsapp_config.with_recipient(candidate["telephone"])
                result = send_whatsapp_report(
                    {"period_key": period, "month": period, "message": message},
                    config=recipient_config,
                    dry_run=dry_run,
                )
            results.append({"locataire_id": candidate["locataire_id"], **result})

            if result.get("status") in {"sent", "dry_run"}:
                sent += 1
                if cursor and not dry_run:
                    cursor.execute(
                        """
                            INSERT INTO maintenance_journal (
                                operation_key, period_key, status, created_count,
                                error_count, details_json, completed_at
                            ) VALUES (%s, %s, 'done', 1, 0, %s, CURRENT_TIMESTAMP)
                            ON DUPLICATE KEY UPDATE status='done', created_count=1,
                                error_count=0, details_json=VALUES(details_json),
                                completed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                        """,
                        (operation_key, period, json.dumps({"recipient": candidate["telephone"]})),
                    )
                    conn.commit()
            elif result.get("status") in {"manual_opened", "manual_ready"}:
                opened += 1
            elif result.get("status") == "disabled":
                skipped += 1
            else:
                errors += 1

        status = "dry_run" if dry_run else ("completed" if errors == 0 else "partial_failure")
        return {
            "status": status,
            "channel": channel,
            "period": period,
            "sent": sent,
            "opened": opened,
            "skipped": skipped,
            "errors": errors,
            "results": results,
        }
    except Exception as exc:
        if conn:
            conn.rollback()
        return {"status": "error", "sent": sent, "skipped": skipped, "errors": errors + 1, "message": str(exc)}
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
