"""Point d'entrée de l'application TAP Gestion des Loyers."""

from tap.presentation.bootstrap import launch_app
from tap.core.auto_status_updater import executer_mise_a_jour_automatique
from tap.core.error_reporter import report_error

if __name__ == "__main__":
    try:
        # Exécuter la mise à jour automatique des statuts au démarrage
        executer_mise_a_jour_automatique()
    except Exception as e:
        # Rapporter l'erreur sans arrêter l'application
        report_error(e, {'context': 'mise_a_jour_statuts_automatique'})
        print(f"Erreur lors de la mise à jour automatique des statuts: {e}")
    
    # Lancer l'application
    launch_app()
