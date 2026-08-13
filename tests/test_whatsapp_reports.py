from datetime import datetime
from pathlib import Path

from tap.core.whatsapp_reports import (
    WhatsAppConfig,
    build_whatsapp_report_message,
    get_monthly_data_by_status,
    has_already_sent,
    mark_as_sent,
    send_monthly_pdf_reports,
    send_whatsapp_report,
)


def test_build_whatsapp_report_message_mentions_litigieux():
    message = build_whatsapp_report_message(
        {
            "month": "2026-09",
            "creations_speciales": 4,
            "rollover_overdue_updates": 7,
            "rollover_errors": 1,
            "litigieux_reminder_count": 3,
            "mis_a_jour": 2,
            "erreurs": 0,
            "message": "Maintenance terminée",
        }
    )

    assert "TAP - Rapport automatique" in message
    assert "Période: 2026-09" in message
    assert "Clôture mensuelle: 4 création(s), 7 passage(s) en Litigieux, 1 erreur(s)." in message
    assert "Rappel litigieux: 3 paiement(s) en retard." in message


def test_sent_state_roundtrip(tmp_path: Path):
    report = {"period_key": "2026-09", "message": "hello", "completed_at": "2026-09-19 10:00:00"}
    state_path = tmp_path / "whatsapp_state.json"

    assert has_already_sent(report, state_path=state_path) is False
    mark_as_sent(report, state_path=state_path)
    assert has_already_sent(report, state_path=state_path) is True


def test_send_whatsapp_report_dry_run():
    result = send_whatsapp_report({"period_key": "2026-09"}, dry_run=True)

    assert result["status"] == "dry_run"
    assert result["period"] == "2026-09"


def test_send_monthly_pdf_reports_does_not_claim_success_without_provider(monkeypatch):
    monkeypatch.setattr(
        "tap.core.whatsapp_reports.load_config_from_json",
        lambda config_path=Path("config.json"): {
            "whatsapp_reports": {
                "enabled": True,
                "send_monthly_pdf": True,
                "recipients": ["+243852382067"],
                "check_internet": False,
            }
        },
    )
    monkeypatch.setattr(
        "tap.core.whatsapp_reports.load_whatsapp_config",
        lambda: WhatsAppConfig(enabled=False, mode="disabled"),
    )

    result = send_monthly_pdf_reports(month="2026-09")

    assert result["status"] == "not_configured"


def test_get_monthly_data_by_status_uses_paiements(monkeypatch):
    executed = []

    class FakeCursor:
        def execute(self, query, params=None):
            executed.append((query, params))

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self._cursor = FakeCursor()

        def cursor(self):
            return self._cursor

        def is_connected(self):
            return True

        def close(self):
            pass

    monkeypatch.setattr(
        "tap.core.whatsapp_reports.obtenir_connexion",
        lambda: FakeConnection(),
    )

    result = get_monthly_data_by_status("En règle", month="2026-09")

    assert result == []
    assert executed, "Expected the query to be executed"
    assert "FROM paiements" in executed[0][0]
    assert "souscriptions" not in executed[0][0]


def test_send_monthly_pdf_reports_dry_run_with_attachments(monkeypatch):
    monkeypatch.setattr(
        "tap.core.whatsapp_reports.load_config_from_json",
        lambda config_path=Path("config.json"): {
            "whatsapp_reports": {
                "enabled": True,
                "send_monthly_pdf": True,
                "recipients": ["+243852382067"],
                "check_internet": False,
            }
        },
    )
    monkeypatch.setattr(
        "tap.core.whatsapp_reports.load_whatsapp_config",
        lambda: WhatsAppConfig(enabled=False, mode="disabled"),
    )
    monkeypatch.setattr(
        "tap.core.whatsapp_reports.generate_monthly_pdf_reports",
        lambda *args, **kwargs: {
            "en_regle": Path("error_reports/rapport_en_regle_2026-09_000000.pdf"),
            "litigieux": Path("error_reports/rapport_litigieux_2026-09_000000.pdf"),
        },
    )

    result = send_monthly_pdf_reports(dry_run=True)

    assert result["status"] == "dry_run"
    assert result["month"] == datetime.now().strftime("%Y-%m")
    assert result["reports_generated"] == ["en_regle", "litigieux"]
    assert result["recipients_count"] == 1
    assert all(item["status"] == "dry_run" for item in result["results"])


def test_send_monthly_pdf_reports_dry_run_with_selected_type(monkeypatch):
    monkeypatch.setattr(
        "tap.core.whatsapp_reports.load_config_from_json",
        lambda config_path=Path("config.json"): {
            "whatsapp_reports": {
                "enabled": True,
                "send_monthly_pdf": True,
                "recipients": ["+243852382067"],
                "check_internet": False,
            }
        },
    )
    monkeypatch.setattr(
        "tap.core.whatsapp_reports.load_whatsapp_config",
        lambda: WhatsAppConfig(enabled=False, mode="disabled"),
    )
    monkeypatch.setattr(
        "tap.core.whatsapp_reports.generate_monthly_pdf_reports",
        lambda month=None, report_types=None: {
            "en_regle": Path("error_reports/rapport_en_regle_2026-09_000000.pdf")
        } if month == "2026-09" and report_types == ["en_regle"] else {},
    )

    result = send_monthly_pdf_reports(month="2026-09", report_types=["en_regle"], dry_run=True)

    assert result["status"] == "dry_run"
    assert result["month"] == "2026-09"
    assert result["reports_generated"] == ["en_regle"]
    assert result["recipients_count"] == 1
    assert len(result["results"]) == 1
    assert result["results"][0]["report_type"] == "en_regle"
    assert all(item["status"] == "dry_run" for item in result["results"])
