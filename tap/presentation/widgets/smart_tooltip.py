"""
Widget de tooltip intelligent avec suggestions contextuelles.

Ce widget fournit:
- Tooltips contextuels adaptés au champ
- Suggestions en temps réel
- Validation visuelle
- Aide à la saisie
"""

import customtkinter as ctk
from typing import Optional, Callable
from tap.core.smart_error_handler import smart_error_handler


class SmartTooltip:
    """Tooltip intelligent avec suggestions contextuelles."""
    
    def __init__(self, widget, field_name: str, show_delay: int = 500):
        """
        Initialise un tooltip intelligent.
        
        Args:
            widget: Widget ctk auquel attacher le tooltip
            field_name: Nom du champ pour les suggestions contextuelles
            show_delay: Délai en ms avant affichage
        """
        self.widget = widget
        self.field_name = field_name
        self.show_delay = show_delay
        self.tooltip_window = None
        self.after_id = None
        
        # Attacher les événements
        self.widget.bind("<Enter>", self._on_enter)
        self.widget.bind("<Leave>", self._on_leave)
        self.widget.bind("<FocusIn>", self._on_focus_in)
        self.widget.bind("<FocusOut>", self._on_focus_out)
        self.widget.bind("<KeyRelease>", self._on_key_release)
    
    def _on_enter(self, event):
        """Affiche le tooltip après délai."""
        if self.after_id:
            self.widget.after_cancel(self.after_id)
        self.after_id = self.widget.after(self.show_delay, self._show_tooltip)
    
    def _on_leave(self, event):
        """Cache le tooltip."""
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        self._hide_tooltip()
    
    def _on_focus_in(self, event):
        """Affiche le tooltip quand le champ prend le focus."""
        self._show_tooltip()
    
    def _on_focus_out(self, event):
        """Cache le tooltip quand le champ perd le focus."""
        self._hide_tooltip()
    
    def _on_key_release(self, event):
        """Met à jour le tooltip en fonction de la saisie."""
        self._show_tooltip()
    
    def _show_tooltip(self):
        """Affiche le tooltip avec suggestions contextuelles."""
        self._hide_tooltip()
        
        # Obtenir la valeur actuelle
        current_value = ""
        if hasattr(self.widget, "get"):
            current_value = self.widget.get()
        
        # Obtenir la suggestion contextuelle
        suggestion = smart_error_handler.get_tooltip_suggestion(
            self.field_name, 
            current_value
        )
        
        # Créer la fenêtre du tooltip
        self.tooltip_window = ctk.CTkToplevel(self.widget.winfo_toplevel())
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry("+%d+%d" % (
            self.widget.winfo_rootx() + 25,
            self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        ))
        
        # Créer le contenu
        frame = ctk.CTkFrame(
            self.tooltip_window,
            fg_color="#2b2b2b",
            corner_radius=5,
            border_width=1,
            border_color="#555"
        )
        frame.pack(padx=5, pady=5)
        
        label = ctk.CTkLabel(
            frame,
            text=suggestion,
            font=("Arial", 9),
            text_color="#ffffff",
            wraplength=300,
            justify="left"
        )
        label.pack(padx=10, pady=5)
        
        # Ajouter un indicateur visuel si la valeur semble invalide
        if self._is_value_invalid(current_value):
            warning_label = ctk.CTkLabel(
                frame,
                text="⚠️ Format invalide",
                font=("Arial", 8),
                text_color="#ff6b6b"
            )
            warning_label.pack(pady=(0, 5))
    
    def _hide_tooltip(self):
        """Cache le tooltip."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
    
    def _is_value_invalid(self, value: str) -> bool:
        """Vérifie si la valeur actuelle semble invalide."""
        if not value:
            return False
        
        if self.field_name == "telephone":
            # Vérification basique du téléphone
            cleaned = value.replace(" ", "").replace("-", "")
            if not cleaned.startswith("+") or len(cleaned) < 10:
                return True
        
        elif self.field_name == "montant":
            # Vérification basique du montant
            try:
                float(value.replace(",", "."))
            except ValueError:
                return True
        
        return False


class SmartEntry(ctk.CTkEntry):
    """Champ de saisie intelligent avec validation et suggestions."""
    
    def __init__(self, master, field_name: str, **kwargs):
        """
        Initialise un champ de saisie intelligent.
        
        Args:
            master: Widget parent
            field_name: Nom du champ pour les suggestions
            **kwargs: Arguments supplémentaires pour CTkEntry
        """
        self.field_name = field_name
        self.validation_callback = kwargs.pop("validation_callback", None)
        self.error_callback = kwargs.pop("error_callback", None)
        
        super().__init__(master, **kwargs)
        
        # Tooltip intelligent
        self.tooltip = SmartTooltip(self, field_name)
        
        # Validation en temps réel
        self.bind("<KeyRelease>", self._validate_on_type)
        self.bind("<FocusOut>", self._validate_on_focus_out)
        
        # État de validation
        self.is_valid = True
    
    def _validate_on_type(self, event):
        """Valide en temps réel pendant la saisie."""
        value = self.get()
        if not value:
            self._set_valid_state()
            return
        
        is_valid, message = self._validate_value(value)
        self.is_valid = is_valid
        
        if is_valid:
            self._set_valid_state()
        else:
            self._set_invalid_state()
            if self.error_callback:
                self.error_callback(message)
    
    def _validate_on_focus_out(self, event):
        """Valide quand le champ perd le focus."""
        value = self.get()
        if value:
            is_valid, message = self._validate_value(value)
            self.is_valid = is_valid
            
            if not is_valid:
                self._set_invalid_state()
                # Tenter l'auto-correction
                from tap.core.smart_error_handler import smart_error_handler
                success, corrected = smart_error_handler.attempt_auto_fix(
                    self.field_name,
                    {self.field_name: value}
                )
                if success:
                    self.delete(0, ctk.END)
                    self.insert(0, corrected.split(": ")[1])
                    self._set_valid_state()
    
    def _validate_value(self, value: str) -> tuple[bool, str]:
        """Valide la valeur du champ."""
        if self.field_name == "telephone":
            return self._validate_phone(value)
        elif self.field_name == "montant":
            return self._validate_amount(value)
        elif self.field_name in ["nom", "prenom"]:
            return self._validate_name(value)
        
        return True, ""
    
    def _validate_phone(self, value: str) -> tuple[bool, str]:
        """Valide un numéro de téléphone."""
        cleaned = value.replace(" ", "").replace("-", "")
        
        if not cleaned.startswith("+"):
            return False, "Le numéro doit commencer par le code pays (+)"
        
        if len(cleaned) < 10 or len(cleaned) > 15:
            return False, "Le numéro doit contenir entre 10 et 15 chiffres"
        
        if not cleaned[1:].isdigit():
            return False, "Le numéro ne doit contenir que des chiffres après le +"
        
        return True, ""
    
    def _validate_amount(self, value: str) -> tuple[bool, str]:
        """Valide un montant."""
        try:
            amount = float(value.replace(",", "."))
            
            if amount < 0:
                return False, "Le montant ne peut pas être négatif"
            
            if amount > 10000000:
                return False, "Le montant semble trop élevé"
            
            return True, ""
        
        except ValueError:
            return False, "Le montant doit être un nombre valide"
    
    def _validate_name(self, value: str) -> tuple[bool, str]:
        """Valide un nom."""
        if len(value) < 2:
            return False, "Le nom doit contenir au moins 2 caractères"
        
        if len(value) > 50:
            return False, "Le nom est trop long"
        
        return True, ""
    
    def _set_valid_state(self):
        """Met le champ dans l'état valide."""
        self.configure(border_color="#4CAF50")  # Vert
    
    def _set_invalid_state(self):
        """Met le champ dans l'état invalide."""
        self.configure(border_color="#F44336")  # Rouge
    
    def get_validated(self) -> tuple[bool, str]:
        """
        Retourne la valeur validée.
        
        Returns:
            (is_valid, value)
        """
        value = self.get()
        is_valid, _ = self._validate_value(value)
        return is_valid, value


