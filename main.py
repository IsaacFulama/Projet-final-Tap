"""Point d'entrée de l'application TAP Gestion des Loyers."""

import sys
from datetime import date, datetime

from tap.presentation.bootstrap import launch_app
from tap.core.auto_status_updater import (
    executer_demo_cycle_mensuel,
    executer_mise_a_jour_automatique,
)
from tap.core.error_reporter import report_error
from tap.core.whatsapp_reports import send_monthly_pdf_reports
from tap.core.backup_manager import lancer_backup_en_arriere_plan
from tap.core.smart_error_handler import smart_error_handler
from tap.core.data_validator import data_validator
from tap.core.monthly_reports import generate_and_publish_monthly_report


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
        
        # Réparation automatique des données corrompues
        try:
            repair_report = data_validator.repair_database()
            if repair_report["repairs_made"] > 0:
                print(f"Réparation automatique: {repair_report['repairs_made']} corrections effectuées")
        except Exception as e:
            print(f"Erreur lors de la réparation automatique: {e}")
        
        # Envoyer les rapports PDF mensuels si configuré
        try:
            result = send_monthly_pdf_reports()
            if result.get("status") == "completed":
                print(f"Rapports PDF mensuels envoyés avec succès à {result.get('recipients_count')} destinataire(s)")
            elif result.get("status") == "no_internet":
                print("Pas de connexion internet - rapports PDF non envoyés")
            elif result.get("status") == "disabled":
                print("Envoi automatique des rapports PDF désactivé dans config.json")
            elif result.get("status") == "no_data":
                print("Aucune donnée disponible pour les rapports PDF ce mois-ci")
        except Exception as e:
            # Rapporter l'erreur sans arrêter l'application
            report_error(e, {'context': 'envoi_rapports_pdf_mensuels'})
            print(f"Erreur lors de l'envoi des rapports PDF mensuels: {e}")
        try:
            monthly_result = generate_and_publish_monthly_report()
            if monthly_result.get("status") == "completed":
                print("Rapport financier mensuel généré et diffusé selon la configuration")
        except Exception as e:
            report_error(e, {'context': 'rapport_financier_mensuel'})
            print(f"Erreur lors du rapport financier mensuel: {e}")
    except Exception as e:
        # Utiliser le gestionnaire d'erreurs intelligent
        error_analysis = smart_error_handler.analyze_error(str(e))
        print(f"Erreur analysée: {error_analysis['error_type']}")
        print(f"Suggestions: {'; '.join(error_analysis['suggestions'][:2])}")
        
        # Tenter l'auto-correction si disponible
        if error_analysis.get("auto_fix_available"):
            success, message = smart_error_handler.attempt_auto_fix(
                error_analysis["error_type"],
                {}
            )
            if success:
                print(f"Auto-correction réussie: {message}")
        
        # Rapporter l'erreur sans arrêter l'application
        report_error(e, {'context': 'mise_a_jour_statuts_automatique'})
        print(f"Erreur lors de la mise à jour automatique des statuts: {e}")
        
    # Lancement du backup silencieux en arrière-plan
    try:
        lancer_backup_en_arriere_plan()
    except Exception as e:
        print(f"Erreur au lancement du thread de backup: {e}")
    
    # Lancement de l'archivage silencieux en arrière-plan
    try:
        from tap.core.archiver import lancer_archivage_en_arriere_plan
        lancer_archivage_en_arriere_plan()
    except Exception as e:
        print(f"Erreur au lancement du thread d'archivage: {e}")
        
    # Lancer l'application
    launch_app()
