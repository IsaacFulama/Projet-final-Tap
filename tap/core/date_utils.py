import re
from datetime import date, datetime

from tap.config.theme import MONTH_ALIASES

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
MONTH_NAMES_FR = {
    1: "Janvier",
    2: "Février",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Août",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Décembre",
}

# Premier mois autorisé pour le basculement manuel des souscripteurs Spécial.
SPECIAL_ROLLOVER_START = date(2025, 10, 1)


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

    match = re.search(r"\((\d{4}-\d{2}-\d{2})\)\s*$", text)
    if match:
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            pass

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


def month_name_fr(month: int) -> str:
    """Retourne le nom français du mois."""
    return MONTH_NAMES_FR.get(int(month), str(month))


def format_month_label(value) -> str:
    """Retourne un libellé mois/année lisible, en français."""
    parsed = parse_mois_saisie(value)
    if not parsed:
        return str(value)
    return f"{month_name_fr(parsed.month)} {parsed.year}"


def format_month_choice(value) -> str:
    """Retourne un libellé de choix mois/année lisible pour les combos."""
    parsed = parse_mois_saisie(value)
    if not parsed:
        return str(value)
    return f"{format_month_label(parsed)} ({parsed.strftime('%Y-%m-%d')})"


def build_month_choices(start_year: int = 2025, years_ahead: int = 5, reference_date: date | None = None) -> list[str]:
    """Construit la liste des mois disponibles à partir de janvier 2025."""
    reference = reference_date or date.today()
    first_year = max(2025, int(start_year))
    last_year = max(first_year, reference.year + max(0, int(years_ahead)))

    choices: list[str] = []
    for year in range(first_year, last_year + 1):
        for month in range(1, 13):
            choices.append(format_month_choice(date(year, month, 1)))
    return choices


def build_special_rollover_month_choices(
    years_ahead: int = 5,
    reference_date: date | None = None,
) -> list[str]:
    """Liste des mois proposés pour le basculement manuel Spécial (à partir de 10/2025)."""
    reference = reference_date or date.today()
    last_year = max(SPECIAL_ROLLOVER_START.year, reference.year + max(0, int(years_ahead)))

    choices: list[str] = []
    for year in range(SPECIAL_ROLLOVER_START.year, last_year + 1):
        first_month = SPECIAL_ROLLOVER_START.month if year == SPECIAL_ROLLOVER_START.year else 1
        for month in range(first_month, 13):
            choices.append(format_month_choice(date(year, month, 1)))
    return choices


def month_sort_key(value):
    parsed = parse_mois_saisie(value)
    if parsed:
        return parsed.year, parsed.month, parsed.isoformat()
    text = str(value).strip().lower()
    return 9999, 99, text
