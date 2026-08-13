from datetime import date

from tap.core.auto_status_updater import (
    _is_special_rollover_automatic_enabled,
    executer_basculement_special_manuel,
    executer_mise_a_jour_automatique,
)
from tap.core.date_utils import SPECIAL_ROLLOVER_START, build_special_rollover_month_choices


def test_special_rollover_month_choices_start_in_october_2025():
    choices = build_special_rollover_month_choices(years_ahead=0, reference_date=date(2025, 12, 1))

    assert choices
    assert choices[0].startswith("Octobre 2025")
    assert not any(choice.startswith("Septembre 2025") for choice in choices)


def test_executer_basculement_special_manuel_rejects_month_before_start():
    result = executer_basculement_special_manuel(date(2025, 9, 1))

    assert result["status"] == "error"
    assert "10/2025" in result["message"]


def test_executer_mise_a_jour_automatique_skips_special_rollover_by_default(monkeypatch):
    monkeypatch.setattr(
        "tap.core.auto_status_updater._is_special_rollover_automatic_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "tap.core.auto_status_updater.creer_loyers_recurrents_mensuels",
        lambda reference_date=None: {"status": "disabled", "created": 0, "errors": 0},
    )
    monkeypatch.setattr(
        "tap.core.auto_status_updater.verifier_et_mettre_a_jour_statuts",
        lambda reference_date=None: (0, 0),
    )
    monkeypatch.setattr(
        "tap.core.auto_status_updater.verifier_rappel_litigieux",
        lambda reference_date=None: {"status": "skipped", "count": 0},
    )
    monkeypatch.setattr(
        "tap.core.auto_status_updater.obtenir_paiements_a_suivi",
        lambda reference_date=None: [],
    )

    called = {"rollover": False}

    def _fake_rollover(reference_date=None):
        called["rollover"] = True
        return {"status": "done", "created": 1, "errors": 0, "month": "2025-10", "message": ""}

    monkeypatch.setattr(
        "tap.core.auto_status_updater.creer_souscriptions_speciales_mensuelles",
        _fake_rollover,
    )

    rapport = executer_mise_a_jour_automatique(date(2026, 3, 15))

    assert called["rollover"] is False
    assert rapport["rollover_special_status"] == "manual_only"
    assert rapport["creations_speciales"] == 0


def test_special_rollover_start_constant():
    assert SPECIAL_ROLLOVER_START == date(2025, 10, 1)


def test_is_special_rollover_automatic_enabled_default_false(monkeypatch):
    monkeypatch.setattr(
        "tap.core.auto_status_updater.load_app_config",
        lambda: {"automatic_maintenance": {}},
    )
    assert _is_special_rollover_automatic_enabled() is False
