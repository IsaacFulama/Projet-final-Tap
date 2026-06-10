import customtkinter as ctk
from fpdf import FPDF
from tkinter import messagebox, ttk, filedialog
import os

# Import des fonctions métier (à adapter selon ton main.py)
from main import recuperer_inventaire, inserer_souscription

# Configuration de base CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AppGestionLoyers(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Système de Gestion des Souscriptions")
        self.geometry("1050x700")
        self.minsize(800, 500)

        self._configurer_style_tableau()
        self._construire_interface()
        self.charger_donnees() 

    def _configurer_style_tableau(self):
        """Harmonise le Treeview standard avec le mode sombre de CustomTkinter."""
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#2b2b2b", 
                        foreground="white", 
                        rowheight=25, 
                        fieldbackground="#2b2b2b", 
                        bordercolor="#343638", 
                        borderwidth=0)
        style.map('Treeview', background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", 
                        background="#565b5e", 
                        foreground="white", 
                        relief="flat")
        style.map("Treeview.Heading", background=[('active', '#3484F0')])

    def _construire_interface(self):
        """Sépare la construction de l'interface pour un code plus lisible."""
        # --- PANEL LATÉRAL (Menu) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.pack(side="left", fill="y")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Gestion Loyers", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(padx=20, pady=(20, 30))
        
        self.btn_ajouter = ctk.CTkButton(self.sidebar_frame, text="Nouveau Paiement", command=self.ouvrir_formulaire)
        self.btn_ajouter.pack(padx=20, pady=10)
        
        self.btn_exporter = ctk.CTkButton(self.sidebar_frame, text="Exporter PDF", fg_color="#27ae60", hover_color="#2ecc71", command=self.generer_pdf)
        self.btn_exporter.pack(padx=20, pady=10)

        # --- ZONE PRINCIPALE ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        
        # Filtres
        self.filtres_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.filtres_frame.pack(fill="x", pady=(0, 10))
        
        self.entry_recherche = ctk.CTkEntry(self.filtres_frame, placeholder_text="Rechercher par Nom...", width=200)
        self.entry_recherche.pack(side="left", padx=(0, 10))
        
        self.combo_statut = ctk.CTkComboBox(self.filtres_frame, values=["Tous", "Payé", "Litigieux"], width=150)
        self.combo_statut.pack(side="left", padx=10)
        
        self.btn_filtrer = ctk.CTkButton(self.filtres_frame, text="Filtrer", command=self.charger_donnees, width=100)
        self.btn_filtrer.pack(side="left", padx=10)

        # Zone du Tableau
        self.table_frame = ctk.CTkFrame(self.main_frame)
        self.table_frame.pack(fill="both", expand=True)
        
        colonnes = ("Nom", "Prénom", "Téléphone", "Montant", "Devise", "Mois", "Statut")
        self.tree = ttk.Treeview(self.table_frame, columns=colonnes, show="headings")
        
        for col in colonnes:
            self.tree.heading(col, text=col)
            # Ajustement dynamique des largeurs
            largeur = 80 if col in ("Montant", "Devise", "Statut") else 120
            self.tree.column(col, width=largeur, anchor="center")
            
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)

    def ouvrir_formulaire(self):
        """Gère la fenêtre d'insertion de manière stricte (Modale)."""
        form_window = ctk.CTkToplevel(self)
        form_window.title("Nouveau Paiement")
        form_window.geometry("400x550")
        form_window.resizable(False, False)
        
        # Rend la fenêtre modale (bloque les clics sur la fenêtre principale)
        form_window.transient(self)
        form_window.grab_set()
        
        # Conteneur centré
        frame = ctk.CTkFrame(form_window, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=40, pady=20)

        entries = {}
        champs = [("Nom", "entry"), ("Prénom", "entry"), ("Téléphone", "entry"), 
                  ("Mois", "entry"), ("Montant", "entry"), 
                  ("Devise", ["USD", "EUR", "XAF", "CAD"]), 
                  ("Statut", ["Payé", "Litigieux"])]

        for nom_champ, type_champ in champs:
            ctk.CTkLabel(frame, text=f"{nom_champ}:", anchor="w").pack(fill="x", pady=(5, 0))
            if isinstance(type_champ, list):
                widget = ctk.CTkComboBox(frame, values=type_champ)
                widget.set(type_champ[0])
            else:
                widget = ctk.CTkEntry(frame)
            widget.pack(fill="x", pady=(0, 10))
            entries[nom_champ] = widget

        def valider_et_enregistrer():
            valeurs = {k: v.get().strip() for k, v in entries.items()}
            
            # 1. Vérification des champs vides
            if not all([valeurs["Nom"], valeurs["Prénom"], valeurs["Téléphone"], valeurs["Mois"], valeurs["Montant"]]):
                messagebox.showerror("Erreur", "Veuillez remplir tous les champs obligatoires", parent=form_window)
                return
            
            # 2. Validation stricte du montant (Évite les injections et erreurs SQL)
            try:
                montant_propre = float(valeurs["Montant"].replace(",", "."))
                if montant_propre <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Format Invalide", "Le montant doit être un nombre positif valide.", parent=form_window)
                return

            # 3. Insertion
            success, message = inserer_souscription(
                valeurs["Nom"], valeurs["Prénom"], valeurs["Téléphone"], 
                valeurs["Mois"], montant_propre, valeurs["Devise"], valeurs["Statut"]
            )
            
            if success:
                messagebox.showinfo("Succès", message, parent=form_window)
                form_window.destroy()
                self.charger_donnees()
            else:
                messagebox.showerror("Erreur Système", message, parent=form_window)
        
        btn_enregistrer = ctk.CTkButton(frame, text="Enregistrer", command=valider_et_enregistrer, fg_color="#27ae60", hover_color="#2ecc71")
        btn_enregistrer.pack(fill="x", pady=20)

    def charger_donnees(self):
        nom = self.entry_recherche.get().strip()
        statut = self.combo_statut.get()
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        try:
            donnees = recuperer_inventaire(filtre_nom=nom, filtre_statut=statut)
            for row in donnees:
                self.tree.insert("", "end", values=row)
        except Exception as e:
            messagebox.showerror("Erreur de base de données", f"Impossible de charger les données: {e}")

    def generer_pdf(self):
        """Génère le PDF de manière sécurisée avec choix du répertoire."""
        lignes = self.tree.get_children()
        if not lignes:
            messagebox.showwarning("Attention", "Le tableau est vide, rien à exporter.")
            return

        # Demande à l'utilisateur où sauvegarder le fichier
        chemin_fichier = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("Fichiers PDF", "*.pdf")],
            initialfile="rapport_souscriptions.pdf",
            title="Enregistrer le rapport PDF"
        )

        if not chemin_fichier:
            return  # L'utilisateur a annulé

        try:
            pdf = FPDF()
            pdf.add_page()
            
            # Titre
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, txt="Rapport des Souscriptions", ln=True, align='C')
            pdf.ln(10)
            
            # Calcul dynamique des largeurs (Total: 190mm)
            largeurs = [30, 30, 35, 25, 20, 25, 25]
            en_tetes = ["Nom", "Prenom", "Telephone", "Montant", "Devise", "Mois", "Statut"]
            
            # En-têtes
            pdf.set_font("Arial", 'B', 10)
            pdf.set_fill_color(200, 200, 200)
            for w, txt in zip(largeurs, en_tetes):
                pdf.cell(w, 10, txt=txt, border=1, fill=True, align='C')
            pdf.ln()
            
            # Données
            pdf.set_font("Arial", size=9)
            for item in lignes:
                row = self.tree.item(item)['values']
                for w, val in zip(largeurs, row):
                    # Forcer la conversion en string pour FPDF et éviter les erreurs d'encodage
                    val_str = str(val).encode('latin-1', 'replace').decode('latin-1')
                    pdf.cell(w, 8, txt=val_str, border=1, align='C')
                pdf.ln()
            
            pdf.output(chemin_fichier)
            messagebox.showinfo("Succès", f"Le PDF a été généré avec succès :\n{os.path.basename(chemin_fichier)}")
            
        except PermissionError:
            messagebox.showerror("Erreur d'accès", "Impossible de sauvegarder. Le fichier est probablement ouvert dans un autre programme.")
        except Exception as e:
            messagebox.showerror("Erreur critique", f"Une erreur est survenue lors de la création du PDF : {e}")

if __name__ == "__main__":
    app = AppGestionLoyers()
    app.mainloop()