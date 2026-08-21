"""
Module de démarrage de l'application TAP Gestion des Loyers.

Ce module gère l'initialisation et le lancement de l'application,
incluant l'authentification et la gestion des erreurs de démarrage.
"""

import logging
import sys

import customtkinter as ctk

from tap.config.responsive import apply_responsive_scaling
from tap.core.error_reporter import report_error
from tap.presentation.dialogs.login import LoginDialog
from tap.presentation.views.main_window import AppGestionLoyers
from tap.core.startup_manager import ensure_startup_ready

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


def _cancel_pending_after_callbacks(widget) -> None:
    """Annule les callbacks Tk encore attaches avant destruction d'une fenetre."""
    try:
        callback_ids = widget.tk.call("after", "info")
    except Exception:
        return
    if isinstance(callback_ids, str):
        callback_ids = (callback_ids,)
    for callback_id in callback_ids:
        try:
            widget.after_cancel(callback_id)
        except Exception:
            pass

# Configuration de l'interface
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")
apply_responsive_scaling()


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

        startup = ensure_startup_ready()
        if not startup["ok"]:
            _show_startup_error(
                "Base de données indisponible",
                startup["message"] + "\n\n" + "\n".join(
                    f"• {action}" for action in startup.get("actions", [])
                ),
            )
            return
        
        # Créer et afficher le dialogue de connexion
        login_dialog = LoginDialog(None)
        login_dialog.mainloop()

        # Si l'authentification a réussi, lancer l'application principale
        if login_dialog.authenticated:
            try:
                _cancel_pending_after_callbacks(login_dialog)
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
