"""
Module de validation et réparation automatique des données.

Ce module fournit:
- Validation automatique des données avant insertion
- Réparation des données corrompues
- Détection des anomalies
- Nettoyage automatique de la base de données
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from tap.infrastructure.database import obtenir_connexion

logger = logging.getLogger(__name__)


class DataValidator:
    """Validateur et réparateur automatique de données."""
    
    def __init__(self, default_phone_country_code: str = "+243"):
        self.validation_rules = self._init_validation_rules()
        self.default_phone_country_code = self._normalize_country_code(default_phone_country_code)
        self.repair_stats = {
            "total_validated": 0,
            "total_repaired": 0,
            "total_errors": 0,
        }

    @staticmethod
    def _normalize_country_code(country_code: str) -> str:
        """Normalise un préfixe international et refuse une valeur invalide."""
        code = str(country_code or "").strip().replace(" ", "")
        if code.startswith("+") and code[1:].isdigit() and 2 <= len(code) <= 4:
            return code
        return "+243"
    
    def _init_validation_rules(self) -> Dict[str, Dict]:
        """Initialise les règles de validation."""
        return {
            "locataire": {
                "required_fields": ["nom", "prenom"],
                "field_validators": {
                    "nom": self._validate_name,
                    "prenom": self._validate_name,
                    "telephone": self._validate_phone,
                },
                "default_values": {
                    "telephone": None,
                }
            },
            "paiement": {
                "required_fields": ["locataire_id", "mois", "montant"],
                "field_validators": {
                    "montant": self._validate_amount,
                    "montant_total": self._validate_amount,
                    "montant_paye": self._validate_amount,
                    "reste_a_payer": self._validate_amount,
                    "mois": self._validate_date,
                    "devise": self._validate_devise,
                    "statut": self._validate_statut,
                    "statut_souscription": self._validate_statut_souscription,
                },
                "default_values": {
                    "devise": "XAF",
                    "statut": "En attente",
                    "statut_souscription": "Simple",
                    "statut_paiement": "En attente",
                    "montant_total": None,
                    "montant_paye": Decimal("0.00"),
                    "reste_a_payer": None,
                }
            }
        }
    
    def validate_locataire(self, data: Dict) -> Tuple[bool, Dict, List[str]]:
        """
        Valide les données d'un locataire.
        
        Returns:
            (is_valid, cleaned_data, errors)
        """
        return self._validate_data("locataire", data)
    
    def validate_paiement(self, data: Dict) -> Tuple[bool, Dict, List[str]]:
        """
        Valide les données d'un paiement.
        
        Returns:
            (is_valid, cleaned_data, errors)
        """
        return self._validate_data("paiement", data)
    
    def _validate_data(self, entity_type: str, data: Dict) -> Tuple[bool, Dict, List[str]]:
        """
        Valide les données selon le type d'entité.
        
        Returns:
            (is_valid, cleaned_data, errors)
        """
        rules = self.validation_rules.get(entity_type, {})
        cleaned_data = data.copy()
        errors = []
        
        # Vérifier les champs obligatoires
        for field in rules.get("required_fields", []):
            if field not in cleaned_data or not cleaned_data[field]:
                errors.append(f"Champ obligatoire manquant: {field}")
        
        # Appliquer les validateurs de champs
        field_validators = rules.get("field_validators", {})
        for field, validator in field_validators.items():
            if field in cleaned_data and cleaned_data[field]:
                is_valid, error_msg = validator(cleaned_data[field])
                if not is_valid:
                    errors.append(f"{field}: {error_msg}")
                else:
                    # Nettoyer la donnée
                    cleaned_data[field] = self._clean_field(field, cleaned_data[field])
        
        # Appliquer les valeurs par défaut
        default_values = rules.get("default_values", {})
        for field, default_value in default_values.items():
            if field not in cleaned_data or not cleaned_data[field]:
                cleaned_data[field] = default_value
        
        # Calculer les champs dérivés
        if entity_type == "paiement":
            cleaned_data = self._calculate_derived_fields(cleaned_data)
        
        self.repair_stats["total_validated"] += 1
        
        return len(errors) == 0, cleaned_data, errors
    
    def _calculate_derived_fields(self, data: Dict) -> Dict:
        """Calcule les champs dérivés pour un paiement."""
        try:
            montant = Decimal(str(data.get("montant", 0)))
            montant_total = Decimal(str(data.get("montant_total", montant)))
            montant_paye = Decimal(str(data.get("montant_paye", 0)))
            
            # Si montant_total n'est pas défini, utiliser montant
            if not data.get("montant_total"):
                data["montant_total"] = montant
            
            # Calculer reste_a_payer si non défini
            if not data.get("reste_a_payer"):
                data["reste_a_payer"] = montant_total - montant_paye
            
            # Déterminer le statut automatiquement
            if data.get("reste_a_payer", 0) <= 0:
                data["statut"] = "En règle"
                data["statut_paiement"] = "Complet"
            elif montant_paye > 0:
                data["statut"] = "En attente"
                data["statut_paiement"] = "Partiel"
            else:
                data["statut"] = "En attente"
                data["statut_paiement"] = "En attente"
        
        except (InvalidOperation, TypeError) as e:
            logger.error(f"Erreur lors du calcul des champs dérivés: {e}")
        
        return data
    
    def _clean_field(self, field_name: str, value: Any) -> Any:
        """Nettoie une valeur de champ."""
        if field_name in ["nom", "prenom"]:
            return str(value).strip().title()
        elif field_name == "telephone":
            return self._clean_phone(value)
        elif field_name in ["montant", "montant_total", "montant_paye", "reste_a_payer"]:
            return self._clean_amount(value)
        elif field_name == "devise":
            return str(value).upper().strip()
        
        return value
    
    def _clean_phone(self, value: str) -> str:
        """Nettoie un numéro de téléphone."""
        cleaned = str(value).replace(" ", "").replace("-", "").replace(".", "")
        
        # Ajouter le code pays si absent
        if not cleaned.startswith("+") and len(cleaned) == 9:
            cleaned = self.default_phone_country_code + cleaned
        
        return cleaned
    
    def _clean_amount(self, value: Any) -> Decimal:
        """Nettoie un montant."""
        try:
            if isinstance(value, (int, float, Decimal)):
                return Decimal(str(value))
            
            # Remplacer la virgule par un point
            cleaned = str(value).replace(",", ".")
            return Decimal(cleaned)
        
        except InvalidOperation:
            return Decimal("0.00")
    
    def _validate_name(self, value: str) -> Tuple[bool, str]:
        """Valide un nom."""
        if not value or len(str(value).strip()) < 2:
            return False, "Le nom doit contenir au moins 2 caractères"
        
        if len(str(value)) > 50:
            return False, "Le nom est trop long (max 50 caractères)"
        
        return True, ""
    
    def _validate_phone(self, value: str) -> Tuple[bool, str]:
        """Valide un numéro de téléphone."""
        if not value:
            return True, ""  # Téléphone optionnel
        
        cleaned = self._clean_phone(value)
        
        if not cleaned.startswith("+"):
            return False, "Le numéro doit commencer par le code pays (+)"
        
        if len(cleaned) < 10 or len(cleaned) > 15:
            return False, "Le numéro doit contenir entre 10 et 15 caractères"
        
        if not cleaned[1:].isdigit():
            return False, "Le numéro ne doit contenir que des chiffres après le +"
        
        return True, ""
    
    def _validate_amount(self, value: Any) -> Tuple[bool, str]:
        """Valide un montant."""
        try:
            amount = Decimal(str(value))
            
            if amount < 0:
                return False, "Le montant ne peut pas être négatif"
            
            if amount > 100000000:
                return False, "Le montant semble trop élevé"
            
            return True, ""
        
        except InvalidOperation:
            return False, "Le montant doit être un nombre valide"
    
    def _validate_date(self, value: Any) -> Tuple[bool, str]:
        """Valide une date."""
        if isinstance(value, date):
            return True, ""
        
        try:
            datetime.strptime(str(value), "%Y-%m-%d")
            return True, ""
        
        except ValueError:
            return False, "Format de date invalide (attendu: YYYY-MM-DD)"
    
    def _validate_devise(self, value: str) -> Tuple[bool, str]:
        """Valide une devise."""
        valid_devises = ["XAF", "USD", "EUR"]
        devise = str(value).upper().strip()
        
        if devise not in valid_devises:
            return False, f"Devise invalide (acceptées: {', '.join(valid_devises)})"
        
        return True, ""
    
    def _validate_statut(self, value: str) -> Tuple[bool, str]:
        """Valide un statut."""
        valid_statuts = ["En attente", "En règle", "Litigieux"]
        statut = str(value).strip()
        
        if statut not in valid_statuts:
            return False, f"Statut invalide (acceptés: {', '.join(valid_statuts)})"
        
        return True, ""
    
    def _validate_statut_souscription(self, value: str) -> Tuple[bool, str]:
        """Valide un statut de souscription."""
        valid_statuts = ["Simple", "Spécial"]
        statut = str(value).strip()
        
        if statut not in valid_statuts:
            return False, f"Statut de souscription invalide (acceptés: {', '.join(valid_statuts)})"
        
        return True, ""
    
    def repair_database(self) -> Dict[str, Any]:
        """
        Répare automatiquement les données corrompues dans la base de données.
        
        Returns:
            Rapport de réparation
        """
        conn = None
        cursor = None
        repair_report = {
            "repairs_made": 0,
            "errors_found": 0,
            "details": [],
            "timestamp": datetime.now().isoformat(),
        }
        
        try:
            conn = obtenir_connexion()
            if not conn or not conn.is_connected():
                repair_report["errors_found"] += 1
                repair_report["details"].append("Impossible de se connecter à la base de données")
                return repair_report
            
            cursor = conn.cursor()
            
            # Réparer les téléphones mal formatés
            repair_report["details"].append("Réparation des téléphones mal formatés...")
            cursor.execute("SELECT id, telephone FROM locataires WHERE telephone IS NOT NULL")
            for row in cursor.fetchall():
                locataire_id, phone = row
                cleaned_phone = self._clean_phone(phone)
                if cleaned_phone != phone:
                    cursor.execute(
                        "UPDATE locataires SET telephone = %s WHERE id = %s",
                        (cleaned_phone, locataire_id)
                    )
                    repair_report["repairs_made"] += 1
                    repair_report["details"].append(f"Téléphone réparé pour locataire {locataire_id}")
            
            # Réparer les montants invalides
            repair_report["details"].append("Réparation des montants invalides...")
            cursor.execute("SELECT id, montant, montant_total, montant_paye FROM paiements")
            for row in cursor.fetchall():
                paiement_id, montant, montant_total, montant_paye = row
                
                # Réparer montant
                try:
                    cleaned_amount = self._clean_amount(montant)
                    if str(cleaned_amount) != str(montant):
                        cursor.execute(
                            "UPDATE paiements SET montant = %s WHERE id = %s",
                            (cleaned_amount, paiement_id)
                        )
                        repair_report["repairs_made"] += 1
                except (ArithmeticError, TypeError, ValueError):
                    repair_report["errors_found"] += 1
                
                # Recalculer les champs dérivés
                try:
                    total = Decimal(str(montant_total or montant))
                    paye = Decimal(str(montant_paye or 0))
                    reste = total - paye
                    
                    cursor.execute(
                        """UPDATE paiements 
                           SET montant_total = %s, reste_a_payer = %s 
                           WHERE id = %s""",
                        (total, reste, paiement_id)
                    )
                    
                    # Mettre à jour le statut
                    if reste <= 0:
                        cursor.execute(
                            "UPDATE paiements SET statut = 'En règle' WHERE id = %s",
                            (paiement_id,)
                        )
                    
                    repair_report["repairs_made"] += 1
                
                except Exception as e:
                    repair_report["errors_found"] += 1
                    repair_report["details"].append(f"Erreur réparation paiement {paiement_id}: {e}")
            
            conn.commit()
            self.repair_stats["total_repaired"] += repair_report["repairs_made"]
            
            logger.info(f"Réparation base de données terminée: {repair_report['repairs_made']} réparations")
            
        except Exception as e:
            repair_report["errors_found"] += 1
            repair_report["details"].append(f"Erreur générale: {e}")
            logger.error(f"Erreur lors de la réparation de la base de données: {e}")
            
            if conn:
                conn.rollback()
        
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
        
        return repair_report
    
    def get_repair_stats(self) -> Dict[str, int]:
        """Retourne les statistiques de réparation."""
        return self.repair_stats.copy()


# Instance globale du validateur
data_validator = DataValidator()
