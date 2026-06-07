import customtkinter as ctk
from tkinter import messagebox, filedialog
from fpdf import FPDF
from datetime import datetime
import database

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

class ExportPDFDialog(ctk.CTkToplevel):
    def __init__(self, parent, table_data=None):
        super().__init__(parent)
        self.table_data = table_data  # Données pré-filtrées depuis le tableau
        
        self.title('TAP · Export PDF')
        self.geometry('520x580')
        self.configure(fg_color=C['bg_deep'])
        self.resizable(False, False)
        
        # Modalité correcte
        self.transient(parent)
        self.grab_set()
        
        # Fermeture clavier
        self.bind('<Escape>', lambda _: self.destroy())
        
        self._build_ui()
    
    def _build_ui(self):
        card = ctk.CTkFrame(self, fg_color=C['bg_card'], corner_radius=16,
                            border_width=1, border_color=C['border'])
        card.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Header
        header = ctk.CTkFrame(card, fg_color='transparent')
        header.pack(fill='x', padx=24, pady=(24, 16))
        
        ctk.CTkLabel(header, text='Export PDF',
                     font=ctk.CTkFont(family='Georgia', size=22, weight='bold'),
                     text_color=C['accent']).pack(anchor='w')
        ctk.CTkLabel(header, text='Filtrez les données à exporter',
                     font=ctk.CTkFont(size=11),
                     text_color=C['text_lo']).pack(anchor='w', pady=(4, 0))
        
        ctk.CTkFrame(card, height=1, fg_color=C['border']).pack(fill='x', padx=24)
        
        # Formulaire de filtres
        form = ctk.CTkFrame(card, fg_color='transparent')
        form.pack(fill='both', expand=True, padx=24, pady=(16, 0))
        
        # Filtre par nom
        ctk.CTkLabel(form, text='Nom du locataire',
                     font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_hi']).pack(anchor='w', pady=(0, 6))
        self.entry_nom = ctk.CTkEntry(form, placeholder_text='Laisser vide pour tous',
                                      fg_color=C['bg_section'],
                                      border_color=C['border'],
                                      text_color=C['text_hi'],
                                      placeholder_text_color=C['text_lo'])
        self.entry_nom.pack(fill='x', pady=(0, 12))
        
        # Filtre par statut
        ctk.CTkLabel(form, text='Statut',
                     font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_hi']).pack(anchor='w', pady=(0, 6))
        self.combo_statut = ctk.CTkComboBox(
            form,
            values=['Tous', 'Payé', 'Litigieux', 'En attente'],
            fg_color=C['bg_section'],
            border_color=C['border'],
            text_color=C['text_hi'],
            dropdown_fg_color=C['bg_section'],
            dropdown_text_color=C['text_hi'],
            dropdown_hover_color=C['border'],
            button_color=C['border'],
            button_hover_color=C['accent_dim']
        )
        self.combo_statut.set('Tous')
        self.combo_statut.pack(fill='x', pady=(0, 12))
        
        # Filtre par mois
        ctk.CTkLabel(form, text='Nom du mois',
                     font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_hi']).pack(anchor='w', pady=(0, 6))
        self.entry_mois = ctk.CTkEntry(form, placeholder_text='ex: Janvier, 2026',
                                      fg_color=C['bg_section'],
                                      border_color=C['border'],
                                      text_color=C['text_hi'],
                                      placeholder_text_color=C['text_lo'])
        self.entry_mois.pack(fill='x', pady=(0, 16))
        
        # Info
        info_frame = ctk.CTkFrame(form, fg_color=C['bg_section'], corner_radius=8)
        info_frame.pack(fill='x', pady=(0, 16))
        ctk.CTkLabel(info_frame, text='ℹ️  Laissez le mois vide pour exporter toutes les données',
                     font=ctk.CTkFont(size=10),
                     text_color=C['text_lo']).pack(pady=10)
        
        # Boutons
        ctk.CTkFrame(card, height=1, fg_color=C['border']).pack(fill='x', padx=24)
        
        btn_row = ctk.CTkFrame(card, fg_color='transparent')
        btn_row.pack(fill='x', padx=24, pady=16)
        
        ctk.CTkButton(btn_row, text='Annuler', width=120, height=40,
                      fg_color='transparent',
                      border_color=C['border'], border_width=1,
                      text_color=C['text_lo'],
                      hover_color=C['bg_section'],
                      command=self.destroy).pack(side='left')
        
        self.btn_export = ctk.CTkButton(
            btn_row, text='  Exporter PDF  ', height=40,
            fg_color=C['accent'], hover_color=C['accent_dim'],
            text_color='#000000',
            font=ctk.CTkFont(size=13, weight='bold'),
            corner_radius=8,
            command=self.exporter_pdf
        )
        self.btn_export.pack(side='right')
    
    def exporter_pdf(self):
        nom = self.entry_nom.get().strip()
        statut = self.combo_statut.get()
        mois_filtre = self.entry_mois.get().strip()
        
        # Utiliser les données du tableau si disponibles, sinon utiliser les filtres de la base de données
        if self.table_data:
            lignes = self.table_data
            # Filtrer côté client si des filtres supplémentaires sont appliqués
            if nom:
                lignes = [l for l in lignes if nom.lower() in str(l[0]).lower() or nom.lower() in str(l[1]).lower()]
            if statut != 'Tous':
                lignes = [l for l in lignes if str(l[5]) == statut]
            if mois_filtre:
                lignes = [l for l in lignes if mois_filtre.lower() in str(l[2]).lower()]
        else:
            # Récupérer les données filtrées depuis la base de données
            lignes = database.get_souscriptions(nom, statut)
            if mois_filtre:
                lignes = [l for l in lignes if mois_filtre.lower() in str(l[2]).lower()]
        
        if not lignes:
            messagebox.showwarning('Avertissement', 'Aucune donnée trouvée avec ces filtres.\nEssayez avec moins de filtres.')
            return
        
        # Générer le PDF
        self._generer_pdf(lignes, nom, statut, mois_filtre)
    
    def _valider_date(self, date_str):
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def _generer_pdf(self, lignes, nom, statut, mois_filtre):
        pdf = FPDF()
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
        pdf.cell(0, 8, 'Export filtré des paiements de loyers', ln=True, align='C')
        pdf.ln(6)
        
        # Filtres appliqués
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(107, 124, 147)
        filtres = []
        if nom:
            filtres.append(f'Nom: {nom}')
        if statut != 'Tous':
            filtres.append(f'Statut: {statut}')
        if mois_filtre:
            filtres.append(f'Mois: {mois_filtre}')
        
        if filtres:
            filtre_text = ' | '.join(filtres)
            pdf.cell(0, 6, f'Filtres: {filtre_text}', ln=True, align='C')
        
        pdf.ln(8)
        
        # En-têtes du tableau
        col_w = [35, 35, 30, 30, 18, 28]
        headers = ['Nom', 'Prénom', 'Mois', 'Montant', 'Dev', 'Statut']
        
        pdf.set_fill_color(26, 35, 50)
        pdf.set_text_color(201, 168, 76)
        pdf.set_font('Arial', 'B', 9)
        for w, h in zip(col_w, headers):
            pdf.cell(w, 10, h, border=0, fill=True, align='C')
        pdf.ln()
        
        # Lignes de données
        pdf.set_font('Arial', '', 9)
        for i, ligne in enumerate(lignes):
            r, g, b = (22, 30, 40) if i % 2 == 0 else (26, 35, 50)
            pdf.set_fill_color(r, g, b)
            pdf.set_text_color(237, 242, 247)
            
            # ligne: nom, prenom, mois, montant, devise, statut (exclure date_creation)
            ligne_sans_date = ligne[:6]  # Prendre seulement les 6 premières colonnes
            for j, (w, val) in enumerate(zip(col_w, ligne_sans_date)):
                align = 'R' if j == 3 else ('C' if j > 2 else 'L')
                pdf.cell(w, 9, str(val), border=0, fill=True, align=align)
            pdf.ln()
        
        # Calculer les totaux par devise
        totaux_par_devise = {}
        for ligne in lignes:
            devise = str(ligne[4]).upper()
            montant = float(str(ligne[3]).replace(",", "."))
            if devise not in totaux_par_devise:
                totaux_par_devise[devise] = 0
            totaux_par_devise[devise] += montant
        
        # Afficher les totaux
        pdf.ln(10)
        pdf.set_fill_color(26, 35, 50)
        pdf.set_text_color(201, 168, 76)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 10, 'TOTAUX PAR DEVISE', border=0, fill=True, align='C')
        pdf.ln()
        
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(237, 242, 247)
        for devise, total in sorted(totaux_par_devise.items()):
            pdf.cell(0, 8, f'{devise}: {total:,.2f}', border=0, align='C')
            pdf.ln()
        
        # Pied de page
        pdf.set_y(285)
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(107, 124, 147)
        date_gen = datetime.now().strftime('%d/%m/%Y à %H:%M')
        pdf.cell(0, 6, f'Généré le {date_gen}', ln=True, align='C')
        
        # Sauvegarder avec choix de l'emplacement
        nom_fichier_defaut = f'TAP_Export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        nom_fichier = filedialog.asksaveasfilename(
            defaultextension='.pdf',
            filetypes=[('Fichiers PDF', '*.pdf')],
            initialfile=nom_fichier_defaut,
            title='Enregistrer le PDF'
        )
        
        if not nom_fichier:
            return  # Utilisateur a annulé
        
        try:
            pdf.output(nom_fichier)
            messagebox.showinfo('Succès', f'✅ PDF exporté : {nom_fichier}')
            self.destroy()
        except Exception as e:
            messagebox.showerror('Erreur', f'Erreur lors de l\'export : {e}')
