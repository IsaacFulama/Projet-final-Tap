from tap.core.dashboard_service import calculate_dashboard_metrics
from tap.core.models import SubscriptionRecord


def test_subscription_record_maps_sql_row_without_positional_access_in_callers():
    record = SubscriptionRecord.from_row(
        (10, 20, "KABONGO", "Marie", "01/2026", 100, "CDF", "Simple", "Litigieux", "2026-01-01", 100, 25, 75, "Partiel", 1)
    )

    assert record.payment_id == 10
    assert record.paid_amount == 25
    assert record.payment_status == "Partiel"
    assert record.visible_values[-1] == "Signé"
    assert record.to_metadata()["nom"] == "KABONGO"
    assert record.to_metadata()["est_signe"] is True


def test_dashboard_metrics_are_computed_from_typed_records():
    records = [
        SubscriptionRecord.from_row((1, 1, "A", "B", "01/2026", 100, "CDF", "Simple", "En règle")),
        SubscriptionRecord.from_row((2, 2, "C", "D", "01/2026", 50, "CDF", "Simple", "En attente")),
    ]

    metrics = calculate_dashboard_metrics(records)

    assert metrics.total_amount == 150
    assert metrics.average_amount == 75
    assert metrics.maximum_amount == 100
    assert metrics.busiest_month == "01/2026"
    assert metrics.busiest_month_count == 2
