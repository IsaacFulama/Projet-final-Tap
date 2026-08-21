from types import SimpleNamespace

from tap.core.admin_insights import build_admin_insights


def test_admin_insights_identifies_collection_and_priorities():
    result = build_admin_insights([
        SimpleNamespace(total_amount="100", paid_amount="60", payment_status="Litigieux", is_signed=False),
        SimpleNamespace(total_amount="50", paid_amount="50", payment_status="Complet", is_signed=True),
    ])
    assert result["collection_rate"] == 110 / 150 * 100
    assert result["remaining"] == 40
    assert result["overdue"] == 1
    assert result["unsigned"] == 1
    assert result["recommendations"]
    assert result["health"] == "surveillance"
