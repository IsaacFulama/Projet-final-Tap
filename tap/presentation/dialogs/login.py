import customtkinter as ctk
from tkinter import messagebox
from typing import Optional

from tap.config.theme import C
from tap.config.responsive import clamp_window_geometry, detect_screen_profile
from tap.core.auth import authenticate_user, auth_manager


class LoginDialog(ctk.CTk):
    """Dialogue de connexion sécurisée avec gestion des tentatives."""
    
    def __init__(self, parent: Optional[ctk.CTk] = None):
        super().__init__()
        self.parent = parent
        self.authenticated = False
        self.username = ""
        self.user_role = "agent"
        self.password_visible = False
        self.attempts_remaining = 5
        self._screen = detect_screen_profile()
        self._compact_mode = self._screen.width < 1100
        
        self.title('TAP · Gestion des Loyers')
        self._set_initial_geometry()
        self.configure(fg_color=C['bg_deep'])
        self.resizable(True, True)
        self.minsize(
            max(300, min(350, self._screen.width - 20)),
            max(280, min(320, self._screen.height - 20)),
        )
        
        # Centrer la fenêtre
        self.center_window()
        
        # Fermeture clavier
        self.bind('<Escape>', lambda _: self.destroy())
        
        self._build_ui()
    
    def center_window(self) -> None:
        """Centre la fenêtre sur l'écran."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def _set_initial_geometry(self) -> None:
        """Définit la géométrie initiale de la fenêtre de manière responsive."""
        self.update_idletasks()
        screen_width = self._screen.width
        screen_height = self._screen.height

        if min(screen_width, screen_height) < 900:
            width_ratio, height_ratio = 0.92, 0.84
        elif screen_width < 1366:
            width_ratio, height_ratio = 0.40, 0.56
        elif screen_width < 1920:
            width_ratio, height_ratio = 0.34, 0.52
        else:
            width_ratio, height_ratio = 0.28, 0.48

        width, height = clamp_window_geometry(
            screen_width,
            screen_height,
            width_ratio=width_ratio,
            height_ratio=height_ratio,
            min_width=350,
            min_height=320,
        )
        
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def _build_ui(self) -> None:
        """Construit l'interface utilisateur du dialogue de connexion."""
        card = ctk.CTkFrame(self, fg_color=C['bg_card'], corner_radius=16,
                            border_width=1, border_color=C['border'])
        card.pack(fill='both', expand=True, padx=18 if self._compact_mode else 30,
                  pady=18 if self._compact_mode else 30)
        
        # Header
        header = ctk.CTkFrame(card, fg_color='transparent')
        header.pack(fill='x', padx=20 if self._compact_mode else 24, pady=(20 if self._compact_mode else 24, 20))
        
        ctk.CTkLabel(header, text='TAP',
                     font=ctk.CTkFont(family='Georgia', size=32 if self._compact_mode else 36, weight='bold'),
                     text_color=C['accent']).pack(anchor='center')
        ctk.CTkLabel(header, text='GESTION LOYERS',
                     font=ctk.CTkFont(size=12, weight='bold'),
                     text_color=C['text_lo']).pack(anchor='center', pady=(4, 0))
        
        ctk.CTkFrame(card, height=1, fg_color=C['border']).pack(fill='x', padx=20 if self._compact_mode else 24, pady=(0, 20))
        
        # Formulaire de connexion
        form = ctk.CTkFrame(card, fg_color='transparent')
        form.pack(fill='both', expand=True, padx=20 if self._compact_mode else 24, pady=(0, 20))
        
        # Nom d'utilisateur
        ctk.CTkLabel(form, text='Nom d\'utilisateur',
                     font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_hi']).pack(anchor='w', pady=(0, 6))
        self.entry_username = ctk.CTkEntry(
            form, placeholder_text='Entrez votre nom d\'utilisateur',
            fg_color=C['bg_section'],
            border_color=C['border'],
            text_color=C['text_hi'],
            placeholder_text_color=C['text_lo'],
            height=40
        )
        self.entry_username.pack(fill='x', pady=(0, 16))
        self.entry_username.bind('<Return>', lambda _: self.entry_password.focus())
        
        # Mot de passe
        ctk.CTkLabel(form, text='Mot de passe',
                     font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_hi']).pack(anchor='w', pady=(0, 6))
        password_row = ctk.CTkFrame(form, fg_color='transparent')
        password_row.pack(fill='x', pady=(0, 20))
        self.entry_password = ctk.CTkEntry(
            password_row, placeholder_text='Entrez votre mot de passe',
            fg_color=C['bg_section'],
            border_color=C['border'],
            text_color=C['text_hi'],
            placeholder_text_color=C['text_lo'],
            show='•',
            height=40
        )
        self.entry_password.pack(side='left', fill='x', expand=True, padx=(0, 8))
        self.entry_password.bind('<Return>', lambda _: self.connexion())
        self.btn_toggle_password = ctk.CTkButton(
            password_row,
            text='Afficher',
            width=80 if self._compact_mode else 90,
            height=40,
            fg_color=C['bg_section'],
            hover_color=C['border'],
            text_color=C['text_hi'],
            corner_radius=8,
            command=self._toggle_password,
        )
        self.btn_toggle_password.pack(side='right')
        
        # Bouton de connexion
        self.btn_login = ctk.CTkButton(
            form, text='  Se connecter  ', height=42,
            fg_color=C['accent'], hover_color=C['accent_dim'],
            text_color='#000000',
            font=ctk.CTkFont(size=14, weight='bold'),
            corner_radius=8,
            command=self.connexion
        )
        self.btn_login.pack(fill='x', pady=(0, 16))
        
        # Info
        info_frame = ctk.CTkFrame(form, fg_color=C['bg_section'], corner_radius=8)
        info_frame.pack(fill='x')
        ctk.CTkLabel(info_frame, text='🔒  Accès réservé au personnel autorisé',
                     font=ctk.CTkFont(size=10),
                     text_color=C['text_lo']).pack(pady=12)
        self.after(100, self.entry_username.focus)

    def _toggle_password(self) -> None:
        """Bascule la visibilité du mot de passe."""
        self.password_visible = not self.password_visible
        self.entry_password.configure(show='' if self.password_visible else '•')
        self.btn_toggle_password.configure(text='Masquer' if self.password_visible else 'Afficher')
    
    def connexion(self) -> None:
        """Tente d'authentifier l'utilisateur avec les identifiants fournis."""
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        
        if not username or not password:
            messagebox.showerror('Erreur', 'Veuillez remplir tous les champs')
            return
        
        # Utiliser le système d'authentification sécurisé
        success, message = authenticate_user(username, password)
        
        if success:
            self.authenticated = True
            self.username = username
            self.user_role = (auth_manager.get_user_info(username) or {}).get("role", "agent")
            self.quit()  # Quitter la boucle principale au lieu de destroy
        else:
            self.attempts_remaining -= 1
            messagebox.showerror('Erreur', f'{message}\nTentatives restantes: {self.attempts_remaining}')
            self.entry_password.delete(0, 'end')
            self.entry_password.focus()
            
            # Désactiver le bouton si trop de tentatives
            if self.attempts_remaining <= 0:
                self.btn_login.configure(state='disabled', text='Trop de tentatives')
                self.after(30000, self._reenable_login_button)  # Réactiver après 30 secondes
    
    def _reenable_login_button(self) -> None:
        """Réactive le bouton de connexion après un délai."""
        self.btn_login.configure(state='normal', text='  Se connecter  ')
        self.attempts_remaining = 5
