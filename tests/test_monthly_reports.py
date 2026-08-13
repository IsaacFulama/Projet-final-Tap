from tap.core.monthly_reports import summarize_monthly_rows


def test_summarize_monthly_rows_calculates_financial_totals():
    summary = summarize_monthly_rows(
        [
            {"montant_paye": "100", "reste_a_payer": "0", "statut": "En règle", "devise": "USD"},
            {"montant_paye": 40, "reste_a_payer": 60, "statut": "Litigieux", "devise": "USD"},
        ],
        "2026-07",
    )

    assert summary["month"] == "2026-07"
    assert summary["total_encaisse"] == 140.0
    assert summary["total_restant"] == 60.0
    assert summary["paiements_en_regle"] == 1
    assert summary["paiements_litigieux"] == 1
    assert summary["devises"] == ["USD"]
