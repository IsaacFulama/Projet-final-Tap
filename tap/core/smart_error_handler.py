"""
Module de gestion intelligente des erreurs avec auto-correction.

Ce module fournit des fonctionnalités pour:
- Détecter automatiquement les erreurs courantes
- Proposer des corrections automatiques
- Adapter le système aux besoins de l'utilisateur
- Réduire le besoin d'intervention manuelle
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class SmartErrorHandler:
    """Gestionnaire intelligent des erreurs avec auto-correction."""
    
    def __init__(self):
        self.error_patterns = self._init_error_patterns()
        self.auto_corrections = self._init_auto_corrections()
        self.user_preferences = {}
        self.error_history = []
    
    def _init_error_patterns(self) -> Dict[str, Dict]:
        """Initialise les patterns d'erreurs connus."""
        return {
            "database_connection": {
                "patterns": [
                    r"Can't connect to MySQL server",
                    r"Access denied for user",
                    r"Unknown database",
                    r"Connection refused",
                ],
                "severity": "critical",
                "auto_fix": True,
                "suggestions": [
                    "Vérifier que le serveur MySQL est démarré",
                    "Vérifier les identifiants de connexion dans config.json",
                    "Vérifier que la base de données existe",
                    "Redémarrer le service MySQL si nécessaire",
                ]
            },
            "invalid_phone": {
                "patterns": [
                    r"numéro.*invalide",
                    r"phone.*format",
                    r"téléphone.*incorrect",
                ],
                "severity": "warning",
                "auto_fix": True,
                "suggestions": [
                    "Le numéro doit contenir entre 9 et 15 chiffres",
                    "Incluez le code pays (ex: +243 pour la RDC)",
                    "Évitez les espaces et caractères spéciaux",
                ]
            },
            "invalid_amount": {
                "patterns": [
                    r"montant.*invalide",
                    r"amount.*invalid",
                    r"valeur.*numérique",
                ],
                "severity": "warning",
                "auto_fix": True,
                "suggestions": [
                    "Le montant doit être un nombre positif",
                    "Utilisez le point comme séparateur décimal (ex: 1000.50)",
                    "Vérifiez que le montant n'est pas négatif",
                ]
            },
            "duplicate_entry": {
                "patterns": [
                    r"Duplicate entry",
                    r"déjà existe",
                    r"already exists",
                ],
                "severity": "warning",
                "auto_fix": True,
                "suggestions": [
                    "Cette souscription existe déjà pour ce mois",
                    "Vérifiez si le locataire a déjà un paiement ce mois-ci",
                    "Modifiez l'enregistrement existant au lieu d'en créer un nouveau",
                ]
            },
            "missing_field": {
                "patterns": [
                    r"champ.*obligatoire",
                    r"required.*field",
                    r"cannot be null",
                ],
                "severity": "error",
                "auto_fix": False,
                "suggestions": [
                    "Remplissez tous les champs obligatoires",
                    "Les champs marqués d'un * sont obligatoires",
                    "Vérifiez que vous n'avez pas oublié de saisir une information",
                ]
            },
            "file_permission": {
                "patterns": [
                    r"Permission denied",
                    r"accès refusé",
                    r"cannot write",
                ],
                "severity": "error",
                "auto_fix": True,
                "suggestions": [
                    "Vérifiez les permissions du dossier",
                    "Exécutez l'application en tant qu'administrateur",
                    "Assurez-vous que le dossier n'est pas en lecture seule",
                ]
            },
            "network_error": {
                "patterns": [
                    r"timeout",
                    r"network.*unreachable",
                    r"connection.*timeout",
                ],
                "severity": "warning",
                "auto_fix": True,
                "suggestions": [
                    "Vérifiez votre connexion internet",
                    "L'application va réessayer automatiquement",
                    "Certains fonctionnalités seront limitées hors ligne",
                ]
            }
        }
    
    def _init_auto_corrections(self) -> Dict[str, callable]:
        """Initialise les fonctions d'auto-correction."""
        return {
            "normalize_phone": self._normalize_phone,
            "normalize_amount": self._normalize_amount,
            "fill_defaults": self._fill_defaults,
            "retry_connection": self._retry_database_connection,
        }
    
    def analyze_error(self, error_message: str) -> Dict[str, Any]:
        """
        Analyse une erreur et propose des solutions.
        
        Returns:
            Dict avec: error_type, severity, suggestions, auto_fix_available
        """
        error_lower = error_message.lower()
        
        for error_type, config in self.error_patterns.items():
            for pattern in config["patterns"]:
                if re.search(pattern, error_lower, re.IGNORECASE):
                    result = {
                        "error_type": error_type,
                        "severity": config["severity"],
                        "suggestions": config["suggestions"],
                        "auto_fix_available": config["auto_fix"],
                        "detected_at": datetime.now().isoformat(),
                    }
                    
                    # Enregistrer dans l'historique
                    self.error_history.append(result)
                    
                    logger.info(f"Erreur détectée: {error_type} - Auto-correction: {config['auto_fix']}")
                    return result
        
        # Erreur inconnue
        return {
            "error_type": "unknown",
            "severity": "error",
            "suggestions": [
                "Erreur inconnue - Contactez le support technique",
                "Sauvegardez votre travail et redémarrez l'application",
                "Vérifiez les logs dans le dossier error_reports",
            ],
            "auto_fix_available": False,
            "detected_at": datetime.now().isoformat(),
        }
    
    def attempt_auto_fix(self, error_type: str, context: Dict = None) -> Tuple[bool, str]:
        """
        Tente de corriger automatiquement l'erreur.
        
        Returns:
            (success, message)
        """
        context = context or {}
        
        if error_type == "invalid_phone" and "phone" in context:
            return self._normalize_phone(context["phone"])
        
        elif error_type == "invalid_amount" and "amount" in context:
            return self._normalize_amount(context["amount"])
        
        elif error_type == "database_connection":
            return self._retry_database_connection()
        
        elif error_type == "missing_field":
            return self._fill_defaults(context)
        
        return False, "Aucune auto-correction disponible pour ce type d'erreur"
    
    def _normalize_phone(self, phone: str) -> Tuple[bool, str]:
        """Normalise un numéro de téléphone."""
        try:
            # Supprimer tous les caractères non numériques sauf le +
            cleaned = re.sub(r'[^\d+]', '', phone)
            
            # Ajouter le code pays si absent
            if not cleaned.startswith('+'):
                if len(cleaned) == 9:  # Format gabonais probable
                    cleaned = '+243' + cleaned
                elif len(cleaned) == 10 and cleaned.startswith('0'):
                    cleaned = '+243' + cleaned[1:]
            
            # Validation basique
            if len(cleaned) >= 10 and len(cleaned) <= 15:
                return True, f"Numéro normalisé: {cleaned}"
            
            return False, "Format de numéro invalide après normalisation"
        
        except Exception as e:
            return False, f"Erreur lors de la normalisation: {e}"
    
    def _normalize_amount(self, amount: str) -> Tuple[bool, str]:
        """Normalise un montant."""
        try:
            # Remplacer la virgule par un point
            cleaned = str(amount).replace(',', '.')
            
            # Convertir en nombre
            value = float(cleaned)
            
            if value < 0:
                return False, "Le montant ne peut pas être négatif"
            
            return True, f"Montant normalisé: {value:.2f}"
        
        except ValueError:
            return False, "Format de montant invalide"
    
    def _fill_defaults(self, context: Dict) -> Tuple[bool, str]:
        """Remplit les valeurs par défaut pour les champs manquants."""
        defaults = {
            "montant": "0.00",
            "devise": "XAF",
            "statut": "En attente",
            "statut_souscription": "Simple",
        }
        
        filled = []
        for field, default_value in defaults.items():
            if field in context and not context[field]:
                context[field] = default_value
                filled.append(field)
        
        if filled:
            return True, f"Champs remplis avec valeurs par défaut: {', '.join(filled)}"
        
        return False, "Aucun champ à remplir"
    
    def _retry_database_connection(self) -> Tuple[bool, str]:
        """Tente de reconnecter à la base de données."""
        try:
            from tap.infrastructure.database.connection import obtenir_connexion
            conn = obtenir_connexion()
            
            if conn and conn.is_connected():
                return True, "Connexion à la base de données rétablie"
            
            return False, "Impossible de se connecter à la base de données"
        
        except Exception as e:
            return False, f"Erreur de reconnexion: {e}"
    
    def get_tooltip_suggestion(self, field_name: str, current_value: str = "") -> str:
        """
        Retourne une suggestion contextuelle pour un champ.
        
        Args:
            field_name: Nom du champ
            current_value: Valeur actuelle du champ
        
        Returns:
            Message de suggestion
        """
        tooltips = {
            "nom": "Entrez le nom de famille du locataire",
            "prenom": "Entrez le prénom du locataire",
            "telephone": "Format: +243XX XX XX XX (code pays obligatoire)",
            "montant": "Entrez le montant en chiffres (ex: 50000)",
            "devise": "XAF (Francs CFA) ou USD (Dollars US)",
            "mois": "Format automatique basé sur la date actuelle",
            "statut": "En attente, En règle, ou Litigieux",
            "statut_souscription": "Simple ou Spécial",
        }
        
        base_tooltip = tooltips.get(field_name, "Champ de saisie")
        
        # Ajouter des suggestions basées sur la valeur actuelle
        if field_name == "telephone" and current_value:
            if not current_value.startswith('+'):
                base_tooltip += " | Suggestion: Ajoutez le code pays (+243)"
            elif len(current_value) < 10:
                base_tooltip += " | Suggestion: Numéro trop court"
        
        elif field_name == "montant" and current_value:
            try:
                if ',' in current_value:
                    base_tooltip += " | Suggestion: Utilisez un point (.) au lieu de la virgule"
            except:
                pass
        
        return base_tooltip
    
    def get_common_errors(self) -> List[Dict]:
        """Retourne les erreurs les plus courantes avec solutions."""
        common_errors = [
            {
                "error": "Connexion base de données échouée",
                "solution": "Vérifiez que MySQL est démarré et que config.json est correct",
                "auto_fix": True,
            },
            {
                "error": "Numéro de téléphone invalide",
                "solution": "Utilisez le format +243XX XX XX XX avec code pays",
                "auto_fix": True,
            },
            {
                "error": "Souscription déjà existante",
                "solution": "Modifiez l'enregistrement existant au lieu d'en créer un nouveau",
                "auto_fix": False,
            },
            {
                "error": "Montant invalide",
                "solution": "Entrez un nombre positif (ex: 50000.50)",
                "auto_fix": True,
            },
        ]
        
        return common_errors
    
    def learn_from_error(self, error_type: str, user_choice: str):
        """
        Apprend du choix de l'utilisateur pour améliorer les suggestions futures.
        
        Args:
            error_type: Type d'erreur
            user_choice: Choix de l'utilisateur (accept_fix, reject_fix, etc.)
        """
        if error_type not in self.user_preferences:
            self.user_preferences[error_type] = {}
        
        self.user_preferences[error_type]["last_choice"] = user_choice
        self.user_preferences[error_type]["timestamp"] = datetime.now().isoformat()
        
        logger.info(f"Préférence utilisateur enregistrée pour {error_type}: {user_choice}")


# Instance globale du gestionnaire d'erreurs
smart_error_handler = SmartErrorHandler()


def handle_error_with_suggestions(error: Exception, context: Dict = None) -> Dict:
    """
    Fonction utilitaire pour gérer une erreur avec suggestions intelligentes.
    
    Args:
        error: Exception levée
        context: Contexte additionnel (données du formulaire, etc.)
    
    Returns:
        Dict avec suggestions et possibilité d'auto-correction
    """
    error_message = str(error)
    analysis = smart_error_handler.analyze_error(error_message)
    
    if analysis["auto_fix_available"]:
        success, message = smart_error_handler.attempt_auto_fix(
            analysis["error_type"],
            context or {}
        )
        analysis["auto_fix_result"] = {
            "success": success,
            "message": message
        }
    
    return analysis