class SmartComboBox(ctk.CTkComboBox):
    """ComboBox intelligent avec suggestions."""
    
    def __init__(self, master, field_name: str, **kwargs):
        """
        Initialise un ComboBox intelligent.
        
        Args:
            master: Widget parent
            field_name: Nom du champ pour les suggestions
            **kwargs: Arguments supplémentaires pour CTkComboBox
        """
        self.field_name = field_name
        super().__init__(master, **kwargs)
        
        # Tooltip intelligent
        self.tooltip = SmartTooltip(self, field_name)


def create_smart_form_field(parent, field_name: str, field_type: str = "entry", **kwargs):
    """
    Crée un champ de formulaire intelligent.
    
    Args:
        parent: Widget parent
        field_name: Nom du champ
        field_type: Type de champ ("entry", "combobox")
        **kwargs: Arguments supplémentaires
    
    Returns:
        Widget intelligent créé
    """
    common_kwargs = {
        "placeholder_text": field_name.capitalize(),
        "width": 200,
        "height": 32,
    }
    common_kwargs.update(kwargs)
    
    if field_type == "entry":
        return SmartEntry(parent, field_name, **common_kwargs)
    elif field_type == "combobox":
        return SmartComboBox(parent, field_name, **common_kwargs)
    else:
        return ctk.CTkEntry(parent, **common_kwargs)
