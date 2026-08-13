from datetime import date

from tap.core.date_utils import build_month_choices, format_month_choice, parse_mois_saisie


def test_build_month_choices_starts_at_2025():
    choices = build_month_choices(start_year=2025, years_ahead=1, reference_date=date(2026, 6, 15))

    assert choices[0].endswith("(2025-01-01)")
    assert choices[1].endswith("(2025-02-01)")
    assert choices[-1].endswith("(2027-12-01)")


def test_format_month_choice_uses_parseable_value():
    choice = format_month_choice(date(2026, 6, 1))

    assert "(2026-06-01)" in choice


def test_parse_month_choice_label():
    choice = format_month_choice(date(2025, 1, 1))

    assert parse_mois_saisie(choice) == date(2025, 1, 1)
