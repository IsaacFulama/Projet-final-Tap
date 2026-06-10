import customtkinter as ctk
from tkinter import messagebox, filedialog
from fpdf import FPDF
from typing import List, Tuple, Dict

# Palette de couleurs
C = {'bg_deep': '#0B0F14', 'text_hi': '#EDF2F7', 'accent': '#C9A84C'}

class PDFReportService:
    @staticmethod
    def _parse_montant(valeur) -> float:
        try:
            return float(str(valeur).replace(" ", "").replace(",", "."))
        except (ValueError, TypeError):
            return 0.0

    @classmethod
    def generer_rapport(cls, lignes: List[Tuple], filepath: str) -> bool:
        try:
            pdf = FPDF()
            pdf.add_page()
            # Fond sombre
            pdf.set_fill_color(11, 15, 20)
            pdf.rect(0, 0, 210, 297, 'F')
            
            # Titre
            pdf.set_font('Arial', 'B', 20)
            pdf.set_text_color(201, 168, 76)
            pdf.cell(0, 16, 'TAP - Rapport des Souscriptions', ln=True, align='C')
            pdf.ln(10)
            
            # En-têtes
            pdf.set_font('Arial', 'B', 10)
            pdf.set_text_color(255, 255, 255)
            pdf.set_fill_color(40, 40, 60)
            col_w = [30, 30, 30, 30, 20, 30]
            headers = ['Nom', 'Prénom', 'Mois', 'Montant', 'Dev', 'Statut']
            
            for i, h in enumerate(headers):
                pdf.cell(col_w[i], 10, h, border=1, fill=True, align='C')
            pdf.ln()
            
            # Lignes
            pdf.set_font('Arial', '', 9)
            pdf.set_text_color(237, 242, 247)
            
            for i, ligne in enumerate(lignes):
                if pdf.get_y() > 250: pdf.add_page()
                
                # Alternance de couleurs
                r, g, b = (22, 30, 40) if i % 2 == 0 else (30, 40, 60)
                pdf.set_fill_color(r, g, b)
                
                for j, val in enumerate(ligne):
                    pdf.cell(col_w[j], 9, str(val), border=0, fill=True, align='C')
                pdf.ln()
            
            pdf.output(filepath)
            return True
        except Exception as e:
            print(f"Erreur PDF : {e}")
            return False

class ExportPDFDialog(ctk.CTkToplevel):
    def __init__(self, parent, table_data=None):
        super().__init__(parent)
        self.table_data = table_data
        self.title('TAP · Export PDF')
        self.geometry('400x200')
        self.configure(fg_color=C['bg_deep'])
        
        # REMPLACEMENT CRUCIAL : 
        # Utiliser transient au lieu de grab_set() pour éviter de bloquer l'interface parente
        self.transient(parent)
        self.focus_set()
        
        ctk.CTkLabel(self, text="Exporter les données en PDF ?", font=("Arial", 16)).pack(pady=30)
        
        ctk.CTkButton(self, text="Confirmer l'Export", command=self.exporter_pdf, 
                      fg_color=C['accent'], text_color="black").pack(pady=10)

    def exporter_pdf(self):
        path = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[("PDF files", "*.pdf")])
        if path:
            if PDFReportService.generer_rapport(self.table_data or [], path):
                messagebox.showinfo('Succès', 'Rapport généré avec succès.')
                self.destroy()
            else:
                messagebox.showerror('Erreur', 'Impossible de générer le fichier.')