"""
Module de rapport d'erreurs et correction automatique de bugs.
Ce système ne touche PAS à la base de données, il se contente de logger et rapporter les erreurs.
"""

import logging
import traceback
import json
from datetime import datetime
from typing import Optional, Dict, Any
import os

# Configuration du logging
ERROR_LOG_FILE = 'error_reports.log'
ERROR_REPORTS_DIR = 'error_reports'


class ErrorReporter:
    """Classe pour gérer les rapports d'erreurs sans toucher à la base de données."""
    
    def __init__(self):
        self.logger = self._setup_logger()
        self._ensure_reports_dir()
    
    def _setup_logger(self) -> logging.Logger:
        """Configure le logger pour les rapports d'erreurs."""
        logger = logging.getLogger('error_reporter')
        logger.setLevel(logging.INFO)
        
        # Handler pour le fichier
        file_handler = logging.FileHandler(ERROR_LOG_FILE)
        file_handler.setLevel(logging.INFO)
        
        # Handler pour la console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _ensure_reports_dir(self):
        """S'assure que le répertoire des rapports existe."""
        if not os.path.exists(ERROR_REPORTS_DIR):
            os.makedirs(ERROR_REPORTS_DIR)
    
    def report_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Rapporte une erreur sans toucher à la base de données.
        
        Args:
            error: L'exception survenue
            context: Contexte additionnel (fonction, paramètres, etc.)
        
        Returns:
            str: ID du rapport d'erreur
        """
        error_id = f"ERR_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Préparer le rapport
        rapport = {
            'error_id': error_id,
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'context': context or {}
        }
        
        # Logger l'erreur
        self.logger.error(f"Erreur rapportée: {error_id} - {type(error).__name__}: {error}")
        if context:
            self.logger.error(f"Contexte: {context}")
        
        # Sauvegarder le rapport dans un fichier JSON
        report_file = os.path.join(ERROR_REPORTS_DIR, f"{error_id}.json")
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(rapport, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Rapport sauvegardé: {report_file}")
        except Exception as e:
            self.logger.error(f"Impossible de sauvegarder le rapport: {e}")
        
        return error_id
    
    def report_warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Rapporte un avertissement sans toucher à la base de données.
        
        Args:
            message: Le message d'avertissement
            context: Contexte additionnel
        
        Returns:
            str: ID du rapport d'avertissement
        """
        warning_id = f"WARN_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        rapport = {
            'warning_id': warning_id,
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'context': context or {}
        }
        
        # Logger l'avertissement
        self.logger.warning(f"Avertissement: {warning_id} - {message}")
        if context:
            self.logger.warning(f"Contexte: {context}")
        
        # Sauvegarder le rapport
        report_file = os.path.join(ERROR_REPORTS_DIR, f"{warning_id}.json")
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(rapport, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Rapport d'avertissement sauvegardé: {report_file}")
        except Exception as e:
            self.logger.error(f"Impossible de sauvegarder le rapport: {e}")
        
        return warning_id
    
    def get_recent_errors(self, limit: int = 10) -> list:
        """
        Récupère les erreurs récentes depuis les fichiers de rapport.
        
        Args:
            limit: Nombre maximum d'erreurs à retourner
        
        Returns:
            list: Liste des rapports d'erreurs récents
        """
        errors = []
        
        if not os.path.exists(ERROR_REPORTS_DIR):
            return errors
        
        try:
            # Lister les fichiers de rapport
            files = sorted(
                [f for f in os.listdir(ERROR_REPORTS_DIR) if f.endswith('.json')],
                reverse=True
            )
            
            # Lire les fichiers
            for filename in files[:limit]:
                file_path = os.path.join(ERROR_REPORTS_DIR, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        rapport = json.load(f)
                        errors.append(rapport)
                except Exception as e:
                    self.logger.error(f"Impossible de lire le rapport {filename}: {e}")
        
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des erreurs récentes: {e}")
        
        return errors
    
    def cleanup_old_reports(self, days: int = 30):
        """
        Nettoie les rapports d'erreurs plus anciens que le nombre de jours spécifié.
        
        Args:
            days: Nombre de jours après lesquels les rapports sont supprimés
        """
        if not os.path.exists(ERROR_REPORTS_DIR):
            return
        
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
            
            for filename in os.listdir(ERROR_REPORTS_DIR):
                file_path = os.path.join(ERROR_REPORTS_DIR, filename)
                file_mtime = os.path.getmtime(file_path)
                
                if file_mtime < cutoff_date:
                    try:
                        os.remove(file_path)
                        self.logger.info(f"Rapport supprimé: {filename}")
                    except Exception as e:
                        self.logger.error(f"Impossible de supprimer {filename}: {e}")
        
        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage des rapports: {e}")


# Instance globale du rapporteur d'erreurs
error_reporter = ErrorReporter()


def report_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Fonction utilitaire pour rapporter une erreur.
    
    Args:
        error: L'exception survenue
        context: Contexte additionnel
    
    Returns:
        str: ID du rapport d'erreur
    """
    return error_reporter.report_error(error, context)


def report_warning(message: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Fonction utilitaire pour rapporter un avertissement.
    
    Args:
        message: Le message d'avertissement
        context: Contexte additionnel
    
    Returns:
        str: ID du rapport d'avertissement
    """
    return error_reporter.report_warning(message, context)


# Décorateur pour capturer les erreurs automatiquement
def capture_errors(context: Optional[Dict[str, Any]] = None):
    """
    Décorateur pour capturer automatiquement les erreurs dans les fonctions.
    
    Args:
        context: Contexte additionnel à inclure dans le rapport
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Préparer le contexte
                func_context = {
                    'function': func.__name__,
                    'module': func.__module__,
                    'args': str(args),
                    'kwargs': str(kwargs)
                }
                if context:
                    func_context.update(context)
                
                # Rapporter l'erreur
                report_error(e, func_context)
                
                # Relever l'erreur pour que le programme continue normalement
                raise
        return wrapper
    return decorator


if __name__ == "__main__":
    # Test du système de rapport
    print("Test du système de rapport d'erreurs...")
    
    # Test d'erreur
    try:
        raise ValueError("Erreur de test")
    except Exception as e:
        error_id = report_error(e, {'test': True})
        print(f"Erreur rapportée: {error_id}")
    
    # Test d'avertissement
    warning_id = report_warning("Avertissement de test", {'test': True})
    print(f"Avertissement rapporté: {warning_id}")
    
    # Test des erreurs récentes
    recent_errors = error_reporter.get_recent_errors(5)
    print(f"Erreurs récentes: {len(recent_errors)}")
    
    print("Test terminé.")
