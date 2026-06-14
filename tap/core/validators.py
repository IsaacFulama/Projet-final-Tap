"""
Module de validation des données avec règles strictes et cohérentes.

Ce module fournit des fonctions de validation robustes pour les différents
champs de l'application, en utilisant des expressions régulières et des
règles métier spécifiques.
"""

import re
from datetime import datetime
from typing import Optional, Pattern


class ValidationError(Exception):
    """Exception levée lorsqu'une validation échoue."""
    pass


class Validators:
    """Classe contenant des validateurs pour différents types de données."""
    
    # Patterns regex compilés pour la performance
    NAME_PATTERN: Pattern = re.compile(r"^[a-zA-ZÀ-ÿ\s\-']{2,50}$")
    PHONE_PATTERN: Pattern = re.compile(r"^\+?[\d\s\-\(\)]{7,20}$")
    EMAIL_PATTERN: Pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    
    @staticmethod
    def validate_name(value: str, field_name: str = "Nom") -> str:
        """
        Valide un nom ou prénom.
        
        Args:
            value: La valeur à valider
            field_name: Le nom du champ pour les messages d'erreur
            
        Returns:
            str: La valeur validée (trimée)
            
        Raises:
            ValidationError: Si la validation échoue
        """
        if not value or not value.strip():
            raise ValidationError(f"{field_name} est obligatoire")
        
        value = value.strip()
        
        if len(value) < 2:
            raise ValidationError(f"{field_name} doit contenir au moins 2 caractères")
        
        if len(value) > 50:
            raise ValidationError(f"{field_name} ne peut pas dépasser 50 caractères")
        
        if not Validators.NAME_PATTERN.match(value):
            raise ValidationError(
                f"{field_name} ne peut contenir que des lettres, espaces, tirets et apostrophes"
            )
        
        return value
    
    @staticmethod
    def validate_phone(value: str, field_name: str = "Téléphone") -> Optional[str]:
        """
        Valide un numéro de téléphone (optionnel).
        
        Args:
            value: La valeur à valider
            field_name: Le nom du champ pour les messages d'erreur
            
        Returns:
            Optional[str]: La valeur validée ou None si vide
            
        Raises:
            ValidationError: Si la validation échoue
        """
        if not value or not value.strip():
            return None
        
        value = value.strip()
        
        # Extraire uniquement les chiffres pour la vérification de longueur
        digits = re.sub(r'[^\d]', '', value)
        
        # Vérifier d'abord le format avant la longueur
        if not digits:
            raise ValidationError(
                f"{field_name} format invalide. Utilisez le format international (ex: +243 XXX XXX XXX)"
            )
        
        if len(digits) < 7:
            raise ValidationError(
                f"{field_name} doit contenir au moins 7 chiffres"
            )
        
        if len(digits) > 15:
            raise ValidationError(
                f"{field_name} ne peut pas dépasser 15 chiffres"
            )
        
        if not Validators.PHONE_PATTERN.match(value):
            raise ValidationError(
                f"{field_name} format invalide. Utilisez le format international (ex: +243 XXX XXX XXX)"
            )
        
        return value
    
    @staticmethod
    def validate_amount(value: str, field_name: str = "Montant") -> float:
        """
        Valide un montant monétaire.
        
        Args:
            value: La valeur à valider
            field_name: Le nom du champ pour les messages d'erreur
            
        Returns:
            float: Le montant validé comme float
            
        Raises:
            ValidationError: Si la validation échoue
        """
        if not value or not value.strip():
            raise ValidationError(f"{field_name} est obligatoire")
        
        value = value.strip()
        
        # Gérer différents formats de nombres
        # Format américain : 1,000.50 -> supprimer les virgules comme séparateurs de milliers
        # Format européen : 1.000,50 -> remplacer les points par rien et virgules par points
        if ',' in value and '.' in value:
            # Format américain probablement (1,000.50)
            value = value.replace(',', '')
        elif ',' in value:
            # Pourrait être européen ou américain
            # Si la virgule est suivie de 2 chiffres à la fin, c'est probablement décimal
            if value.rfind(',') == len(value) - 3:
                value = value.replace(',', '.')
            else:
                value = value.replace(',', '')
        
        # Supprimer les espaces
        value = value.replace(' ', '')
        
        try:
            amount = float(value)
        except ValueError:
            raise ValidationError(f"{field_name} doit être un nombre valide")
        
        if amount <= 0:
            raise ValidationError(f"{field_name} doit être positif")
        
        if amount > 1_000_000_000:  # 1 milliard
            raise ValidationError(f"{field_name} ne peut pas dépasser 1 milliard")
        
        # Arrondir à 2 décimales pour éviter les problèmes de précision
        return round(amount, 2)
    
    @staticmethod
    def validate_email(value: str, field_name: str = "Email") -> str:
        """
        Valide une adresse email (optionnelle).
        
        Args:
            value: La valeur à valider
            field_name: Le nom du champ pour les messages d'erreur
            
        Returns:
            str: L'email validé ou None si vide
            
        Raises:
            ValidationError: Si la validation échoue
        """
        if not value or not value.strip():
            return ""
        
        value = value.strip().lower()
        
        if not Validators.EMAIL_PATTERN.match(value):
            raise ValidationError(f"{field_name} format invalide")
        
        return value
    
    @staticmethod
    def validate_month(value: str, field_name: str = "Mois") -> str:
        """
        Valide une date au format YYYY-MM-DD ou YYYY-MM.
        
        Args:
            value: La valeur à valider
            field_name: Le nom du champ pour les messages d'erreur
            
        Returns:
            str: La date validée au format YYYY-MM-DD
            
        Raises:
            ValidationError: Si la validation échoue
        """
        if not value or not value.strip():
            raise ValidationError(f"{field_name} est obligatoire")
        
        value = value.strip()
        
        # Essayer différents formats
        formats = ['%Y-%m-%d', '%Y-%m', '%d/%m/%Y', '%m/%Y']
        
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(value, fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        raise ValidationError(
            f"{field_name} format invalide. Utilisez YYYY-MM-DD ou YYYY-MM"
        )
    
    @staticmethod
    def validate_currency(value: str, field_name: str = "Devise") -> str:
        """
        Valide un code de devise.
        
        Args:
            value: La valeur à valider
            field_name: Le nom du champ pour les messages d'erreur
            
        Returns:
            str: Le code de devise validé en majuscules
            
        Raises:
            ValidationError: Si la validation échoue
        """
        if not value or not value.strip():
            raise ValidationError(f"{field_name} est obligatoire")
        
        value = value.strip().upper()
        
        # Liste des devises supportées
        supported_currencies = {'CDF', 'USD', 'EUR', 'XAF', 'CAD'}
        
        if value not in supported_currencies:
            raise ValidationError(
                f"{field_name} doit être l'une de: {', '.join(sorted(supported_currencies))}"
            )
        
        return value
    
    @staticmethod
    def validate_status(value: str, field_name: str = "Statut") -> str:
        """
        Valide un statut de souscription.
        
        Args:
            value: La valeur à valider
            field_name: Le nom du champ pour les messages d'erreur
            
        Returns:
            str: Le statut validé (en majuscule pour la première lettre)
            
        Raises:
            ValidationError: Si la validation échoue
        """
        if not value or not value.strip():
            raise ValidationError(f"{field_name} est obligatoire")
        
        value = value.strip()
        
        # Liste des statuts supportés (insensible à la casse)
        supported_statuses = {'simple', 'spécial'}
        
        if value.lower() not in supported_statuses:
            raise ValidationError(
                f"{field_name} doit être l'une de: {', '.join(sorted([s.capitalize() for s in supported_statuses]))}"
            )
        
        # Retourner avec la première lettre en majuscule
        return value.capitalize()


# Fonctions de commodité pour une utilisation plus simple
def validate_name(value: str, field_name: str = "Nom") -> str:
    """Fonction de commodité pour valider un nom."""
    return Validators.validate_name(value, field_name)


def validate_phone(value: str, field_name: str = "Téléphone") -> Optional[str]:
    """Fonction de commodité pour valider un téléphone."""
    return Validators.validate_phone(value, field_name)


def validate_amount(value: str, field_name: str = "Montant") -> float:
    """Fonction de commodité pour valider un montant."""
    return Validators.validate_amount(value, field_name)


def validate_email(value: str, field_name: str = "Email") -> str:
    """Fonction de commodité pour valider un email."""
    return Validators.validate_email(value, field_name)


def validate_month(value: str, field_name: str = "Mois") -> str:
    """Fonction de commodité pour valider un mois."""
    return Validators.validate_month(value, field_name)


def validate_currency(value: str, field_name: str = "Devise") -> str:
    """Fonction de commodité pour valider une devise."""
    return Validators.validate_currency(value, field_name)


def validate_status(value: str, field_name: str = "Statut") -> str:
    """Fonction de commodité pour valider un statut."""
    return Validators.validate_status(value, field_name)
