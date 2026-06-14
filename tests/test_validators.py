"""
Tests unitaires pour le module de validation.

Ce module contient les tests pour toutes les fonctions de validation
assurant la qualité et la robustesse des données entrées dans l'application.
"""

import pytest
from tap.core.validators import (
    ValidationError,
    validate_name,
    validate_phone,
    validate_amount,
    validate_email,
    validate_currency,
    validate_status,
)


class TestNameValidation:
    """Tests pour la validation des noms."""
    
    def test_valid_name(self):
        """Teste des noms valides."""
        assert validate_name("Jean") == "Jean"
        assert validate_name("Dupont") == "Dupont"
        assert validate_name("Marie-Claire") == "Marie-Claire"
        assert validate_name("O'Connor") == "O'Connor"
        assert validate_name("  François  ") == "François"
    
    def test_empty_name(self):
        """Teste qu'un nom vide est rejeté."""
        with pytest.raises(ValidationError, match="obligatoire"):
            validate_name("")
        
        with pytest.raises(ValidationError, match="obligatoire"):
            validate_name("   ")
    
    def test_short_name(self):
        """Teste qu'un nom trop court est rejeté."""
        with pytest.raises(ValidationError, match="au moins 2 caractères"):
            validate_name("J")
    
    def test_long_name(self):
        """Teste qu'un nom trop long est rejeté."""
        long_name = "A" * 51
        with pytest.raises(ValidationError, match="ne peut pas dépasser 50"):
            validate_name(long_name)
    
    def test_invalid_characters(self):
        """Teste que les caractères invalides sont rejetés."""
        with pytest.raises(ValidationError, match="ne peut contenir que des lettres"):
            validate_name("Jean123")
        
        with pytest.raises(ValidationError, match="ne peut contenir que des lettres"):
            validate_name("Jean@dupont")


class TestPhoneValidation:
    """Tests pour la validation des numéros de téléphone."""
    
    def test_valid_phone(self):
        """Teste des numéros valides."""
        assert validate_phone("+243 123 456 789") == "+243 123 456 789"
        assert validate_phone("0123456789") == "0123456789"
        assert validate_phone("(123) 456-7890") == "(123) 456-7890"
        assert validate_phone("") is None  # Optionnel
    
    def test_short_phone(self):
        """Teste qu'un numéro trop court est rejeté."""
        with pytest.raises(ValidationError, match="au moins 7 chiffres"):
            validate_phone("123456")
    
    def test_long_phone(self):
        """Teste qu'un numéro trop long est rejeté."""
        with pytest.raises(ValidationError, match="ne peut pas dépasser 15 chiffres"):
            validate_phone("1" * 16)
    
    def test_invalid_phone_format(self):
        """Teste qu'un format invalide est rejeté."""
        with pytest.raises(ValidationError, match="format invalide"):
            validate_phone("abc-def-ghi")


class TestAmountValidation:
    """Tests pour la validation des montants."""
    
    def test_valid_amount(self):
        """Teste des montants valides."""
        assert validate_amount("100") == 100.0
        assert validate_amount("100.50") == 100.5
        assert validate_amount("1,000.50") == 1000.5
        assert validate_amount("  500  ") == 500.0
    
    def test_empty_amount(self):
        """Teste qu'un montant vide est rejeté."""
        with pytest.raises(ValidationError, match="obligatoire"):
            validate_amount("")
    
    def test_negative_amount(self):
        """Teste qu'un montant négatif est rejeté."""
        with pytest.raises(ValidationError, match="doit être positif"):
            validate_amount("-100")
    
    def test_zero_amount(self):
        """Teste qu'un montant nul est rejeté."""
        with pytest.raises(ValidationError, match="doit être positif"):
            validate_amount("0")
    
    def test_invalid_amount(self):
        """Teste qu'un montant invalide est rejeté."""
        with pytest.raises(ValidationError, match="doit être un nombre valide"):
            validate_amount("abc")
    
    def test_too_large_amount(self):
        """Teste qu'un montant trop grand est rejeté."""
        with pytest.raises(ValidationError, match="ne peut pas dépasser 1 milliard"):
            validate_amount("1000000001")


class TestEmailValidation:
    """Tests pour la validation des emails."""
    
    def test_valid_email(self):
        """Teste des emails valides."""
        assert validate_email("test@example.com") == "test@example.com"
        assert validate_email("user.name@domain.co.uk") == "user.name@domain.co.uk"
        assert validate_email("") == ""  # Optionnel
    
    def test_invalid_email(self):
        """Teste qu'un email invalide est rejeté."""
        with pytest.raises(ValidationError, match="format invalide"):
            validate_email("invalid-email")
        
        with pytest.raises(ValidationError, match="format invalide"):
            validate_email("@example.com")


class TestCurrencyValidation:
    """Tests pour la validation des devises."""
    
    def test_valid_currency(self):
        """Teste des devises valides."""
        assert validate_currency("USD") == "USD"
        assert validate_currency("cdf") == "CDF"  # Converti en majuscules
        assert validate_currency("Eur") == "EUR"
    
    def test_empty_currency(self):
        """Teste qu'une devise vide est rejetée."""
        with pytest.raises(ValidationError, match="obligatoire"):
            validate_currency("")
    
    def test_invalid_currency(self):
        """Teste qu'une devise invalide est rejetée."""
        with pytest.raises(ValidationError, match="doit être l'une de"):
            validate_currency("GBP")


class TestStatusValidation:
    """Tests pour la validation des statuts."""
    
    def test_valid_status(self):
        """Teste des statuts valides."""
        assert validate_status("Simple") == "Simple"
        assert validate_status("spécial") == "Spécial"  # Converti
    
    def test_empty_status(self):
        """Teste qu'un statut vide est rejeté."""
        with pytest.raises(ValidationError, match="obligatoire"):
            validate_status("")
    
    def test_invalid_status(self):
        """Teste qu'un statut invalide est rejeté."""
        with pytest.raises(ValidationError, match="doit être l'une de"):
            validate_status("Premium")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
