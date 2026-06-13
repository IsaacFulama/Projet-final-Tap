import re
from datetime import date, datetime

from tap.config.theme import MONTH_ALIASES

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")


def parse_mois_saisie(value) -> date | None:
    """Convertit une saisie utilisateur en date MySQL."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    if not text:
        return None

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    match = re.match(r"^(\d{4})[-/](\d{1,2})$", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1)

    match = re.match(r"^(\d{1,2})[-/](\d{4})$", text)
    if match:
        return date(int(match.group(2)), int(match.group(1)), 1)

    parts = text.lower().split()
    year = next((int(part) for part in parts if part.isdigit() and len(part) == 4), None)
    month = next((MONTH_ALIASES[part] for part in parts if part in MONTH_ALIASES), None)
    if year and month:
        return date(year, month, 1)

    return None


def format_mois_affichage(value) -> str:
    """Affiche un mois au format MM/AAAA."""
    parsed = parse_mois_saisie(value)
    if parsed:
        return parsed.strftime("%m/%Y")
    return str(value)


def month_sort_key(value):
    parsed = parse_mois_saisie(value)
    if parsed:
        return parsed.year, parsed.month, parsed.isoformat()
    text = str(value).strip().lower()
    return 9999, 99, text
