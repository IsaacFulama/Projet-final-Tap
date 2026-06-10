import customtkinter as ctk
from tkinter import messagebox, filedialog
from fpdf import FPDF
from collections import Counter
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
    def _build_summary(cls, lignes: List[Tuple]) -> Dict[str, object]:
        montants_souscrits = 0.0
        montants_verses = 0.0
        souscripteurs_en_regle = 0
        souscripteurs_litigieux = 0
        devises = Counter()

        for ligne in lignes:
            if len(ligne) < 6:
                continue

            montant = cls._parse_montant(ligne[3])
            devise = str(ligne[4]).strip().upper()
            statut = str(ligne[5]).strip()

            montants_souscrits += montant
            devises[devise] += 1

            if statut == "Payé":
                montants_verses += montant
                souscripteurs_en_regle += 1
            elif statut == "Litigieux":
                souscripteurs_litigieux += 1

        return {
            "montants_souscrits": montants_souscrits,
            "montants_verses": montants_verses,
            "souscripteurs_en_regle": souscripteurs_en_regle,
            "souscripteurs_litigieux": souscripteurs_litigieux,
            "montant_restant": max(montants_souscrits - montants_verses, 0.0),
            "devises": devises,
        }

    @staticmethod
    def _write_summary_row(pdf: FPDF, label: str, value: str) -> None:
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(237, 242, 247)
        pdf.cell(120, 9, label, border=1, fill=True)
        pdf.cell(0, 9, value, border=1, ln=True, fill=True)

    @classmethod
    def generer_rapport(cls, lignes: List[Tuple], filepath: str) -> bool:
        try:
            summary = cls._build_summary(lignes)
            devises = summary["devises"]
            devise_label = ""
            if len(devises) == 1:
                devise_label = next(iter(devises.keys()))
            elif len(devises) > 1:
                devise_label = "MULTI-DEVISES"

            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            # Fond sombre
            pdf.set_fill_color(11, 15, 20)
            pdf.rect(0, 0, 210, 297, 'F')
            
            # Titre
            pdf.set_font('Arial', 'B', 20)
            pdf.set_text_color(201, 168, 76)
            pdf.cell(0, 16, 'TAP - Rapport des Souscriptions', ln=True, align='C')
            pdf.set_font('Arial', '', 10)
            pdf.set_text_color(107, 124, 147)
            pdf.cell(0, 7, 'Synthese du recouvrement sur les lignes filtrees', ln=True, align='C')
            pdf.ln(10)

            pdf.set_font('Arial', 'B', 12)
            pdf.set_text_color(237, 242, 247)
            pdf.cell(0, 10, 'Synthese du recouvrement', ln=True)
            pdf.set_fill_color(26, 35, 50)

            devise_suffix = f" {devise_label}" if devise_label and devise_label != "MULTI-DEVISES" else ""
            if devise_label == "MULTI-DEVISES":
                pdf.set_font('Arial', '', 9)
                pdf.set_text_color(107, 124, 147)
                pdf.multi_cell(0, 6, 'Note: plusieurs devises sont presentes dans ce filtre. Les montants ci-dessous sont additionnes sur les valeurs saisies.')
                pdf.ln(2)

            cls._write_summary_row(
                pdf,
                'Total des montants souscrits',
                f"{summary['montants_souscrits']:,.0f}{devise_suffix}"
            )
            cls._write_summary_row(
                pdf,
                'Total des montants effectivement verses',
                f"{summary['montants_verses']:,.0f}{devise_suffix}"
            )
            cls._write_summary_row(
                pdf,
                'Nombre de souscripteurs en regle',
                str(summary['souscripteurs_en_regle'])
            )
            cls._write_summary_row(
                pdf,
                'Nombre de souscripteurs litigieux',
                str(summary['souscripteurs_litigieux'])
            )
            cls._write_summary_row(
                pdf,
                'Montant global restant a recouvrer',
                f"{summary['montant_restant']:,.0f}{devise_suffix}"
            )
            pdf.ln(10)
            
            # En-têtes
            pdf.set_font('Arial', 'B', 10)
            pdf.set_text_color(255, 255, 255)
            pdf.set_fill_color(40, 40, 60)
            col_w = [32, 32, 38, 30, 20, 30]
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
                
                for j, val in enumerate(ligne[:6]):
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
        
        ctk.CTkLabel(self, text="Exporter le filtre courant ?", font=("Arial", 16)).pack(pady=28)
        ctk.CTkLabel(
            self,
            text="Le rapport inclut la synthese du recouvrement et le detail filtre.",
            font=("Arial", 10),
        ).pack(pady=(0, 12))
        
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
