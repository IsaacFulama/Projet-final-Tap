"""
Module de suggestions d'erreurs intelligentes et contextuelles.

Ce module fournit:
- Suggestions d'erreurs contextuelles
- Solutions automatiques proposées
- Apprentissage des erreurs fréquentes
- Interface utilisateur pour les suggestions
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from tap.core.smart_error_handler import smart_error_handler

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Niveaux de sévérité des erreurs."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SmartErrorSuggestion:
    """Suggestion d'erreur intelligente."""
    
    def __init__(
        self,
        error_type: str,
        message: str,
        severity: ErrorSeverity,
        auto_fix_available: bool,
        suggestions: List[str],
        steps: List[str] = None
    ):
        self.error_type = error_type
        self.message = message
        self.severity = severity
        self.auto_fix_available = auto_fix_available
        self.suggestions = suggestions
        self.steps = steps or []
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "severity": self.severity.value,
            "auto_fix_available": self.auto_fix_available,
            "suggestions": self.suggestions,
            "steps": self.steps,
            "timestamp": self.timestamp.isoformat(),
        }


class SmartErrorSuggestionEngine:
    """Moteur de suggestions d'erreurs intelligentes."""
    
    def __init__(self):
        self.error_suggestions = self._init_error_suggestions()
        self.user_feedback = {}
        self.suggestion_history = []
    
    def _init_error_suggestions(self) -> Dict[str, SmartErrorSuggestion]:
        """Initialise les suggestions d'erreurs."""
        return {
            "database_connection_failed": SmartErrorSuggestion(
                error_type="database_connection_failed",
                message="Impossible de se connecter à la base de données",
                severity=ErrorSeverity.CRITICAL,
                auto_fix_available=True,
                suggestions=[
                    "Vérifiez que le serveur MySQL est démarré",
                    "Vérifiez les identifiants dans config.json",
                    "Assurez-vous que la base de données existe",
                ],
                steps=[
                    "1. Ouvrez config.json",
                    "2. Vérifiez les paramètres de connexion",
                    "3. Démarrez le service MySQL si nécessaire",
                    "4. Cliquez sur 'Réessayer automatiquement'",
                ]
            ),
            "invalid_phone_format": SmartErrorSuggestion(
                error_type="invalid_phone_format",
                message="Format de numéro de téléphone invalide",
                severity=ErrorSeverity.WARNING,
                auto_fix_available=True,
                suggestions=[
                    "Le numéro doit commencer par le code pays (+)",
                    "Format attendu: +243XX XX XX XX",
                    "L'application peut corriger automatiquement ce format",
                ],
                steps=[
                    "1. Ajoutez le code pays (+243 pour la RDC)",
                    "2. Supprimez les espaces et tirets",
                    "3. Cliquez sur 'Corriger automatiquement'",
                ]
            ),
            "invalid_amount": SmartErrorSuggestion(
                error_type="invalid_amount",
                message="Format de montant invalide",
                severity=ErrorSeverity.WARNING,
                auto_fix_available=True,
                suggestions=[
                    "Utilisez le point (.) comme séparateur décimal",
                    "Le montant doit être positif",
                    "L'application peut convertir automatiquement",
                ],
                steps=[
                    "1. Remplacez la virgule par un point",
                    "2. Vérifiez que le montant est positif",
                    "3. Cliquez sur 'Corriger automatiquement'",
                ]
            ),
            "duplicate_entry": SmartErrorSuggestion(
                error_type="duplicate_entry",
                message="Cette souscription existe déjà",
                severity=ErrorSeverity.WARNING,
                auto_fix_available=False,
                suggestions=[
                    "Modifiez l'enregistrement existant au lieu d'en créer un nouveau",
                    "Vérifiez si le locataire a déjà un paiement ce mois-ci",
                    "Utilisez la fonction de recherche pour trouver l'enregistrement existant",
                ],
                steps=[
                    "1. Recherchez le locataire dans la liste",
                    "2. Cliquez sur 'Modifier' sur l'enregistrement existant",
                    "3. Mettez à jour les informations nécessaires",
                ]
            ),
            "missing_required_field": SmartErrorSuggestion(
                error_type="missing_required_field",
                message="Champ obligatoire manquant",
                severity=ErrorSeverity.ERROR,
                auto_fix_available=True,
                suggestions=[
                    "Les champs marqués d'un * sont obligatoires",
                    "L'application peut remplir certaines valeurs par défaut",
                    "Vérifiez que vous n'avez pas oublié une information",
                ],
                steps=[
                    "1. Repérez le champ en rouge",
                    "2. Remplissez le champ avec une valeur valide",
                    "3. Cliquez sur 'Remplir automatiquement' si disponible",
                ]
            ),
            "file_permission_denied": SmartErrorSuggestion(
                error_type="file_permission_denied",
                message="Permission d'accès refusée",
                severity=ErrorSeverity.ERROR,
                auto_fix_available=True,
                suggestions=[
                    "Exécutez l'application en tant qu'administrateur",
                    "Vérifiez les permissions du dossier",
                    "Assurez-vous que le dossier n'est pas en lecture seule",
                ],
                steps=[
                    "1. Faites un clic droit sur l'application",
                    "2. Sélectionnez 'Exécuter en tant qu'administrateur'",
                    "3. Acceptez la demande de l'UAC",
                ]
            ),
            "network_timeout": SmartErrorSuggestion(
                error_type="network_timeout",
                message="Délai d'attente réseau dépassé",
                severity=ErrorSeverity.WARNING,
                auto_fix_available=True,
                suggestions=[
                    "Vérifiez votre connexion internet",
                    "L'application va réessayer automatiquement",
                    "Certaines fonctionnalités seront limitées hors ligne",
                ],
                steps=[
                    "1. Vérifiez votre connexion internet",
                    "2. Attendez que la connexion soit rétablie",
                    "3. L'application réessaiera automatiquement",
                ]
            ),
            "data_corruption_detected": SmartErrorSuggestion(
                error_type="data_corruption_detected",
                message="Données corrompues détectées",
                severity=ErrorSeverity.CRITICAL,
                auto_fix_available=True,
                suggestions=[
                    "L'application peut tenter de réparer les données automatiquement",
                    "Une sauvegarde sera créée avant réparation",
                    "Contactez le support si le problème persiste",
                ],
                steps=[
                    "1. Cliquez sur 'Réparer automatiquement'",
                    "2. Attendez la fin de la réparation",
                    "3. Vérifiez que les données sont correctes",
                ]
            ),
        }
    
    def get_suggestion_for_error(self, error_message: str) -> Optional[SmartErrorSuggestion]:
        """
        Retourne une suggestion pour une erreur donnée.
        
        Args:
            error_message: Message d'erreur
        
        Returns:
            SmartErrorSuggestion ou None
        """
        analysis = smart_error_handler.analyze_error(error_message)
        
        if analysis["error_type"] in self.error_suggestions:
            suggestion = self.error_suggestions[analysis["error_type"]]
            self.suggestion_history.append({
                "error_message": error_message,
                "suggestion": suggestion.to_dict(),
                "timestamp": datetime.now().isoformat(),
            })
            return suggestion
        
        # Suggestion générique pour erreur inconnue
        return SmartErrorSuggestion(
            error_type="unknown_error",
            message="Erreur inconnue détectée",
            severity=ErrorSeverity.ERROR,
            auto_fix_available=False,
            suggestions=[
                "Sauvegardez votre travail et redémarrez l'application",
                "Vérifiez les logs dans le dossier error_reports",
                "Contactez le support technique si le problème persiste",
            ],
            steps=[
                "1. Sauvegardez votre travail actuel",
                "2. Redémarrez l'application",
                "3. Si le problème persiste, consultez les logs",
            ]
        )
    
    def get_common_errors_with_solutions(self) -> List[Dict]:
        """Retourne les erreurs courantes avec leurs solutions."""
        common_errors = []
        
        for error_type, suggestion in self.error_suggestions.items():
            if suggestion.severity in [ErrorSeverity.WARNING, ErrorSeverity.ERROR]:
                common_errors.append({
                    "error_type": error_type,
                    "message": suggestion.message,
                    "severity": suggestion.severity.value,
                    "auto_fix_available": suggestion.auto_fix_available,
                    "quick_solution": suggestion.suggestions[0] if suggestion.suggestions else "",
                })
        
        return common_errors
    
    def record_user_feedback(self, error_type: str, was_helpful: bool, comment: str = ""):
        """
        Enregistre le feedback utilisateur sur une suggestion.
        
        Args:
            error_type: Type d'erreur
            was_helpful: Si la suggestion était utile
            comment: Commentaire optionnel
        """
        if error_type not in self.user_feedback:
            self.user_feedback[error_type] = []
        
        self.user_feedback[error_type].append({
            "was_helpful": was_helpful,
            "comment": comment,
            "timestamp": datetime.now().isoformat(),
        })
        
        logger.info(f"Feedback enregistré pour {error_type}: utile={was_helpful}")
    
    def get_suggestion_statistics(self) -> Dict:
        """Retourne les statistiques d'utilisation des suggestions."""
        stats = {
            "total_suggestions_given": len(self.suggestion_history),
            "total_feedback_received": sum(len(feedback) for feedback in self.user_feedback.values()),
            "most_helpful_suggestions": [],
            "least_helpful_suggestions": [],
        }
        
        # Calculer les suggestions les plus/moins utiles
        helpfulness = {}
        for error_type, feedback_list in self.user_feedback.items():
            if feedback_list:
                helpful_count = sum(1 for f in feedback_list if f["was_helpful"])
                helpfulness[error_type] = helpful_count / len(feedback_list)
        
        if helpfulness:
            sorted_helpfulness = sorted(helpfulness.items(), key=lambda x: x[1], reverse=True)
            stats["most_helpful_suggestions"] = [
                {"error_type": et, "helpfulness_rate": hr}
                for et, hr in sorted_helpfulness[:3]
            ]
            stats["least_helpful_suggestions"] = [
                {"error_type": et, "helpfulness_rate": hr}
                for et, hr in sorted_helpfulness[-3:]
            ]
        
        return stats
    
    def get_contextual_help(self, context: Dict) -> List[str]:
        """
        Retourne de l'aide contextuelle basée sur la situation actuelle.
        
        Args:
            context: Contexte de l'application (page actuelle, action, etc.)
        
        Returns:
            Liste de suggestions contextuelles
        """
        suggestions = []
        
        current_page = context.get("current_page", "")
        current_action = context.get("current_action", "")
        
        # Suggestions basées sur la page
        if current_page == "formulaire":
            suggestions.extend([
                "💡 Astuce: Les champs en rouge sont invalides",
                "💡 Astuce: Utilisez Tab pour passer au champ suivant",
                "💡 Astuce: Les tooltips apparaissent au survol de la souris",
            ])
        
        elif current_page == "tableau":
            suggestions.extend([
                "💡 Astuce: Cliquez sur les en-têtes pour trier",
                "💡 Astuce: Utilisez Ctrl+F pour rechercher",
                "💡 Astuce: Double-cliquez pour modifier une ligne",
            ])
        
        # Suggestions basées sur l'action
        if current_action == "ajout":
            suggestions.append("💡 Astuce: Remplissez les champs obligatoires (*)")
        
        elif current_action == "suppression":
            suggestions.append("⚠️ Attention: Cette action est irréversible")
        
        return suggestions


# Instance globale du moteur de suggestions
smart_suggestion_engine = SmartErrorSuggestionEngine()


def get_smart_suggestion(error_message: str) -> Optional[SmartErrorSuggestion]:
    """
    Fonction utilitaire pour obtenir une suggestion intelligente.
    
    Args:
        error_message: Message d'erreur
    
    Returns:
        SmartErrorSuggestion ou None
    """
    return smart_suggestion_engine.get_suggestion_for_error(error_message)


def get_contextual_help(context: Dict) -> List[str]:
    """
    Fonction utilitaire pour obtenir de l'aide contextuelle.
    
    Args:
        context: Contexte de l'application
    
    Returns:
        Liste de suggestions contextuelles
    """
    return smart_suggestion_engine.get_contextual_help(context)
