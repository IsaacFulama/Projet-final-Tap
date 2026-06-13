from datetime import date

import customtkinter as ctk
from tkinter import messagebox

from tap.config.theme import C
from tap.core.date_utils import parse_mois_saisie
from tap.infrastructure.database import inserer_souscription, modifier_souscription

# ── Helpers de validation ──────────────────────────────────────────────────────

def _is_valid_name(v: str) -> bool:
    return len(v.strip()) >= 2

def _is_valid_phone(v: str) -> bool:
    digits = ''.join(c for c in v if c.isdigit())
    return len(digits) >= 7

def _is_valid_month(v: str) -> bool:
    """Valide une date au format AAAA-MM-JJ ou AAAA-MM."""
    return parse_mois_saisie(v) is not None

def _is_valid_amount(v: str) -> bool:
    try:
        return float(v.strip()) > 0
    except ValueError:
        return False


# ── Widget : champ avec label + validation inline ─────────────────────────────

class ValidatedField(ctk.CTkFrame):
    """Entry avec label, placeholder et feedback de validation intégré."""

    def __init__(self, master, label: str, placeholder: str,
                 validator=None, required: bool = True, **entry_kwargs):
        super().__init__(master, fg_color='transparent')
        self.validator = validator
        self.required  = required
        self._dirty    = False  # ne valider qu'après première interaction

        # Label
        lbl_row = ctk.CTkFrame(self, fg_color='transparent')
        lbl_row.pack(fill='x')

        self.lbl = ctk.CTkLabel(lbl_row,
                                text=f'{label} {"*" if required else ""}',
                                font=ctk.CTkFont(size=11, weight='bold'),
                                text_color=C['text_hi'])
        self.lbl.pack(side='left')

        self.lbl_error = ctk.CTkLabel(lbl_row, text='',
                                      font=ctk.CTkFont(size=10),
                                      text_color=C['red'])
        self.lbl_error.pack(side='right')

        # Entry
        self.entry = ctk.CTkEntry(self,
                                  placeholder_text=placeholder,
                                  fg_color=C['bg_section'],
                                  border_color=C['border'],
                                  text_color=C['text_hi'],
                                  placeholder_text_color=C['text_lo'],
                                  height=38,
                                  **entry_kwargs)
        self.entry.pack(fill='x', pady=(6, 0))

        self.entry.bind('<FocusOut>', self._on_blur)
        self.entry.bind('<KeyRelease>', self._on_key)

    def _on_blur(self, _event=None):
        """Valide au moment où l'utilisateur quitte le champ."""
        self._dirty = True
        self._validate()

    def _on_key(self, _event=None):
        """Revalide à chaque frappe si le champ a déjà été touché."""
        if self._dirty:
            self._validate()

    def _validate(self) -> bool:
        if not self._dirty:
            return True
        value = self.entry.get()
        if self.required and not value.strip():
            self._set_error('Champ obligatoire')
            return False
        if self.validator and value.strip() and not self.validator(value):
            self._set_error('Valeur invalide')
            return False
        self._set_valid()
        return True

    def _set_error(self, msg: str):
        self.entry.configure(border_color=C['red'])
        self.lbl_error.configure(text=msg)

    def _set_valid(self):
        self.entry.configure(border_color=C['green'])
        self.lbl_error.configure(text='✓')
        self.lbl_error.configure(text_color=C['green'])

    def get(self) -> str:
        return self.entry.get().strip()

    def is_valid(self) -> bool:
        """Force la validation (même si pas encore touché) et retourne le résultat."""
        self._dirty = True
        return self._validate()

    def focus(self):
        self.entry.focus()

    def bind_return(self, next_widget):
        """Passe le focus au widget suivant lorsque <Return> est pressé."""
        self.entry.bind('<Return>', lambda _: next_widget.focus())


# ── Formulaire principal ───────────────────────────────────────────────────────

