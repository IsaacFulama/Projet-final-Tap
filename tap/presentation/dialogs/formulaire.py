from datetime import date

import customtkinter as ctk
from tkinter import messagebox

from tap.config.theme import C
from tap.config.responsive import clamp_window_geometry, detect_screen_profile
from tap.core.date_utils import build_month_choices, format_month_choice, format_month_label, month_name_fr, parse_mois_saisie
from tap.core.validators import ValidationError, validate_name, validate_phone, validate_amount
from tap.infrastructure.database import inserer_souscription, modifier_souscription


def _appeler_callback(callback, details=None):
    if details:
        try:
            callback(details)
            return
        except TypeError:
            pass
    callback()


# ── Helpers de validation compatibles avec l'interface existante ────────────────

def _is_valid_name(v: str) -> bool:
    """Wrapper de validation pour les noms (compatible avec l'interface existante)."""
    try:
        validate_name(v)
        return True
    except ValidationError:
        return False


def _is_valid_phone(v: str) -> bool:
    """Wrapper de validation pour les téléphones (compatible avec l'interface existante)."""
    try:
        validate_phone(v)
        return True
    except ValidationError:
        return False


def _is_valid_amount(v: str) -> bool:
    """Wrapper de validation pour les montants (compatible avec l'interface existante)."""
    try:
        validate_amount(v)
        return True
    except ValidationError:
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


# ── Nouveau souscripteur ─────────────────────────────────────────────────────

