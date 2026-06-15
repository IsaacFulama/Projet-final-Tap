"""Point d'entrée de l'application TAP Gestion des Loyers."""

import sys
from datetime import date, datetime

from tap.presentation.bootstrap import launch_app
from tap.core.auto_status_updater import (
    executer_demo_cycle_mensuel,
    executer_mise_a_jour_automatique,
)
from tap.core.error_reporter import report_error


def _parse_demo_date(argv: list[str]) -> date | None:
    if "--demo-date" not in argv:
        return None
    index = argv.index("--demo-date")
    if index + 1 >= len(argv):
        return None
    try:
        return datetime.fromisoformat(argv[index + 1]).date()
    except ValueError:
        return None


if __name__ == "__main__":
    try:
        if "--demo-cycle" in sys.argv:
            demo_date = _parse_demo_date(sys.argv)
            rapport = executer_demo_cycle_mensuel(demo_date)
            print(f"Démo mensuelle sur {rapport['date_demo']}")
            print(f"Créations mensuelles: {rapport['creations_speciales']}")
            print(f"Mises à jour litigieuses: {rapport['mis_a_jour']}")
            print(f"Paiements à suivre: {rapport['paiements_a_suivi']}")
            sys.exit(0)

        # Exécuter la mise à jour automatique des statuts au démarrage
        executer_mise_a_jour_automatique()
    except Exception as e:
        # Rapporter l'erreur sans arrêter l'application
        report_error(e, {'context': 'mise_a_jour_statuts_automatique'})
        print(f"Erreur lors de la mise à jour automatique des statuts: {e}")
    
    # Lancer l'application
    launch_app()
