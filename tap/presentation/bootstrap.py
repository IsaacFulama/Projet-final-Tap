"""
Module de démarrage de l'application TAP Gestion des Loyers.

Ce module gère l'initialisation et le lancement de l'application,
incluant l'authentification et la gestion des erreurs de démarrage.
"""

import logging
import sys

import customtkinter as ctk

from tap.core.error_reporter import report_error
from tap.presentation.dialogs.login import LoginDialog
from tap.presentation.views.main_window import AppGestionLoyers

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration de l'interface
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def launch_app() -> None:
    """
    Lance l'application TAP Gestion des Loyers.
    
    Cette fonction gère le flux complet de l'application :
    1. Affiche le dialogue de connexion
    2. Si l'authentification réussit, lance l'application principale
    3. Gère les erreurs de manière élégante
    """
    try:
        logger.info("Démarrage de l'application TAP Gestion des Loyers")
        
        # Créer et afficher le dialogue de connexion
        login_dialog = LoginDialog(None)
        login_dialog.mainloop()

        # Si l'authentification a réussi, lancer l'application principale
        if login_dialog.authenticated:
            try:
                login_dialog.destroy()
                logger.info("Authentification réussie, lancement de l'application principale")
                
                app = AppGestionLoyers()
                app.mainloop()
                
            except Exception as e:
                logger.error(f"Erreur lors du lancement de l'application principale: {e}")
                report_error(e, {'context': 'launch_main_app'})
                _show_startup_error(
                    "Erreur de démarrage",
                    "Une erreur est survenue lors du lancement de l'application. "
                    "Veuillez consulter les logs pour plus de détails."
                )
        else:
            logger.info("Authentification annulée ou échouée")
            
    except KeyboardInterrupt:
        logger.info("Application interrompue par l'utilisateur")
        sys.exit(0)
        
    except Exception as e:
        logger.critical(f"Erreur critique au démarrage: {e}")
        report_error(e, {'context': 'app_startup'})
        _show_startup_error(
            "Erreur critique",
            "Une erreur critique est survenue au démarrage de l'application. "
            "Veuillez contacter l'administrateur système."
        )
        sys.exit(1)


def _show_startup_error(title: str, message: str) -> None:
    """
    Affiche une boîte de dialogue d'erreur au démarrage.
    
    Args:
        title: Titre de l'erreur
        message: Message d'erreur détaillé
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
        
        # Créer une fenêtre racine cachée
        root = tk.Tk()
        root.withdraw()
        
        # Afficher l'erreur
        messagebox.showerror(title, message)
        
        root.destroy()
    except Exception:
        # Si tkinter n'est pas disponible, afficher dans la console
        print(f"ERREUR: {title}")
        print(f"MESSAGE: {message}")


if __name__ == "__main__":
    launch_app()