class NouveauSouscripteurDialog(ctk.CTkToplevel):
    """Dialogue de création rapide d'un souscripteur synchronisé au mois courant."""

    def __init__(self, parent, callback_maj_tableau):
        super().__init__(parent)
        self.callback_maj_tableau = callback_maj_tableau
        self._screen = detect_screen_profile()
        self._compact_mode = self._screen.width < 1100
        self._cycle_reference = date.today().replace(day=1)

        self.title("TAP · Nouveau Souscripteur")
        self._set_initial_geometry()
        self.resizable(True, True)
        self.minsize(
            max(380, min(560, self._screen.width - 20)),
            max(400, min(520, self._screen.height - 20)),
        )
        self.configure(fg_color=C['bg_deep'])

        self.transient(parent)
        self.grab_set()
        self.bind('<Escape>', lambda _: self.destroy())

        self._build_ui()
        self.after(120, self.field_nom.focus)

    def _set_initial_geometry(self):
        self.update_idletasks()
        screen_width = self._screen.width
        screen_height = self._screen.height

        if min(screen_width, screen_height) < 900:
            width_ratio, height_ratio = 0.92, 0.80
            min_width, min_height = 420, 420
        elif screen_width < 1366:
            width_ratio, height_ratio = 0.50, 0.66
            min_width, min_height = 480, 460
        else:
            width_ratio, height_ratio = 0.40, 0.62
            min_width, min_height = 520, 480

        width, height = clamp_window_geometry(
            screen_width,
            screen_height,
            width_ratio=width_ratio,
            height_ratio=height_ratio,
            min_width=min_width,
            min_height=min_height,
        )
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_ui(self):
        card = ctk.CTkFrame(
            self,
            fg_color=C['bg_card'],
            corner_radius=16,
            border_width=1,
            border_color=C['border'],
        )
        card.pack(
            fill='both',
            expand=True,
            padx=16 if self._compact_mode else 20,
            pady=16 if self._compact_mode else 20,
        )

        header = ctk.CTkFrame(card, fg_color='transparent')
        header.pack(
            fill='x',
            padx=20 if self._compact_mode else 24,
            pady=(20 if self._compact_mode else 24, 14),
        )
        ctk.CTkLabel(
            header,
            text='Nouveau souscripteur',
            font=ctk.CTkFont(family='Georgia', size=20 if self._compact_mode else 22, weight='bold'),
            text_color=C['accent'],
        ).pack(anchor='w')
        ctk.CTkLabel(
            header,
            text='Création synchronisée au mois courant pour coller au cycle mensuel du projet',
            font=ctk.CTkFont(size=11),
            text_color=C['text_lo'],
        ).pack(anchor='w', pady=(4, 0))

        sync_card = ctk.CTkFrame(
            card,
            fg_color=C['bg_section'],
            corner_radius=12,
            border_width=0,
        )
        sync_card.pack(fill='x', padx=20 if self._compact_mode else 24, pady=(0, 14))
        ctk.CTkLabel(
            sync_card,
            text=f"Cycle par défaut : {format_month_label(self._cycle_reference)}",
            font=ctk.CTkFont(size=13, weight='bold'),
            text_color=C['text_hi'],
        ).pack(anchor='w', padx=14, pady=(10, 0))
        ctk.CTkLabel(
            sync_card,
            text="Le mois et l'année peuvent être choisis ici sans casser la logique d'enregistrement ni la maintenance mensuelle.",
            font=ctk.CTkFont(size=10),
            text_color=C['text_lo'],
            wraplength=560,
            justify='left',
        ).pack(anchor='w', padx=14, pady=(2, 10))

        ctk.CTkFrame(card, height=1, fg_color=C['border']).pack(fill='x', padx=20 if self._compact_mode else 24)

        form = ctk.CTkScrollableFrame(card, fg_color='transparent')
        form.pack(fill='both', expand=True, padx=20 if self._compact_mode else 24, pady=(16, 0))

        row1 = ctk.CTkFrame(form, fg_color='transparent')
        row1.pack(fill='x', pady=(0, 12))
        self.field_nom = ValidatedField(row1, 'Nom', 'Dupont', validator=_is_valid_name)
        self.field_prenom = ValidatedField(row1, 'Prénom', 'Jean', validator=_is_valid_name)
        if self._compact_mode:
            self.field_nom.pack(fill='x', pady=(0, 10))
            self.field_prenom.pack(fill='x')
        else:
            self.field_nom.pack(side='left', fill='both', expand=True, padx=(0, 8))
            self.field_prenom.pack(side='left', fill='both', expand=True, padx=(8, 0))

        self.field_telephone = ValidatedField(
            form,
            'Numéro (optionnel)',
            '+243 XXX XXX XXX',
            validator=_is_valid_phone,
            required=False,
        )
        self.field_telephone.pack(fill='x', pady=(0, 12))

        month_card = ctk.CTkFrame(
            form,
            fg_color=C['bg_card'],
            corner_radius=14,
            border_width=1,
            border_color=C['border'],
        )
        month_card.pack(fill='x', pady=(0, 12))

        month_header = ctk.CTkFrame(month_card, fg_color='transparent')
        month_header.pack(fill='x', padx=14, pady=(12, 6))
        ctk.CTkLabel(
            month_header,
            text='Mois de souscription',
            font=ctk.CTkFont(size=11, weight='bold'),
            text_color=C['text_hi'],
        ).pack(side='left')
        ctk.CTkLabel(
            month_header,
            text='Choix guidé',
            font=ctk.CTkFont(size=10),
            text_color=C['text_lo'],
        ).pack(side='right')

        month_controls = ctk.CTkFrame(month_card, fg_color='transparent')
        month_controls.pack(fill='x', padx=14, pady=(0, 10))
        if self._compact_mode:
            month_controls.columnconfigure(0, weight=1)
        else:
            month_controls.columnconfigure((0, 1), weight=1, uniform='new_month')

        current_month = self._cycle_reference.month
        current_year = self._cycle_reference.year
        month_options = [month_name_fr(i) for i in range(1, 13)]
        year_start = 2025
        year_end = max(year_start, current_year + 5)
        year_options = [str(year) for year in range(year_start, year_end + 1)]

        self.combo_month_name = self._combo(
            month_controls,
            month_options,
            month_name_fr(current_month),
            180 if self._compact_mode else 200,
        )
        self.combo_month_year = self._combo(
            month_controls,
            year_options,
            str(current_year),
            120 if self._compact_mode else 140,
        )
        if self._compact_mode:
            self.combo_month_name.pack(fill='x', pady=(0, 10))
            self.combo_month_year.pack(fill='x')
        else:
            self.combo_month_name.grid(row=0, column=0, sticky='ew', padx=(0, 8))
            self.combo_month_year.grid(row=0, column=1, sticky='ew', padx=(8, 0))

        self.month_preview_card = ctk.CTkFrame(
            month_card,
            fg_color=C['bg_section'],
            corner_radius=12,
            border_width=0,
        )
        self.month_preview_card.pack(fill='x', padx=14, pady=(0, 14))
        self.month_preview_label = ctk.CTkLabel(
            self.month_preview_card,
            text='',
            font=ctk.CTkFont(size=16, weight='bold'),
            text_color=C['accent'],
        )
        self.month_preview_label.pack(anchor='w', padx=14, pady=(10, 0))
        self.month_preview_subtitle = ctk.CTkLabel(
            self.month_preview_card,
            text='',
            font=ctk.CTkFont(size=10),
            text_color=C['text_lo'],
        )
        self.month_preview_subtitle.pack(anchor='w', padx=14, pady=(0, 10))
        self.combo_month_name.configure(command=lambda _: self._update_month_preview())
        self.combo_month_year.configure(command=lambda _: self._update_month_preview())
        self._set_month_picker_from_date(self._cycle_reference)

        row2 = ctk.CTkFrame(form, fg_color='transparent')
        row2.pack(fill='x', pady=(0, 12))

        col_montant = ctk.CTkFrame(row2, fg_color='transparent')
        if self._compact_mode:
            col_montant.pack(fill='x', pady=(0, 10))
        else:
            col_montant.pack(side='left', fill='both', expand=True, padx=(0, 8))
        self.field_montant_souscrit = ValidatedField(
            col_montant,
            'Souscription',
            '0.00',
            validator=_is_valid_amount,
        )
        self.field_montant_souscrit.pack(fill='x')

        col_devise = ctk.CTkFrame(row2, fg_color='transparent')
        if self._compact_mode:
            col_devise.pack(fill='x')
        else:
            col_devise.pack(side='left', fill='both', expand=True, padx=(8, 0))
        ctk.CTkLabel(
            col_devise,
            text='Devise',
            font=ctk.CTkFont(size=11, weight='bold'),
            text_color=C['text_hi'],
        ).pack(anchor='w', pady=(0, 6))
        self.combo_devise = self._combo(col_devise, ['CDF', 'USD'], 'CDF', 180 if self._compact_mode else 200)
        self.combo_devise.pack(fill='x')

        row3 = ctk.CTkFrame(form, fg_color='transparent')
        row3.pack(fill='x', pady=(0, 16))

        self.field_avance = ValidatedField(
            row3,
            'Avance / acompte (optionnel)',
            'Ex. 20 si une avance est déjà versée',
            validator=_is_valid_amount,
            required=False,
        )
        self.field_avance.pack(fill='x', pady=(0, 8))

        ctk.CTkLabel(
            row3,
            text='Statut du souscripteur',
            font=ctk.CTkFont(size=11, weight='bold'),
            text_color=C['text_hi'],
        ).pack(anchor='w', pady=(0, 6))
        self.combo_statut_souscription = self._combo(row3, ['Spécial', 'Simple'], 'Simple', 260)
        self.combo_statut_souscription.pack(fill='x')

        ctk.CTkFrame(card, height=1, fg_color=C['border']).pack(fill='x', padx=20 if self._compact_mode else 24)

        btn_row = ctk.CTkFrame(card, fg_color='transparent')
        btn_row.pack(fill='x', padx=20 if self._compact_mode else 24, pady=16)

        ctk.CTkButton(
            btn_row,
            text='Annuler',
            width=120,
            height=40,
            fg_color='transparent',
            border_color=C['border'],
            border_width=1,
            text_color=C['text_lo'],
            hover_color=C['bg_section'],
            command=self.destroy,
        ).pack(side='top' if self._compact_mode else 'left', fill='x' if self._compact_mode else 'none', pady=(0, 8) if self._compact_mode else 0)

        self.btn_save = ctk.CTkButton(
            btn_row,
            text='  Créer  ',
            height=40,
            fg_color=C['accent'],
            hover_color=C['accent_dim'],
            text_color='#000000',
            font=ctk.CTkFont(size=13, weight='bold'),
            corner_radius=8,
            command=self._enregistrer,
        )
        self.btn_save.pack(side='top' if self._compact_mode else 'right', fill='x' if self._compact_mode else 'none')

        self.field_nom.bind_return(self.field_prenom)
        self.field_prenom.bind_return(self.field_telephone)
        self.field_telephone.bind_return(self.field_montant_souscrit)
        self.field_montant_souscrit.entry.bind('<Return>', lambda _: self._enregistrer())

    def _combo(self, master, values: list, default: str, width: int) -> ctk.CTkComboBox:
        cb = ctk.CTkComboBox(
            master,
            values=values,
            width=width,
            height=38,
            state='readonly',
            fg_color=C['bg_section'],
            border_color=C['border'],
            text_color=C['text_hi'],
            dropdown_fg_color=C['bg_section'],
            dropdown_text_color=C['text_hi'],
            dropdown_hover_color=C['border'],
            button_color=C['border'],
            button_hover_color=C['accent_dim'],
        )
        cb.set(default)
        return cb

    def _get_selected_month_date(self) -> date:
        """Construit la date du mois choisi dans le formulaire."""
        month_text = self.combo_month_name.get().strip()
        year_text = self.combo_month_year.get().strip()

        month_number = None
        for index in range(1, 13):
            if month_name_fr(index).casefold() == month_text.casefold():
                month_number = index
                break

        try:
            year_number = int(year_text)
        except ValueError:
            year_number = self._cycle_reference.year

        if month_number is None:
            month_number = self._cycle_reference.month

        return date(year_number, month_number, 1)

    def _set_month_picker_from_date(self, selected_date: date):
        """Positionne les sélecteurs mois et année sur une date donnée."""
        selected_date = selected_date.replace(day=1)
        self.combo_month_name.set(month_name_fr(selected_date.month))
        self.combo_month_year.set(str(selected_date.year))
        self._update_month_preview()

    def _update_month_preview(self):
        """Met à jour l'aperçu visuel du mois sélectionné."""
        selected_month = self._get_selected_month_date()
        self.month_preview_label.configure(text=format_month_label(selected_month))
        self.month_preview_subtitle.configure(
            text=f"Sera enregistré comme {selected_month.isoformat()}"
        )

    def _enregistrer(self):
        fields = [self.field_nom, self.field_prenom, self.field_montant_souscrit]
        errors = [f for f in fields if not f.is_valid()]

        if self.field_telephone.get() and not self.field_telephone.is_valid():
            errors.append(self.field_telephone)

        if errors:
            errors[0].focus()
            return

        montant_paye = None
        avance = self.field_avance.get() or None
        montant_souscrit = self.field_montant_souscrit.get()
        mois = self._get_selected_month_date().isoformat()

        self.btn_save.configure(state='disabled', text='Création…')
        self.update_idletasks()

        success, message, details = inserer_souscription(
            self.field_nom.get(),
            self.field_prenom.get(),
            self.field_telephone.get(),
            mois,
            montant_souscrit,
            self.combo_devise.get(),
            statut_souscription=self.combo_statut_souscription.get(),
            montant_paye=montant_paye,
            avance=avance,
            return_details=True,
        )

        if success:
            messagebox.showinfo('Succès', message)
            self.destroy()
            _appeler_callback(self.callback_maj_tableau, details)
        else:
            self.btn_save.configure(state='normal', text='  Créer  ')
            messagebox.showerror('Erreur base de données', message)


