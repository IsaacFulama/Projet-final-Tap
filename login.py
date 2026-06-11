import customtkinter as ctk
from tkinter import messagebox

# Palette de couleurs (même que main.py)
C = {
    'bg_deep':    '#0B0F14',
    'bg_panel':   '#111820',
    'bg_card':    '#161E28',
    'bg_section': '#1A2332',
    'border':     '#243042',
    'accent':     '#C9A84C',
    'accent_dim': '#8A7035',
    'text_hi':    '#EDF2F7',
    'text_lo':    '#6B7C93',
    'green':      '#3ECF8E',
    'orange':     '#F59E0B',
    'blue':       '#3B82F6',
    'red':        '#EF4444',
}

class LoginDialog(ctk.CTk):
    def __init__(self, callback_success):
        super().__init__()
        self.callback_success = callback_success
        self.authenticated = False
        self.password_visible = False
        
        self.title('TAP · Gestion des Loyers')
        self._set_initial_geometry()
        self.configure(fg_color=C['bg_deep'])
        self.resizable(True, True)
        self.minsize(380, 340)
        
        # Centrer la fenêtre
        self.center_window()
        
        # Fermeture clavier
        self.bind('<Escape>', lambda _: self.destroy())
        
        self._build_ui()
    
    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def _set_initial_geometry(self):
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(max(int(screen_width * 0.34), 420), 560)
        height = min(max(int(screen_height * 0.55), 380), 520)
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def _build_ui(self):
        card = ctk.CTkFrame(self, fg_color=C['bg_card'], corner_radius=16,
                            border_width=1, border_color=C['border'])
        card.pack(fill='both', expand=True, padx=30, pady=30)
        
        # Header
        header = ctk.CTkFrame(card, fg_color='transparent')
        header.pack(fill='x', padx=24, pady=(24, 20))
        
        ctk.CTkLabel(header, text='TAP',
                     font=ctk.CTkFont(family='Georgia', size=36, weight='bold'),
                     text_color=C['accent']).pack(anchor='center')
        ctk.CTkLabel(header, text='GESTION LOYERS',
                     font=ctk.CTkFont(size=12, weight='bold'),
                     text_color=C['text_lo']).pack(anchor='center', pady=(4, 0))
        
        ctk.CTkFrame(card, height=1, fg_color=C['border']).pack(fill='x', padx=24, pady=(0, 20))
        
        # Formulaire de connexion
        form = ctk.CTkFrame(card, fg_color='transparent')
        form.pack(fill='both', expand=True, padx=24, pady=(0, 20))
        
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
            width=90,
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

    def _toggle_password(self):
        self.password_visible = not self.password_visible
        self.entry_password.configure(show='' if self.password_visible else '•')
        self.btn_toggle_password.configure(text='Masquer' if self.password_visible else 'Afficher')
    
    def connexion(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        
        # Vérification des identifiants
        if username == 'TAPADM' and password == 'TAPADM':
            self.authenticated = True
            self.quit()  # Quitter la boucle principale au lieu de destroy
        else:
            messagebox.showerror('Erreur', 'Nom d\'utilisateur ou mot de passe incorrect')
            self.entry_password.delete(0, 'end')
            self.entry_password.focus()
