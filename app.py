import customtkinter as ctk
import mysql.connector
from fpdf import FPDF
from tkinter import messagebox

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

        # Zone du Tableau (Ici tu intégrerais un Treeview de Tkinter classique pour les colonnes)
        # ... 

    def ouvrir_formulaire(self):
        # Logique pour ouvrir une fenêtre modale d'enregistrement
        print("Ouverture du formulaire d'enregistrement...")
        pass

    def charger_donnees(self):
        # Logique de connexion à XAMPP et de requête SELECT avec WHERE selon les filtres
        # nom = self.entry_recherche.get()
        # statut = self.combo_statut.get()
        pass

    def generer_pdf(self):
        # Récupération des données actuellement filtrées
        # Logique avec FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Rapport des Souscriptions", ln=True, align='C')
        
        # Exemple de boucle sur les données
        pdf.cell(200, 10, txt="Nom: Doe | Montant: 500 USD | Statut: Litigieux", ln=True)
        
        pdf.output("rapport_filtre.pdf")
        messagebox.showinfo("Succès", "Le PDF a été généré avec succès dans le dossier courant.")

if __name__ == "__main__":
    app = AppGestionLoyers()
    app.mainloop()