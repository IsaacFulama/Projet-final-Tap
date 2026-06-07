import customtkinter as ctk
from fpdf import FPDF
from tkinter import messagebox, ttk
from main import recuperer_inventaire, inserer_souscription

# Configuration de base CustomTkinter
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class AppGestionLoyers(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Système de Gestion des Souscriptions")
        self.geometry("1000x700")

        # --- PANEL LATÉRAL (Menu) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.pack(side="left", fill="y")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Gestion Loyers", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.btn_ajouter = ctk.CTkButton(self.sidebar_frame, text="Nouveau Paiement", command=self.ouvrir_formulaire)
        self.btn_ajouter.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_exporter = ctk.CTkButton(self.sidebar_frame, text="Exporter PDF", fg_color="green", command=self.generer_pdf)
        self.btn_exporter.grid(row=2, column=0, padx=20, pady=10)

        # --- ZONE PRINCIPALE (Filtres et Tableau) ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        
        # Filtres
        self.filtres_frame = ctk.CTkFrame(self.main_frame)
        self.filtres_frame.pack(fill="x", padx=10, pady=10)
        
        self.entry_recherche = ctk.CTkEntry(self.filtres_frame, placeholder_text="Rechercher par Nom...")
        self.entry_recherche.pack(side="left", padx=10)
        
        self.combo_statut = ctk.CTkComboBox(self.filtres_frame, values=["Tous", "Payé", "Litigieux"])
        self.combo_statut.pack(side="left", padx=10)
        
        self.btn_filtrer = ctk.CTkButton(self.filtres_frame, text="Filtrer", command=self.charger_donnees)
        self.btn_filtrer.pack(side="left", padx=10)

        # Zone du Tableau
        self.table_frame = ctk.CTkFrame(self.main_frame)
        self.table_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Treeview pour afficher les données
        self.tree = ttk.Treeview(self.table_frame, columns=("Nom", "Prénom", "Téléphone", "Montant", "Devise", "Mois", "Statut"), show="headings")
        self.tree.heading("Nom", text="Nom")
        self.tree.heading("Prénom", text="Prénom")
        self.tree.heading("Téléphone", text="Téléphone")
        self.tree.heading("Montant", text="Montant")
        self.tree.heading("Devise", text="Devise")
        self.tree.heading("Mois", text="Mois")
        self.tree.heading("Statut", text="Statut")
        
        self.tree.column("Nom", width=100)
        self.tree.column("Prénom", width=100)
        self.tree.column("Téléphone", width=120)
        self.tree.column("Montant", width=80)
        self.tree.column("Devise", width=60)
        self.tree.column("Mois", width=80)
        self.tree.column("Statut", width=80)
        
        self.tree.pack(fill="both", expand=True)
        
        # Charger les données initiales
        self.charger_donnees() 

    def ouvrir_formulaire(self):
        # Créer une fenêtre modale pour l'enregistrement
        form_window = ctk.CTkToplevel(self)
        form_window.title("Nouveau Paiement")
        form_window.geometry("500x450")
        
        # Champs du formulaire
        ctk.CTkLabel(form_window, text="Nom:").pack(pady=5)
        entry_nom = ctk.CTkEntry(form_window)
        entry_nom.pack(pady=5)
        
        ctk.CTkLabel(form_window, text="Prénom:").pack(pady=5)
        entry_prenom = ctk.CTkEntry(form_window)
        entry_prenom.pack(pady=5)
        
        ctk.CTkLabel(form_window, text="Téléphone:").pack(pady=5)
        entry_telephone = ctk.CTkEntry(form_window)
        entry_telephone.pack(pady=5)
        
        ctk.CTkLabel(form_window, text="Mois:").pack(pady=5)
        entry_mois = ctk.CTkEntry(form_window)
        entry_mois.pack(pady=5)
        
        ctk.CTkLabel(form_window, text="Montant:").pack(pady=5)
        entry_montant = ctk.CTkEntry(form_window)
        entry_montant.pack(pady=5)
        
        ctk.CTkLabel(form_window, text="Devise:").pack(pady=5)
        combo_devise = ctk.CTkComboBox(form_window, values=["USD", "EUR", "XAF", "CAD"])
        combo_devise.pack(pady=5)
        combo_devise.set("XAF")
        
        ctk.CTkLabel(form_window, text="Statut:").pack(pady=5)
        combo_statut = ctk.CTkComboBox(form_window, values=["Payé", "Litigieux"])
        combo_statut.pack(pady=5)
        combo_statut.set("Payé")
        
        def enregistrer():
            nom = entry_nom.get()
            prenom = entry_prenom.get()
            telephone = entry_telephone.get()
            mois = entry_mois.get()
            montant = entry_montant.get()
            devise = combo_devise.get()
            statut = combo_statut.get()
            
            if not all([nom, prenom, telephone, mois, montant]):
                messagebox.showerror("Erreur", "Veuillez remplir tous les champs obligatoires")
                return
            
            success, message = inserer_souscription(nom, prenom, telephone, mois, montant, devise, statut)
            if success:
                messagebox.showinfo("Succès", message)
                form_window.destroy()
                self.charger_donnees()
            else:
                messagebox.showerror("Erreur", message)
        
        btn_enregistrer = ctk.CTkButton(form_window, text="Enregistrer", command=enregistrer, fg_color="green")
        btn_enregistrer.pack(pady=20)

    def charger_donnees(self):
        # Récupérer les filtres
        nom = self.entry_recherche.get()
        statut = self.combo_statut.get()
        
        # Effacer les données existantes dans le tableau
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Récupérer les données depuis la base de données
        donnees = recuperer_inventaire(filtre_nom=nom, filtre_statut=statut)
        
        # Afficher les données dans le Treeview
        for row in donnees:
            self.tree.insert("", "end", values=row)

    def generer_pdf(self):
        # Récupération des données actuellement affichées dans le tableau
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Rapport des Souscriptions", ln=True, align='C')
        pdf.ln(10)
        
        # En-têtes du tableau
        pdf.set_font("Arial", size=10, style='B')
        pdf.cell(30, 10, txt="Nom", border=1)
        pdf.cell(30, 10, txt="Prénom", border=1)
        pdf.cell(35, 10, txt="Téléphone", border=1)
        pdf.cell(25, 10, txt="Montant", border=1)
        pdf.cell(20, 10, txt="Devise", border=1)
        pdf.cell(25, 10, txt="Mois", border=1)
        pdf.cell(30, 10, txt="Statut", border=1, ln=True)
        
        # Données du tableau
        pdf.set_font("Arial", size=10)
        for item in self.tree.get_children():
            row = self.tree.item(item)['values']
            pdf.cell(30, 10, txt=str(row[0]), border=1)
            pdf.cell(30, 10, txt=str(row[1]), border=1)
            pdf.cell(35, 10, txt=str(row[2]), border=1)
            pdf.cell(25, 10, txt=str(row[3]), border=1)
            pdf.cell(20, 10, txt=str(row[4]), border=1)
            pdf.cell(25, 10, txt=str(row[5]), border=1)
            pdf.cell(30, 10, txt=str(row[6]), border=1, ln=True)
        
        pdf.output("rapport_filtre.pdf")
        messagebox.showinfo("Succès", "Le PDF a été généré avec succès dans le dossier courant.")

if __name__ == "__main__":
    app = AppGestionLoyers()
    app.mainloop()