class FormulaireSouscription(ctk.CTkToplevel):
    def __init__(self, parent, callback_maj_tableau, paiement_id=None, donnees_initiales=None):
        super().__init__(parent)
        self.callback_maj_tableau = callback_maj_tableau
        self.paiement_id = paiement_id
        self.mode_edition = paiement_id is not None
        self.donnees_initiales = donnees_initiales

        title = 'TAP · Modifier Paiement' if self.mode_edition else 'TAP · Nouveau Paiement'
        self.title(title)
        self._set_initial_geometry()
        self.resizable(True, True)
        self.minsize(420, 480)
        self.configure(fg_color=C['bg_deep'])

        # Modalité correcte
        self.transient(parent)
        self.grab_set()

        # Fermeture clavier
        self.bind('<Escape>', lambda _: self.destroy())

        self._build_ui()

        # Pré-remplir si mode édition
        if self.mode_edition and self.donnees_initiales:
            self._remplir_champs()

        # Auto-focus sur le premier champ
        self.after(120, self.field_nom.focus)

    def _set_initial_geometry(self):
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(max(int(screen_width * 0.42), 520), 760)
        height = min(max(int(screen_height * 0.8), 560), 780)
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f'{width}x{height}+{x}+{y}')

    # ── Construction UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        card = ctk.CTkFrame(self, fg_color=C['bg_card'], corner_radius=16,
                            border_width=1, border_color=C['border'])
        card.pack(fill='both', expand=True, padx=20, pady=20)

        # ─ Header ─
        header = ctk.CTkFrame(card, fg_color='transparent')
        header.pack(fill='x', padx=24, pady=(24, 16))

        header_text = 'Modifier Paiement' if self.mode_edition else 'Nouveau Paiement'
        ctk.CTkLabel(header, text=header_text,
                     font=ctk.CTkFont(family='Georgia', size=22, weight='bold'),
                     text_color=C['accent']).pack(anchor='w')
        ctk.CTkLabel(header, text='Tous les champs marqués * sont obligatoires',
                     font=ctk.CTkFont(size=11),
                     text_color=C['text_lo']).pack(anchor='w', pady=(4, 0))

        ctk.CTkFrame(card, height=1, fg_color=C['border']).pack(fill='x', padx=24)

        # ─ Champs ─
        form = ctk.CTkScrollableFrame(card, fg_color='transparent')
        form.pack(fill='both', expand=True, padx=24, pady=(16, 0))

        # Ligne 1 : Nom / Prénom
        row1 = ctk.CTkFrame(form, fg_color='transparent')
        row1.pack(fill='x', pady=(0, 12))

        self.field_nom = ValidatedField(row1, 'Nom', 'Dupont',
                                        validator=_is_valid_name)
        self.field_nom.pack(side='left', fill='both', expand=True, padx=(0, 8))

        self.field_prenom = ValidatedField(row1, 'Prénom', 'Jean',
                                           validator=_is_valid_name)
        self.field_prenom.pack(side='left', fill='both', expand=True, padx=(8, 0))

        # Téléphone
        self.field_telephone = ValidatedField(form, 'Téléphone', '+243 XXX XXX XXX',
                                              validator=_is_valid_phone)
        self.field_telephone.pack(fill='x', pady=(0, 12))

        # Ligne 2 : Mois / Montant
        row2 = ctk.CTkFrame(form, fg_color='transparent')
        row2.pack(fill='x', pady=(0, 12))

        default_mois = date.today().replace(day=1).strftime('%Y-%m-%d')
        self.field_mois = ValidatedField(row2, 'Mois (date)', 'AAAA-MM-JJ',
                                         validator=_is_valid_month)
        self.field_mois.entry.insert(0, default_mois)
        self.field_mois.pack(side='left', fill='both', expand=True, padx=(0, 8))

        self.field_montant = ValidatedField(row2, 'Montant total', '0.00',
                                            validator=_is_valid_amount)
        self.field_montant.pack(side='left', fill='both', expand=True, padx=(0, 8))

        # Montant payé (acompte optionnel)
        self.field_montant_paye = ValidatedField(row2, 'Montant payé (optionnel)', 'Laisser vide pour paiement complet',
                                              validator=_is_valid_amount, required=False)
        self.field_montant_paye.pack(side='left', fill='both', expand=True, padx=(8, 0))

        # Ligne 3 : Devise
        row3 = ctk.CTkFrame(form, fg_color='transparent')
        row3.pack(fill='x', pady=(0, 16))

        col_devise = ctk.CTkFrame(row3, fg_color='transparent')
        col_devise.pack(side='left', fill='both', expand=True)
        ctk.CTkLabel(col_devise, text='Devise',
                     font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_hi']).pack(anchor='w', pady=(0, 6))
        self.combo_devise = self._combo(col_devise, ['CDF', 'USD', 'EUR', 'XAF', 'CAD'], 'CDF')
        self.combo_devise.pack(fill='x')

        col_statut_souscription = ctk.CTkFrame(row3, fg_color='transparent')
        col_statut_souscription.pack(side='left', fill='both', expand=True, padx=(12, 0))
        ctk.CTkLabel(col_statut_souscription, text='Statut souscription',
                     font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_hi']).pack(anchor='w', pady=(0, 6))
        self.combo_statut_souscription = self._combo(
            col_statut_souscription,
            ['Spécial', 'Simple'],
            'Simple'
        )
        self.combo_statut_souscription.pack(fill='x')

        # ─ Navigation clavier : <Return> passe au champ suivant ─
        all_fields = [self.field_nom, self.field_prenom,
                      self.field_telephone, self.field_mois, self.field_montant, self.field_montant_paye]
        for i, f in enumerate(all_fields[:-1]):
            f.bind_return(all_fields[i + 1])
        # Dernier champ → soumettre
        self.field_montant_paye.entry.bind('<Return>', lambda _: self._enregistrer())

        # ─ Boutons ─
        ctk.CTkFrame(card, height=1, fg_color=C['border']).pack(fill='x', padx=24)

        btn_row = ctk.CTkFrame(card, fg_color='transparent')
        btn_row.pack(fill='x', padx=24, pady=16)

        ctk.CTkButton(btn_row, text='Annuler', width=120, height=40,
                      fg_color='transparent',
                      border_color=C['border'], border_width=1,
                      text_color=C['text_lo'],
                      hover_color=C['bg_section'],
                      command=self.destroy).pack(side='left')

        self.btn_save = ctk.CTkButton(
            btn_row, text='  Enregistrer  ', height=40,
            fg_color=C['accent'], hover_color=C['accent_dim'],
            text_color='#000000',
            font=ctk.CTkFont(size=13, weight='bold'),
            corner_radius=8,
            command=self._enregistrer
        )
        self.btn_save.pack(side='right')

    def _remplir_champs(self):
        """Pré-remplit les champs avec les données existantes."""
        if not self.donnees_initiales:
            return

        # donnees_initiales format: (paiement_id, locataire_id, nom, prenom, mois, montant, devise, statut_souscription, statut, montant_total, montant_paye, reste_a_payer, statut_paiement)
        paiement_id, locataire_id, nom, prenom, mois, montant, devise, statut_souscription, statut, montant_total, montant_paye, reste_a_payer, statut_paiement = self.donnees_initiales

        self.field_nom.entry.delete(0, 'end')
        self.field_nom.entry.insert(0, nom)

        self.field_prenom.entry.delete(0, 'end')
        self.field_prenom.entry.insert(0, prenom)

        # Téléphone n'est pas dans les données initiales, on laisse vide
        # self.field_telephone.entry.delete(0, 'end')
        # self.field_telephone.entry.insert(0, telephone)

        self.field_mois.entry.delete(0, 'end')
        self.field_mois.entry.insert(0, mois)

        self.field_montant.entry.delete(0, 'end')
        self.field_montant.entry.insert(0, str(montant_total))

        # Montant payé (si différent du total)
        if montant_paye and float(montant_paye) < float(montant_total):
            self.field_montant_paye.entry.delete(0, 'end')
            self.field_montant_paye.entry.insert(0, str(montant_paye))

        self.combo_devise.set(devise)
        self.combo_statut_souscription.set(statut_souscription)

    # ── Helpers UI ─────────────────────────────────────────────────────────────

    def _combo(self, master, values: list, default: str) -> ctk.CTkComboBox:
        cb = ctk.CTkComboBox(
            master, values=values, height=38,
            fg_color=C['bg_section'],
            border_color=C['border'],
            text_color=C['text_hi'],
            dropdown_fg_color=C['bg_section'],
            dropdown_text_color=C['text_hi'],
            dropdown_hover_color=C['border'],
            button_color=C['border'],
            button_hover_color=C['accent_dim']
        )
        cb.set(default)
        return cb

    # ── Logique d'enregistrement ───────────────────────────────────────────────

    def _enregistrer(self):
        # Forcer la validation de tous les champs obligatoires
        fields = [self.field_nom, self.field_prenom,
                  self.field_telephone, self.field_mois, self.field_montant]
        errors = [f for f in fields if not f.is_valid()]

        # Valider le montant payé seulement s'il est rempli
        if self.field_montant_paye.get() and not self.field_montant_paye.is_valid():
            errors.append(self.field_montant_paye)

        if errors:
            errors[0].focus()   # amener le focus sur le premier champ en erreur
            return

        # Récupérer le montant payé (optionnel)
        montant_paye = self.field_montant_paye.get()
        if not montant_paye:
            montant_paye = None

        # Désactiver le bouton le temps de l'insertion
        self.btn_save.configure(state='disabled', text='Enregistrement…')
        self.update_idletasks()

        if self.mode_edition:
            success, message = modifier_souscription(
                self.paiement_id,
                self.field_nom.get(),
                self.field_prenom.get(),
                self.field_telephone.get(),
                self.field_mois.get(),
                self.field_montant.get(),
                self.combo_devise.get(),
                statut_souscription=self.combo_statut_souscription.get(),
                montant_paye=montant_paye,
            )
        else:
            success, message = inserer_souscription(
                self.field_nom.get(),
                self.field_prenom.get(),
                self.field_telephone.get(),
                self.field_mois.get(),
                self.field_montant.get(),
                self.combo_devise.get(),
                statut_souscription=self.combo_statut_souscription.get(),
                montant_paye=montant_paye,
            )

        if success:
            messagebox.showinfo('Succès', message)
            self.destroy()
            self.callback_maj_tableau()
        else:
            self.btn_save.configure(state='normal', text='  Enregistrer  ')
            messagebox.showerror('Erreur base de données', message)
