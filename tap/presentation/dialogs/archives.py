import csv
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk

from tap.config.theme import C
from tap.core.archiver import executer_archivage
from tap.infrastructure.database.repository import get_archives, restaurer_archive
from tap.presentation.dialogs.export_pdf import ExportPDFDialog


class DialogArchives(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self._closed = False
        self.title("Archives des Mois Passés")
        self.geometry("900x600")
        self.minsize(800, 500)
        
        self.transient(master)
        self.grab_set()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(20, 10))

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="🗃️ Gestion des Archives",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(side="left")

        # Filters
        self.filters_frame = ctk.CTkFrame(self)
        self.filters_frame.pack(fill="x", padx=20, pady=10)

        self.entry_search = ctk.CTkEntry(
            self.filters_frame, placeholder_text="Rechercher par nom...", width=200
        )
        self.entry_search.pack(side="left", padx=10, pady=10)
        self.entry_search.bind("<KeyRelease>", lambda e: self.load_data())

        self.entry_mois = ctk.CTkEntry(
            self.filters_frame, placeholder_text="Mois (ex: 01/2023)...", width=150
        )
        self.entry_mois.pack(side="left", padx=10, pady=10)
        self.entry_mois.bind("<KeyRelease>", lambda e: self.load_data())

        self.btn_refresh = ctk.CTkButton(
            self.filters_frame, text="Actualiser", command=self.load_data, width=100
        )
        self.btn_refresh.pack(side="left", padx=10, pady=10)

        self.btn_archiver = ctk.CTkButton(
            self.filters_frame,
            text="Archiver maintenant",
            command=self.archiver_maintenant,
            width=150,
            fg_color=C["orange"],
            hover_color=C["orange"],
        )
        self.btn_archiver.pack(side="left", padx=10, pady=10)

        # Table
        self.table_frame = ctk.CTkFrame(self)
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Style spécifique pour rendre les enregistrements plus compacts et lisibles
        style = ttk.Style()
        style.configure("Archives.Treeview", font=("Helvetica", 10))
        style.configure("Archives.Treeview.Heading", font=("Helvetica", 11, "bold"))

        columns = ("ID", "Nom", "Prénom", "Mois", "Montant", "Devise", "Statut Souscription", "Statut des versements", "Date Création")
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings", selectmode="extended", style="Archives.Treeview")
        
        self.tree.heading("ID", text="ID")
        self.tree.column("ID", width=50, anchor="center")
        self.tree.heading("Nom", text="Nom")
        self.tree.heading("Prénom", text="Prénom")
        self.tree.heading("Mois", text="Mois")
        self.tree.column("Mois", width=100, anchor="center")
        self.tree.heading("Montant", text="Montant")
        self.tree.column("Montant", width=100, anchor="e")
        self.tree.heading("Devise", text="Devise")
        self.tree.column("Devise", width=80, anchor="center")
        self.tree.heading("Statut Souscription", text="Souscription")
        self.tree.heading("Statut des versements", text="Statut des versements")
        self.tree.heading("Date Création", text="Date d'archivage")

        # Scrollbar
        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Actions Footer
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(fill="x", padx=20, pady=20)

        self.btn_export_pdf = ctk.CTkButton(
            self.footer_frame, 
            text="📄 Exporter PDF", 
            command=self.export_pdf,
            fg_color=C["bg_section"],
            hover_color=C["border"]
        )
        self.btn_export_pdf.pack(side="left", padx=(0, 10))

        self.btn_export_csv = ctk.CTkButton(
            self.footer_frame, 
            text="📊 Exporter CSV", 
            command=self.export_csv,
            fg_color=C["green"],
            hover_color=C["green"]
        )
        self.btn_export_csv.pack(side="left", padx=10)

        self.btn_restaurer = ctk.CTkButton(
            self.footer_frame, 
            text="🔄 Restaurer Sélection", 
            command=self.restaurer_selection,
            fg_color=C["orange"],
            hover_color=C["orange"]
        )
        self.btn_restaurer.pack(side="right")

        self.current_data = []
        
        # Charger les données
        self.after(100, self.load_data)

    def load_data(self):
        nom = self.entry_search.get().strip()
        mois = self.entry_mois.get().strip()

        try:
            records = get_archives(filtre_nom=nom, filtre_mois=mois)
        except Exception as exc:
            messagebox.showerror(
                "Archives indisponibles",
                f"Impossible de charger les archives : {exc}",
                parent=self,
            )
            records = []
        self.current_data = records

        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in records:
            # row: p.id, l.id, l.nom, l.prenom, mois, p.montant, p.devise, p.statut_souscription, p.statut, p.date_creation
            # table cols: ID, Nom, Prénom, Mois, Montant, Devise, Statut Souscription, Statut, Date Création
            display_row = (
                row[0], # ID paiement
                row[2], # Nom
                row[3], # Prénom
                row[4], # Mois
                f"{row[5]:,.2f}", # Montant
                row[6], # Devise
                row[7], # Statut Souscription
                row[8], # Statut
                row[9]  # Date Création
            )
            self.tree.insert("", "end", values=display_row)

    def restaurer_selection(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Sélection", "Veuillez sélectionner au moins une archive à restaurer.")
            return

        if not messagebox.askyesno("Confirmation", f"Êtes-vous sûr de vouloir restaurer {len(selected_items)} archive(s) ?\n\nElles seront réintégrées dans les données actives."):
            return

        success_count = 0
        for item in selected_items:
            values = self.tree.item(item, "values")
            paiement_id = values[0]
            success, _ = restaurer_archive(paiement_id)
            if success:
                success_count += 1

        messagebox.showinfo("Restauration", f"{success_count}/{len(selected_items)} archive(s) restaurée(s) avec succès.")
        self.load_data()
        
        # Notifier la fenêtre parente qu'elle doit se rafraîchir
        if hasattr(self.master, "charger_donnees"):
            self.master.charger_donnees()
        elif hasattr(self.master, "load_data"):
            self.master.load_data()

    def archiver_maintenant(self):
        if not messagebox.askyesno(
            "Archivage",
            "Voulez-vous archiver maintenant les paiements anciens ?\n\n"
            "Les archives resteront consultables ici et pourront être restaurées.",
            parent=self,
        ):
            return

        try:
            result = executer_archivage()
        except Exception as exc:
            messagebox.showerror(
                "Archivage",
                f"Impossible de lancer l'archivage automatique : {exc}",
                parent=self,
            )
            return

        if not result.get("enabled", True):
            messagebox.showinfo(
                "Archivage",
                "L'archivage automatique est désactivé dans config.json.",
                parent=self,
            )
            return

        archived = int(result.get("archived", 0) or 0)
        skipped = int(result.get("skipped", 0) or 0)
        cutoff = result.get("cutoff") or "inconnu"
        messagebox.showinfo(
            "Archivage",
            (
                f"{archived} paiement(s) archivé(s).\n"
                f"{skipped} ligne(s) conservée(s) ou déjà archivées.\n"
                f"Seuil d'archivage : {cutoff}."
            ),
            parent=self,
        )
        self.load_data()
        if hasattr(self.master, "charger_donnees"):
            self.master.charger_donnees()
        elif hasattr(self.master, "load_data"):
            self.master.load_data()

    def export_csv(self):
        if not self.current_data:
            messagebox.showwarning("Attention", "Aucune donnée à exporter.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Exporter les archives en CSV",
            initialfile="archives_export.csv"
        )
        if not filepath:
            return

        try:
            with open(filepath, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file, delimiter=';')
                writer.writerow(["ID", "Nom", "Prénom", "Mois", "Montant", "Devise", "Souscription", "Statut des versements", "Date Archivage"])
                for row in self.current_data:
                    writer.writerow([
                        row[0], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9]
                    ])
            messagebox.showinfo("Succès", f"Les archives ont été exportées vers {filepath}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec de l'exportation CSV: {e}")

    def export_pdf(self):
        if not self.current_data:
            messagebox.showwarning("Attention", "Aucune donnée à exporter.")
            return
            
        # Format the data for ExportPDFDialog
        # It expects records like: nom, prenom, tel, montant, devise, mois, statut
        # We'll map what we have
        pdf_data = []
        for r in self.current_data:
            # r: [p.id, l.id, nom, prenom, mois, montant, devise, souscription, statut, date]
            pdf_data.append((r[2], r[3], "", r[5], r[6], r[4], r[8]))
            
        filters = {"type": "Archives"}
        # Garder une référence pour éviter le garbage collection
        self._export_pdf_dialog = ExportPDFDialog(self, pdf_data, filters, export_mode="pdf")

    def on_close(self):
        if getattr(self, '_closed', False):
            return
        self._closed = True
        # Nettoyer la référence dans le parent si elle existe
        try:
            if hasattr(self.master, '_archives_dialog') and self.master._archives_dialog == self:
                self.master._archives_dialog = None
        except Exception:
            pass
        try:
            self.grab_release()
        except Exception:
            pass
        if self.winfo_exists():
            try:
                self.destroy()
            except Exception:
                pass
