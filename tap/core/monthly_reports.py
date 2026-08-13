"""Rapports mensuels financiers et diffusion multi-canal."""

from __future__ import annotations

import json
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from fpdf import FPDF

from tap.config.settings import load_app_config
from tap.infrastructure.database.connection import ConnectionProvider, obtenir_connexion


def summarize_monthly_rows(rows: list[dict[str, Any]], month: str) -> dict[str, Any]:
    """Calcule une synthèse déterministe à partir de lignes de paiements."""
    total_encaisse = sum(float(row.get("montant_paye") or 0) for row in rows)
    total_restant = sum(float(row.get("reste_a_payer") or 0) for row in rows)
    return {
        "month": month,
        "total_encaisse": round(total_encaisse, 2),
        "total_restant": round(total_restant, 2),
        "paiements_total": len(rows),
        "paiements_en_regle": sum(row.get("statut") == "En règle" for row in rows),
        "paiements_litigieux": sum(row.get("statut") == "Litigieux" for row in rows),
        "devises": sorted({str(row.get("devise") or "") for row in rows if row.get("devise")}),
    }


def get_monthly_summary(
    month: str | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> dict[str, Any]:
    """Récupère les paiements du mois et retourne les indicateurs financiers."""
    target_month = month or datetime.now().strftime("%Y-%m")
    conn = obtenir_connexion(connection_provider)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT p.montant_paye, p.reste_a_payer, p.statut, p.devise
            FROM paiements p
            WHERE p.mois >= %s AND p.mois < DATE_ADD(%s, INTERVAL 1 MONTH)
            """,
            (f"{target_month}-01", f"{target_month}-01"),
        )
        rows = [
            {"montant_paye": row[0], "reste_a_payer": row[1], "statut": row[2], "devise": row[3]}
            for row in cursor.fetchall()
        ]
        return summarize_monthly_rows(rows, target_month)
    finally:
        cursor.close()
        if conn.is_connected():
            conn.close()


def generate_monthly_summary_pdf(summary: dict[str, Any], output_path: Path) -> Path:
    """Génère le PDF récapitulatif destiné au propriétaire/gestionnaire."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, f"TAP Gestion des Loyers - Rapport {summary['month']}", ln=True)
    pdf.set_font("Helvetica", size=11)
    pdf.ln(5)
    values = (
        ("Total encaissé", summary["total_encaisse"]),
        ("Total restant à payer", summary["total_restant"]),
        ("Nombre de paiements", summary["paiements_total"]),
        ("Paiements en règle", summary["paiements_en_regle"]),
        ("Paiements litigieux", summary["paiements_litigieux"]),
    )
    for label, value in values:
        pdf.cell(90, 9, str(label))
        pdf.cell(0, 9, str(value), ln=True)
    pdf.cell(90, 9, "Devises")
    pdf.cell(0, 9, ", ".join(summary.get("devises", [])) or "-", ln=True)
    pdf.output(str(output_path))
    return output_path


def write_internal_notification(summary: dict[str, Any], output_dir: Path = Path("error_reports")) -> Path:
    """Dépose une notification locale lisible par l'interface ou un superviseur."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"notification_rapport_{summary['month']}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def send_email_report(summary: dict[str, Any], pdf_path: Path, settings: dict[str, Any]) -> dict[str, Any]:
    """Envoie le rapport par SMTP lorsque l'e-mail est explicitement configuré."""
    recipients = settings.get("recipients", [])
    if not settings.get("enabled") or not recipients:
        return {"status": "disabled"}
    message = EmailMessage()
    message["Subject"] = f"Rapport loyers {summary['month']}"
    message["From"] = settings.get("from") or settings.get("username", "")
    message["To"] = ", ".join(recipients)
    message.set_content(
        f"Total encaissé : {summary['total_encaisse']}\n"
        f"Reste à payer : {summary['total_restant']}\n"
        f"Paiements en règle : {summary['paiements_en_regle']}\n"
        f"Paiements litigieux : {summary['paiements_litigieux']}"
    )
    message.add_attachment(pdf_path.read_bytes(), maintype="application", subtype="pdf", filename=pdf_path.name)
    with smtplib.SMTP(settings["host"], int(settings.get("port", 587)), timeout=30) as smtp:
        if settings.get("starttls", True):
            smtp.starttls()
        if settings.get("username"):
            smtp.login(settings["username"], settings.get("password", ""))
        smtp.send_message(message)
    return {"status": "sent", "recipients_count": len(recipients)}


def generate_and_publish_monthly_report(
    month: str | None = None,
    output_dir: Path = Path("error_reports"),
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Produit le rapport, la notification interne et les diffusions configurées."""
    config = load_app_config()
    target_month = month or datetime.now().strftime("%Y-%m")
    state_path = output_dir / "monthly_report_state.json"
    if not dry_run and state_path.exists():
        try:
            if json.loads(state_path.read_text(encoding="utf-8")).get("month") == target_month:
                return {"status": "already_published", "month": target_month}
        except (OSError, json.JSONDecodeError):
            pass
    summary = get_monthly_summary(target_month)
    pdf_path = generate_monthly_summary_pdf(summary, output_dir / f"rapport_mensuel_{target_month}.pdf")
    notification_path = write_internal_notification(summary, output_dir)
    result: dict[str, Any] = {
        "status": "dry_run" if dry_run else "completed",
        "month": target_month,
        "summary": summary,
        "pdf_path": str(pdf_path),
        "notification_path": str(notification_path),
        "channels": {"internal": "written"},
    }
    if dry_run:
        result["channels"].update({"email": "dry_run", "whatsapp": "dry_run"})
        return result
    email_settings = config.get("monthly_report", {}).get("email", {})
    result["channels"]["email"] = send_email_report(summary, pdf_path, email_settings)
    whatsapp_settings = config.get("monthly_report", {}).get("whatsapp", {})
    if whatsapp_settings.get("enabled"):
        from tap.core.whatsapp_reports import send_whatsapp_report, WhatsAppConfig

        recipient = whatsapp_settings.get("recipient", "")
        payload = {
            "month": target_month,
            "message": (
                f"TAP - Rapport mensuel {target_month}\n"
                f"Encaissé: {summary['total_encaisse']}\n"
                f"Reste: {summary['total_restant']}\n"
                f"En règle: {summary['paiements_en_regle']} | Litigieux: {summary['paiements_litigieux']}"
            ),
            "attachments": [{"type": "document", "path": str(pdf_path), "filename": pdf_path.name}],
        }
        result["channels"]["whatsapp"] = send_whatsapp_report(
            payload, config=WhatsAppConfig(enabled=True, mode=whatsapp_settings.get("mode", "disabled"), recipient=recipient)
        )
    else:
        result["channels"]["whatsapp"] = {"status": "disabled"}
    if result["status"] == "completed":
        state_path.write_text(json.dumps({"month": target_month}, ensure_ascii=False), encoding="utf-8")
    return result