# ── Formulaire principal ───────────────────────────────────────────────────────

class FormulaireSouscription(ctk.CTkToplevel):
    def __init__(self, parent, callback_maj_tableau, paiement_id=None, donnees_initiales=None):
        super().__init__(parent)
        self.callback_maj_tableau = callback_maj_tableau
        self.paiement_id = paiement_id
        self.mode_edition = paiement_id is not None
        self.donnees_initiales = donnees_initiales
        self._screen = detect_screen_profile()
        self._compact_mode = self._screen.width < 1100

        title = 'TAP · Modifier Paiement' if self.mode_edition else 'TAP · Nouveau Paiement'
        self.title(title)
        self._set_initial_geometry()
        self.resizable(True, True)
        self.minsize(
            max(380, min(560, self._screen.width - 20)),
            max(440, min(580, self._screen.height - 20)),
        )
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
        screen_width = self._screen.width
        screen_height = self._screen.height

        if min(screen_width, screen_height) < 900:
            width_ratio, height_ratio = 0.94, 0.88
            min_width, min_height = 420, 480
        elif screen_width < 1366:
            width_ratio, height_ratio = 0.52, 0.78
            min_width, min_height = 480, 540
        elif screen_width < 1920:
            width_ratio, height_ratio = 0.42, 0.80
            min_width, min_height = 520, 560
        else:
            width_ratio, height_ratio = 0.34, 0.76
            min_width, min_height = 560, 580

        width, height = clamp_window_geometry(
            screen_width,
            screen_height,
            width_ratio=width_ratio,
            height_ratio=height_ratio,
            min_width=min_width,
            min_height=min_height,
        )
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f'{width}x{height}+{x}+{y}')

    # ── Construction UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        card = ctk.CTkFrame(self, fg_color=C['bg_card'], corner_radius=16,
                            border_width=1, border_color=C['border'])
        card.pack(fill='both', expand=True, padx=16 if self._compact_mode else 20,
                  pady=16 if self._compact_mode else 20)

        # ─ Header ─
        header = ctk.CTkFrame(card, fg_color='transparent')
        header.pack(fill='x', padx=20 if self._compact_mode else 24,
                    pady=(20 if self._compact_mode else 24, 16))

        header_text = 'Modifier Paiement' if self.mode_edition else 'Nouveau Paiement'
        ctk.CTkLabel(header, text=header_text,
                     font=ctk.CTkFont(family='Georgia', size=20 if self._compact_mode else 22, weight='bold'),
                     text_color=C['accent']).pack(anchor='w')
        ctk.CTkLabel(header, text='Tous les champs marqués * sont obligatoires',
                     font=ctk.CTkFont(size=11),
                     text_color=C['text_lo']).pack(anchor='w', pady=(4, 0))

        ctk.CTkFrame(card, height=1, fg_color=C['border']).pack(fill='x', padx=20 if self._compact_mode else 24)

        # ─ Champs ─
        form = ctk.CTkScrollableFrame(card, fg_color='transparent')
        form.pack(fill='both', expand=True, padx=20 if self._compact_mode else 24, pady=(16, 0))

        # Ligne 1 : Nom / Prénom
        row1 = ctk.CTkFrame(form, fg_color='transparent')
        row1.pack(fill='x', pady=(0, 12))

        self.field_nom = ValidatedField(row1, 'Nom', 'Dupont',
                                        validator=_is_valid_name)
        self.field_prenom = ValidatedField(row1, 'Prénom', 'Jean',
                                           validator=_is_valid_name)
        if self._compact_mode:
            self.field_nom.pack(fill='x', pady=(0, 10))
            self.field_prenom.pack(fill='x')
        else:
            self.field_nom.pack(side='left', fill='both', expand=True, padx=(0, 8))
            self.field_prenom.pack(side='left', fill='both', expand=True, padx=(8, 0))

        # Numéro (optionnel)
        self.field_telephone = ValidatedField(form, 'Numéro (optionnel)', '+243 XXX XXX XXX',
                                              validator=_is_valid_phone, required=False)
        self.field_telephone.pack(fill='x', pady=(0, 12))

        # Ligne 2 : Mois / Montant souscrit
        row2 = ctk.CTkFrame(form, fg_color='transparent')
        row2.pack(fill='x', pady=(0, 12))

        # Sélecteur de mois guidé
        col_mois = ctk.CTkFrame(row2, fg_color='transparent')
        if self._compact_mode:
            col_mois.pack(fill='x', pady=(0, 10))
        else:
            col_mois.pack(side='left', fill='both', expand=True, padx=(0, 8))

        month_card = ctk.CTkFrame(
            col_mois,
            fg_color=C['bg_card'],
            corner_radius=14,
            border_width=1,
            border_color=C['border'],
        )
        month_card.pack(fill='x')

        month_header = ctk.CTkFrame(month_card, fg_color='transparent')
        month_header.pack(fill='x', padx=14, pady=(12, 6))
        ctk.CTkLabel(
            month_header,
            text='Mois de paiement',
            font=ctk.CTkFont(size=11, weight='bold'),
            text_color=C['text_hi']
        ).pack(side='left')
        ctk.CTkLabel(
            month_header,
            text='Choix guidé depuis 2025',
            font=ctk.CTkFont(size=10),
            text_color=C['text_lo']
        ).pack(side='right')

        month_controls = ctk.CTkFrame(month_card, fg_color='transparent')
        month_controls.pack(fill='x', padx=14, pady=(0, 10))

        self.month_choices = build_month_choices(start_year=2025, years_ahead=5)
        self.current_month = date.today().replace(day=1)
        current_choice = format_month_choice(self.current_month)
        if current_choice not in self.month_choices:
            self.month_choices.insert(0, current_choice)

        self.combo_mois = self._combo(
            month_controls,
            self.month_choices,
            current_choice,
            320 if self._compact_mode else 360,
        )
        self.combo_mois.configure(command=lambda _: self._update_month_preview())
        self.combo_mois.pack(fill='x')

        self.month_preview_card = ctk.CTkFrame(
            month_card,
            fg_color=C['bg_section'],
            corner_radius=12,
            border_width=0,
        )
        self.month_preview_card.pack(fill='x', padx=14, pady=(0, 14))
        self.month_preview_label = ctk.CTkLabel(
            self.month_preview_card,
            text='',
            font=ctk.CTkFont(size=17, weight='bold'),
            text_color=C['accent']
        )
        self.month_preview_label.pack(anchor='w', padx=14, pady=(10, 0))
        self.month_preview_subtitle = ctk.CTkLabel(
            self.month_preview_card,
            text='',
            font=ctk.CTkFont(size=10),
            text_color=C['text_lo']
        )
        self.month_preview_subtitle.pack(anchor='w', padx=14, pady=(0, 10))

        self._set_month_picker_from_date(self.current_month)

        self.field_montant_souscrit = ValidatedField(row2, 'Souscription', '0.00',
                                                     validator=_is_valid_amount)
        if self._compact_mode:
            self.field_montant_souscrit.pack(fill='x')
        else:
            self.field_montant_souscrit.pack(side='left', fill='both', expand=True, padx=(0, 8))

        # Ligne 3 : Montant payé
        row3 = ctk.CTkFrame(form, fg_color='transparent')
        row3.pack(fill='x', pady=(0, 12))

        self.field_montant_paye = ValidatedField(
            row3,
            'Montant payé (optionnel)',
            'Laisser vide = En attente, entrer un montant pour enregistrer un versement',
            validator=_is_valid_amount,
            required=False,
        )
        self.field_montant_paye.pack(fill='x', pady=(0, 8))

        self.field_avance = ValidatedField(
            row3,
            'Avance / acompte (optionnel)',
            'Ex. 20 si l’avance est déjà versée',
            validator=_is_valid_amount,
            required=False,
        )
        self.field_avance.pack(fill='x')

        # Ligne 4 : Devise / statut
        row4 = ctk.CTkFrame(form, fg_color='transparent')
        row4.pack(fill='x', pady=(0, 16))

        col_devise = ctk.CTkFrame(row4, fg_color='transparent')
        if self._compact_mode:
            col_devise.pack(fill='x', pady=(0, 10))
        else:
            col_devise.pack(side='left', fill='both', expand=True)
        ctk.CTkLabel(col_devise, text='Devise de souscription',
                     font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_hi']).pack(anchor='w', pady=(0, 6))
        self.combo_devise = self._combo(col_devise, ['CDF', 'USD'], 'CDF')
        self.combo_devise.pack(fill='x')

        col_statut_souscription = ctk.CTkFrame(row4, fg_color='transparent')
        if self._compact_mode:
            col_statut_souscription.pack(fill='x')
        else:
            col_statut_souscription.pack(side='left', fill='both', expand=True, padx=(12, 0))
        ctk.CTkLabel(col_statut_souscription, text='Statut du souscripteur',
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
                      self.field_montant_souscrit, self.field_montant_paye]
        for i, f in enumerate(all_fields[:-1]):
            f.bind_return(all_fields[i + 1])
        # Dernier champ → soumettre
        self.field_montant_paye.entry.bind('<Return>', lambda _: self._enregistrer())

        # ─ Boutons ─
        ctk.CTkFrame(card, height=1, fg_color=C['border']).pack(fill='x', padx=20 if self._compact_mode else 24)

        btn_row = ctk.CTkFrame(card, fg_color='transparent')
        btn_row.pack(fill='x', padx=20 if self._compact_mode else 24, pady=16)

        ctk.CTkButton(btn_row, text='Annuler', width=120, height=40,
                      fg_color='transparent',
                      border_color=C['border'], border_width=1,
                      text_color=C['text_lo'],
                      hover_color=C['bg_section'],
                      command=self.destroy).pack(side='top' if self._compact_mode else 'left',
                                                fill='x' if self._compact_mode else 'none',
                                                pady=(0, 8) if self._compact_mode else 0)

        self.btn_save = ctk.CTkButton(
            btn_row, text='  Enregistrer  ', height=40,
            fg_color=C['accent'], hover_color=C['accent_dim'],
            text_color='#000000',
            font=ctk.CTkFont(size=13, weight='bold'),
            corner_radius=8,
            command=self._enregistrer
        )
        self.btn_save.pack(side='top' if self._compact_mode else 'right',
                           fill='x' if self._compact_mode else 'none')

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

        try:
            mois_date = (parse_mois_saisie(mois) or date.fromisoformat(mois)).replace(day=1)
            self._set_month_picker_from_date(mois_date)
        except (ValueError, AttributeError):
            # Si la conversion échoue, laisser la valeur par défaut
            pass

        self.field_montant_souscrit.entry.delete(0, 'end')
        self.field_montant_souscrit.entry.insert(0, str(montant_total))

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
            state='readonly',
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

    def _get_selected_month_date(self) -> date:
        """Construit la date de mois à partir du choix guidé."""
        selected_date = parse_mois_saisie(self.combo_mois.get())
        if selected_date:
            return selected_date.replace(day=1)
        return date.today().replace(day=1)

    def _set_month_picker_from_date(self, selected_date: date):
        """Positionne le sélecteur guidé sur une date donnée."""
        selected_date = selected_date.replace(day=1)
        month_choice = format_month_choice(selected_date)
        month_values = list(self.combo_mois.cget("values") or [])
        if month_choice not in month_values:
            self.combo_mois.configure(values=[month_choice, *month_values])
        self.combo_mois.set(month_choice)
        self._update_month_preview()

    def _update_month_preview(self):
        """Met à jour l'aperçu visuel du mois sélectionné."""
        selected_month = self._get_selected_month_date()
        self.month_preview_label.configure(text=format_month_label(selected_month))
        self.month_preview_subtitle.configure(
            text=f"Sera enregistré comme {selected_month.isoformat()}"
        )

    # ── Logique d'enregistrement ───────────────────────────────────────────────

    def _enregistrer(self):
        # Forcer la validation de tous les champs obligatoires
        fields = [self.field_nom, self.field_prenom,
                  self.field_montant_souscrit]
        errors = [f for f in fields if not f.is_valid()]

        # Valider le téléphone seulement s'il est rempli
        if self.field_telephone.get() and not self.field_telephone.is_valid():
            errors.append(self.field_telephone)

        # Valider le montant payé seulement s'il est rempli
        if self.field_montant_paye.get() and not self.field_montant_paye.is_valid():
            errors.append(self.field_montant_paye)

        if errors:
            errors[0].focus()   # amener le focus sur le premier champ en erreur
            return

        # Extraire la date du combo mois
        mois = self._get_selected_month_date().isoformat()

        # Récupérer le montant souscrit (obligatoire)
        montant_souscrit = self.field_montant_souscrit.get()

        montant_paye = self.field_montant_paye.get()
        if not montant_paye:
            montant_paye = None

        avance = self.field_avance.get()
        if not avance:
            avance = None

        # Désactiver le bouton le temps de l'insertion
        self.btn_save.configure(state='disabled', text='Enregistrement…')
        self.update_idletasks()

        if self.mode_edition:
            success, message = modifier_souscription(
                self.paiement_id,
                self.field_nom.get(),
                self.field_prenom.get(),
                self.field_telephone.get(),
                mois,
                montant_souscrit,
                self.combo_devise.get(),
                statut_souscription=self.combo_statut_souscription.get(),
                montant_paye=montant_paye,
                avance=avance,
            )
        else:
            success, message, details = inserer_souscription(
                self.field_nom.get(),
                self.field_prenom.get(),
                self.field_telephone.get(),
                mois,
                montant_souscrit,
                self.combo_devise.get(),
                statut_souscription=self.combo_statut_souscription.get(),
                montant_paye=montant_paye,
                avance=avance,
                return_details=True,
            )

        if success:
            messagebox.showinfo('Succès', message)
            self.destroy()
            if self.mode_edition:
                self.callback_maj_tableau()
            else:
                _appeler_callback(self.callback_maj_tableau, details)
        else:
            self.btn_save.configure(state='normal', text='  Enregistrer  ')
            messagebox.showerror('Erreur base de données', message)
