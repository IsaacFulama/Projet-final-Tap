import customtkinter as ctk
from tkinter import ttk, messagebox, Menu, StringVar, filedialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as mticker
from collections import Counter, defaultdict
import csv
import os

from tap.config.theme import C, MPL, STATUS_COLORS
from tap.config.responsive import (
    build_layout_profile,
    clamp_window_geometry,
    detect_screen_profile,
    records_page_uses_full_width,
    table_display_columns,
)
from tap.core.utils import (
    build_month_choices,
    build_special_rollover_month_choices,
    format_month_label,
    month_sort_key,
    parse_mois_saisie,
)
from tap.core.auto_status_updater import (
    executer_basculement_special_manuel,
    executer_mise_a_jour_automatique,
)
from tap.core.dashboard_service import calculate_dashboard_metrics
from tap.core.models import HistoryPayment, SubscriptionRecord
from tap.core.local_signature import start_signature_session
from tap.mobile.portal_service import create_portal_token
from tap.mobile.payment_links import create_payment_link
from tap.mobile.runtime import portal_url, payment_link_url, configure_mobile_environment
from tap.core.payment_service import PaymentService, SubscriptionFilters
from tap.core.whatsapp_reports import send_overdue_payment_reminders
from tap.presentation.components.widgets import SidebarButton, StatCard
from tap.presentation.dialogs.export_pdf import ExportPDFDialog
from tap.presentation.dialogs.formulaire import FormulaireSouscription, NouveauSouscripteurDialog
from tap.presentation.dialogs.archives import DialogArchives
from tap.presentation.dialogs.signature_qr import SignatureQRDialog
from tap.presentation.dialogs.portal_qr import PortalQRDialog
from tap.presentation.dialogs.payment_proofs import PaymentProofsDialog

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


# ── Helpers de robustesse pour dialogues CTk ────────────────────────────────

def _assurer_root_disponible(toplevel):
    """
    Enregistre explicitement le root Tk comme default_root avant de construire CTkFont.
    Corrige : RuntimeError("Too early to use font: no default root window")
    sur les 2èmes+ ouvertures après destruction d'anciens dialogues.
    """
    try:
        import tkinter
        master = getattr(toplevel, 'master', None)
        root = None
        if master is not None:
            try:
                root = master.winfo_toplevel()
                while hasattr(root, 'master') and root.master is not None:
                    root = root.master
            except Exception:
                pass
        if root is None or not getattr(root, 'winfo_exists', lambda: False)():
            try:
                root = tkinter._default_root
            except Exception:
                root = None
        if root is not None:
            try:
                tkinter._default_root = root
            except Exception:
                pass
        try:
            if hasattr(root, 'tk') and root.tk is not None:
                root.tk.call('tk', 'useinputmethods', '1')
        except Exception:
            pass
    except Exception:
        pass


def _annuler_after_callbacks(widget):
    """
    Annule TOUS les callbacks after enregistrés sur un widget et ses enfants.
    Corrige : "invalid command name xxxupdate" / "xxxcheck_dpi_scaling"
    (customtkinter interne qui relance after sur widgets détruits)
    """
    try:
        if not getattr(widget, 'winfo_exists', lambda: False)():
            return
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        _annuler_after_callbacks(child)
    try:
        info = widget.tk.call('after', 'info')
    except Exception:
        info = []
    if info:
        ids = []
        if isinstance(info, (list, tuple)):
            for item in info:
                if isinstance(item, str) and (item.startswith('after#') or item[0] in '0123456789'):
                    ids.append(item)
                elif isinstance(item, (list, tuple)) and len(item) >= 1:
                    candidate = item[0]
                    if isinstance(candidate, str):
                        ids.append(candidate)
        for after_id in ids:
            try:
                widget.after_cancel(after_id)
            except Exception:
                pass


# ── StatCard avec animation ─────────────────────────────────────────────────

class AnimatedStatCard(StatCard):
    """StatCard avec animation de transition fluide"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_numeric_value = 0
        self._animation_id = None
        
    def update(self, value, subtitle=""):
        """Met à jour avec animation si c'est un nombre"""
        try:
            new_value = float(str(value).replace(",", "").replace(" ", ""))
            if self._animation_id:
                self.after_cancel(self._animation_id)
            self._animate_value(self._current_numeric_value, new_value, subtitle)
            self._current_numeric_value = new_value
        except (ValueError, TypeError):
            # Valeur non numérique, mise à jour directe
            super().update(value, subtitle)
    
    def _animate_value(self, from_val, to_val, subtitle, steps=15, duration=200):
        """Animation progressive de la valeur"""
        if steps <= 0:
            super().update(f"{to_val:,.0f}", subtitle)
            return
            
        progress = (steps - 1) / steps if steps > 1 else 1
        # Easing function pour une animation plus naturelle
        eased_progress = progress * progress * (3 - 2 * progress)
        current = from_val + (to_val - from_val) * eased_progress
        
        super().update(f"{current:,.0f}", subtitle)
        
        self._animation_id = self.after(
            duration // steps,
            lambda: self._animate_value(from_val, to_val, subtitle, steps - 1, duration)
        )


# ── Dialogue d'historique amélioré ──────────────────────────────────────────

class HistoriqueDialog(ctk.CTkToplevel):
    """Dialogue d'historique avec tri et export"""

    def _assurer_root_disponible(self):
        _assurer_root_disponible(self)

    def __init__(self, parent, nom, prenom, paiements):
        super().__init__(parent)
        self._screen = detect_screen_profile()
        self._compact_mode = self._screen.width < 1100
        self.nom = nom
        self.prenom = prenom
        self.paiements = [HistoryPayment.from_row(row) for row in paiements]
        self._sort_column = None
        self._sort_reverse = False
        self._closed = False
        self.title(f"Historique - {nom} {prenom}")

        # PRÉ-REQUIS OBLIGATOIRE : assurer le root Tk AVANT CTkFont / UI
        self._assurer_root_disponible()
        
        # Géométrie responsive
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        
        # Dimensions adaptatives
        if min(screen_w, screen_h) < 900:
            width_ratio, height_ratio = 0.94, 0.88
            min_width, min_height = 520, 380
        elif screen_w < 1366:
            width_ratio, height_ratio = 0.54, 0.64
            min_width, min_height = 560, 420
        elif screen_w < 1920:
            width_ratio, height_ratio = 0.46, 0.62
            min_width, min_height = 600, 450
        else:
            width_ratio, height_ratio = 0.40, 0.58
            min_width, min_height = 640, 480

        width, height = clamp_window_geometry(
            screen_w,
            screen_h,
            width_ratio=width_ratio,
            height_ratio=height_ratio,
            min_width=min_width,
            min_height=min_height,
        )
        
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(
            max(420, min(640, screen_w - 20)),
            max(320, min(480, screen_h - 20)),
        )
        self.configure(fg_color=C["bg_deep"])
        self.transient(parent)
        self.grab_set()
        
        # Raccourcis clavier
        self.bind("<Escape>", lambda e: self._close())
        self.bind("<Control-w>", lambda e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        
        self._build_ui()

    def _close(self):
        if getattr(self, '_closed', False):
            return
        self._closed = True
        try:
            self.grab_release()
        except Exception:
            pass
        # ANNULATION AFTER CALLBACKS INTERNES CTK
        try:
            _annuler_after_callbacks(self)
        except Exception:
            pass
        # Nettoyer la référence dans le parent si elle existe
        if hasattr(self.master, '_history_dialog') and self.master._history_dialog == self:
            self.master._history_dialog = None
        if self.winfo_exists():
            self.destroy()
        
    def _build_ui(self):
        """Construit l'interface du dialogue"""
        # Frame principal
        frame = ctk.CTkFrame(self, fg_color=C["bg_card"], corner_radius=16,
                              border_width=1, border_color=C["border"])
        frame.pack(fill="both", expand=True, padx=14 if self._compact_mode else 20,
                   pady=14 if self._compact_mode else 20)

        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=18 if self._compact_mode else 24,
                    pady=(18 if self._compact_mode else 20, 14 if self._compact_mode else 16))

        ctk.CTkLabel(header, text="📊 Historique des paiements",
                     font=ctk.CTkFont(family="Georgia", size=18 if self._compact_mode else 20, weight="bold"),
                     text_color=C["accent"]).pack(anchor="w")

        ctk.CTkLabel(header, text=f"{self.nom} {self.prenom}",
                     font=ctk.CTkFont(size=12 if self._compact_mode else 14, weight="bold"),
                     text_color=C["text_hi"]).pack(anchor="w", pady=(8, 0))

        ctk.CTkFrame(frame, height=1, fg_color=C["border"]).pack(fill="x", padx=0)

        # Actions
        actions_frame = ctk.CTkFrame(frame, fg_color="transparent")
        actions_frame.pack(fill="x", padx=18 if self._compact_mode else 24,
                           pady=(12, 0))

        if self._compact_mode:
            for col in range(3):
                actions_frame.columnconfigure(col, weight=1, uniform="hist_actions")

        csv_btn = ctk.CTkButton(actions_frame, text="📄 Exporter CSV",
                                fg_color=C["bg_section"], hover_color=C["border"],
                                text_color=C["text_hi"], height=32,
                                width=118 if self._compact_mode else 140,
                                corner_radius=6,
                                command=self._export_csv)

        chart_btn = ctk.CTkButton(actions_frame, text="📊 Graphique",
                                  fg_color=C["bg_section"], hover_color=C["border"],
                                  text_color=C["text_hi"], height=32,
                                  width=118 if self._compact_mode else 120,
                                  corner_radius=6,
                                  command=self._show_evolution_chart)

        if self._compact_mode:
            csv_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 8))
            chart_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=(0, 8))
        else:
            csv_btn.pack(side="left", padx=(0, 8))
            chart_btn.pack(side="left", padx=(0, 8))

        # Stats
        self.stats_frame = ctk.CTkFrame(frame, fg_color=C["bg_section"], corner_radius=8)
        self.stats_frame.pack(fill="x", padx=18 if self._compact_mode else 24, pady=12)
        self._update_stats()

        # Tableau
        self.tbl_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.tbl_frame.pack(fill="both", expand=True, padx=18 if self._compact_mode else 24, pady=(0, 16))
        self._build_table()

        # Bouton fermer
        ctk.CTkButton(frame, text="Fermer", width=120, height=35,
                      fg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="#000000",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      corner_radius=6,
                      command=self.destroy).pack(
                          fill="x" if self._compact_mode else "none",
                          padx=18 if self._compact_mode else 0,
                          pady=(0, 16 if self._compact_mode else 20)
                      )
        
    def _update_stats(self):
        """Met à jour les statistiques"""
        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        stats_row = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        stats_row.pack(fill="x", padx=12, pady=12)

        if self._compact_mode:
            for col in range(2):
                stats_row.columnconfigure(col, weight=1, uniform="hist")
        else:
            for col in range(7):
                stats_row.columnconfigure(col, weight=1, uniform="hist")

        total_montant = 0
        total_paye = 0
        total_reste = 0
        payes = 0
        litigieux = 0
        attente = 0
        complets = 0
        partiels = 0

        for p in self.paiements:
            try:
                total_montant += float(str(p.total_amount).replace(",", "."))
                total_paye += float(str(p.paid_amount).replace(",", "."))
                total_reste += float(str(p.remaining_amount).replace(",", "."))
            except (TypeError, ValueError):
                pass
            if p.status == "En règle":
                payes += 1
            elif p.status == "Litigieux":
                litigieux += 1
            elif p.status == "En attente":
                attente += 1
            if p.payment_status == "Complet":
                complets += 1
            elif p.payment_status == "Partiel":
                partiels += 1

        stats = [
            (f"Total: {len(self.paiements)}", C["text_hi"]),
            (f"En règle: {payes}", C["green"]),
            (f"Litigieux: {litigieux}", C["orange"]),
            (f"Complet: {complets}", C["green"]),
            (f"Partiel: {partiels}", C["orange"]),
            (f"Total payé: {total_paye:,.0f}", C["accent"]),
            (f"Reste: {total_reste:,.0f}", C["red"]),
        ]

        if self._compact_mode:
            positions = [(i // 2, i % 2) for i in range(len(stats))]
        else:
            positions = [(0, i) for i in range(len(stats))]

        for (text, color), (row, col) in zip(stats, positions):
            self._stat_label(stats_row, text, color, row=row, column=col)
        
    @staticmethod
    def _stat_label(parent, text, color, row=0, column=0):
        """Crée un label de statistique"""
        label = ctk.CTkLabel(parent, text=text,
                             font=ctk.CTkFont(size=10, weight="bold"),
                             text_color=color)
        label.grid(row=row, column=column, sticky="w", padx=(0, 18), pady=4)
        
    def _build_table(self):
        """Construit le tableau des paiements"""
        cols = ("Mois", "Montant Total", "Montant Payé", "Reste", "Devise", "Statut Souscription", "Statut des versements", "Statut Paiement")
        self.tree = ttk.Treeview(self.tbl_frame, columns=cols,
                                 show="headings", style="TAP.Treeview")

        if self._compact_mode:
            widths = {"Mois": 90, "Montant Total": 85, "Montant Payé": 85, "Reste": 75,
                      "Devise": 60, "Statut Souscription": 100, "Statut des versements": 100, "Statut Paiement": 90}
        else:
            widths = {"Mois": 110, "Montant Total": 110, "Montant Payé": 110, "Reste": 100,
                      "Devise": 75, "Statut Souscription": 130, "Statut des versements": 130, "Statut Paiement": 110}
        anchors = {
            "Mois": "center",
            "Montant Total": "e",
            "Montant Payé": "e",
            "Reste": "e",
            "Devise": "center",
            "Statut Souscription": "center",
            "Statut des versements": "center",
            "Statut Paiement": "center",
        }

        for col in cols:
            self.tree.heading(
                col, text=col.upper(), anchor=anchors.get(col, "center"),
                command=lambda c=col: self._sort_by_column(c)
            )
            self.tree.column(col, width=widths.get(col, 90),
                           anchor=anchors.get(col, "center"),
                           stretch=col in {"Mois", "Statut Souscription", "Statut des versements", "Statut Paiement"},
                           minwidth=60)

        # Remplir
        for i, paiement in enumerate(self.paiements):
            tag = "even" if i % 2 == 0 else "odd"
            st = paiement.status
            status_tag = {"En règle": "paye", "Litigieux": "litige",
                         "En attente": "attente"}.get(st, "")

            # Statut paiement tag
            statut_paiement = paiement.payment_status
            paiement_tag = {"Complet": "complet", "Partiel": "partiel", "En attente": "attente_paiement"}.get(statut_paiement, "")

            values = (
                paiement.month,
                paiement.total_amount,
                paiement.paid_amount,
                paiement.remaining_amount,
                paiement.currency,
                paiement.subscription_status,
                paiement.status,
                paiement.payment_status,
            )

            self.tree.insert("", "end", values=values, tags=(tag, status_tag, paiement_tag))

        # Scrollbar
        scrollbar = ctk.CTkScrollbar(
            self.tbl_frame, command=self.tree.yview,
            fg_color=C["bg_section"], button_color=C["border"],
            button_hover_color=C["accent_dim"]
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Appliquer les tags
        self._apply_tree_tags()
        
    def _apply_tree_tags(self):
        """Configure les tags de style pour le tableau"""
        self.tree.tag_configure("even", background=C["tbl_even"])
        self.tree.tag_configure("odd", background=C["tbl_odd"])
        self.tree.tag_configure("paye", foreground=C["green"])
        self.tree.tag_configure("litige", foreground=C["orange"])
        self.tree.tag_configure("attente", foreground=C["blue"])
        self.tree.tag_configure("complet", foreground=C["green"])
        self.tree.tag_configure("partiel", foreground=C["orange"])
        self.tree.tag_configure("attente_paiement", foreground=C["text_lo"])
        
    def _sort_by_column(self, column):
        """Trie le tableau par colonne"""
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
            
        # Récupérer les items
        items = [(self.tree.set(item, column), item) 
                for item in self.tree.get_children("")]
        
        # Trier selon le type
        if column == "Mois":
            items.sort(key=lambda x: month_sort_key(x[0]), reverse=self._sort_reverse)
        elif column in {"Montant Total", "Montant Payé", "Reste"}:
            try:
                items.sort(key=lambda x: float(x[0].replace(",", ".").replace(" ", "")), 
                          reverse=self._sort_reverse)
            except ValueError:
                items.sort(reverse=self._sort_reverse)
        else:
            items.sort(key=lambda x: x[0].lower(), reverse=self._sort_reverse)
        
        # Réorganiser
        for index, (_, item) in enumerate(items):
            self.tree.move(item, "", index)
            
        # Mettre à jour les tags even/odd
        for i, item in enumerate(self.tree.get_children("")):
            current_tags = list(self.tree.item(item, "tags"))
            # Retirer les anciens tags even/odd
            current_tags = [t for t in current_tags if t not in ("even", "odd")]
            current_tags.insert(0, "even" if i % 2 == 0 else "odd")
            self.tree.item(item, tags=tuple(current_tags))
            
    def _export_csv(self):
        """Exporte l'historique en CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"historique_{self.nom}_{self.prenom}.csv"
        )

        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(["Mois", "Montant Total", "Montant Payé", "Reste à Payer", "Devise",
                               "Statut Souscription", "Statut des versements", "Statut Paiement"])
                for p in self.paiements:
                    writer.writerow([
                        p.month, p.total_amount, p.paid_amount, p.remaining_amount,
                        p.currency, p.subscription_status, p.status, p.payment_status,
                    ])
                writer.writerow([])
                writer.writerow(["Filtres", "Aucun filtre individuel dans l'historique", "", "", "", "", "", ""])

            messagebox.showinfo("Export réussi",
                              f"Fichier sauvegardé :\n{filename}")
        except Exception as e:
            messagebox.showerror("Erreur d'export",
                               f"Impossible d'exporter : {str(e)}")
    
    def _show_evolution_chart(self):
        """Affiche un graphique d'évolution dans le dialogue"""
        # Créer un sous-dialogue pour le graphique
        chart_dialog = ctk.CTkToplevel(self)
        chart_dialog.title(f"Évolution - {self.nom} {self.prenom}")
        
        # Dimensions adaptatives
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        if min(screen_w, screen_h) < 900:
            chart_width = max(320, screen_w - 40)
            chart_height = max(260, screen_h - 60)
        elif screen_w < 1366:
            chart_width = min(760, screen_w - 80)
            chart_height = min(520, screen_h - 100)
        else:
            chart_width = min(840, screen_w - 100)
            chart_height = min(560, screen_h - 120)

        chart_dialog.geometry(f"{chart_width}x{chart_height}")
        chart_dialog.minsize(min(chart_width, 320), min(chart_height, 260))
        chart_dialog.configure(fg_color=C["bg_deep"])
        chart_dialog.transient(self)
        chart_dialog.grab_set()
        
        # Frame pour le graphique
        frame = ctk.CTkFrame(chart_dialog, fg_color=C["bg_card"], 
                             corner_radius=12, border_width=1,
                             border_color=C["border"])
        frame.pack(fill="both", expand=True, padx=16, pady=16)
        
        # Titre
        ctk.CTkLabel(frame, text=f"Évolution des paiements",
                     font=ctk.CTkFont(family="Georgia", size=16, weight="bold"),
                     text_color=C["accent"]).pack(pady=(12, 4))
        
        # Graphique
        canvas_frame = ctk.CTkFrame(frame, fg_color="transparent")
        canvas_frame.pack(fill="both", expand=True, padx=8, pady=8)
        
        fig = Figure(figsize=(8, 4), facecolor=MPL["bg"])
        ax = fig.add_subplot(111, facecolor=MPL["axes"])
        
        # Préparer les données
        mois_list = []
        montants = []
        for p in self.paiements:
            try:
                mois_list.append(str(p.month))
                montants.append(float(str(p.amount).replace(",", ".")))
            except (TypeError, ValueError):
                pass
        
        if mois_list:
            # Trier par mois
            sorted_data = sorted(zip(mois_list, montants), 
                               key=lambda x: month_sort_key(x[0]))
            mois_list, montants = zip(*sorted_data)
            
            # Couleurs selon les montants
            max_val = max(montants) if montants else 1
            colors = []
            for val in montants:
                ratio = val / max_val
                r = int(0x60 + ratio * (0xC9 - 0x60))
                g = int(0x50 + ratio * (0xA8 - 0x50))
                b = int(0x30 + ratio * (0x4C - 0x30))
                colors.append(f"#{r:02x}{g:02x}{b:02x}")
            
            ax.bar(range(len(mois_list)), montants, color=colors, width=0.7)
            ax.set_xticks(range(len(mois_list)))
            ax.set_xticklabels(mois_list, rotation=45, ha="right", 
                              color=MPL["text"], fontsize=8)
            
            # Ajouter les valeurs
            for i, (x, y) in enumerate(zip(range(len(mois_list)), montants)):
                ax.text(x, y, f"{y:,.0f}", ha="center", va="bottom",
                       color=MPL["text"], fontsize=8)
        
        ax.set_ylabel("Montant", color=MPL["text"])
        ax.tick_params(axis="y", colors=MPL["text"], labelsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(MPL["border"])
        ax.spines["bottom"].set_color(MPL["border"])
        ax.yaxis.grid(True, color=MPL["grid"], linewidth=0.5, zorder=0)
        ax.set_axisbelow(True)
        
        fig.tight_layout(pad=2)
        
        canvas = FigureCanvasTkAgg(fig, canvas_frame)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        canvas.draw()
        
        # Bouton fermer
        ctk.CTkButton(frame, text="Fermer", width=100, height=30,
                      fg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="#000000",
                      command=chart_dialog.destroy).pack(pady=12)


# ── Application principale ──────────────────────────────────────────────────

class AppGestionLoyers(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._screen = detect_screen_profile()
        short_side = min(self._screen.width, self._screen.height)
        if short_side < 900:
            self._ui_scale = 0.90
        elif short_side < 1100:
            self._ui_scale = 0.96
        elif short_side < 1400:
            self._ui_scale = 1.00
        elif short_side < 1800:
            self._ui_scale = 1.04
        else:
            self._ui_scale = 1.08
        self.configure(fg_color=C["bg_deep"])
        self.title("TAP · Gestion des Loyers")
        self._set_initial_geometry()
        self.minsize(
            max(680, min(980, self._screen.width - 20)),
            max(520, min(760, self._screen.height - 20)),
        )
        
        # Cache des données
        self._all_data: list = []
        self._row_meta: dict[str, dict] = {}

        self.payment_service = PaymentService()

        # Références aux dialogues pour éviter le garbage collection
        self._current_dialog = None
        self._export_pdf_dialog = None
        self._archives_dialog = None
        self._portal_qr_dialog = None
        self._payment_qr_dialog = None
        self._signature_qr_dialog = None
        self._payment_proofs_dialog = None
        self._history_dialog = None

        # Variables d'état
        self.status_var = StringVar(value="Prêt. Connectez-vous aux données ou ajoutez un paiement.")
        self.active_filters = {
            "nom": "",
            "mois": "",
            "statut": "Tous",
            "statut_souscription": "Tous",
            "devise": "Toutes",
        }
        self.current_filter_type = "Nom"
        
        # Gestion du responsive
        self._responsive_after_id = None
        self._filter_debounce_id = None
        self._filter_debounce_delay = 300
        self._last_width = 0
        self._resize_lock = False
        
        # État du layout
        self._current_layout_mode = None
        self._current_chart_layout = None
        self._current_table_card_columns = None
        self._current_kpi_columns = None
        self._layout_profile = None
        self._records_need_page_scroll = self._screen.dpi_scale > 1.05 or self._ui_scale > 1.0
        
        # État de chargement
        self._is_loading = False
        self._loading_after_id = None
        self._maintenance_after_id = None
        self._startup_maintenance_after_id = None

        self._build_sidebar()
        self._build_main()
        self._apply_table_style()
        self._setup_keyboard_shortcuts()
        
        self.bind("<Configure>", self._on_window_resize)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.after(250, self._apply_responsive_layout)
        self._schedule_automatic_maintenance()
        self.charger_donnees()
        self._startup_maintenance_after_id = self.after(1500, self._run_automatic_maintenance)

    # ── Raccourcis clavier ───────────────────────────────────────────────────
    def _setup_keyboard_shortcuts(self):
        """Configure les raccourcis clavier"""
        self.bind("<Control-n>", lambda e: self.ouvrir_formulaire())
        self.bind("<Control-r>", lambda e: self.charger_donnees())
        self.bind("<Control-f>", lambda e: self._focus_search())
        self.bind("<Control-p>", lambda e: self.generer_pdf())
        self.bind("<Control-Escape>", lambda e: self._reset_filters())
        
    def _focus_search(self):
        """Donne le focus au champ de recherche"""
        if hasattr(self, 'filter_value_widget') and self.filter_value_widget.winfo_exists():
            self.filter_value_widget.focus_set()
            self._set_status("🔍 Recherche - tapez votre filtre")

    # ── Gestion du chargement ────────────────────────────────────────────────
    def _show_loading(self, message="Chargement..."):
        """Affiche un indicateur de chargement"""
        if self._is_loading:
            return
        self._is_loading = True
        self.configure(cursor="watch")
        self._set_status(f"⏳ {message}")
        self._disable_interactions()
        
    def _hide_loading(self):
        """Cache l'indicateur de chargement"""
        self._is_loading = False
        self.configure(cursor="")
        self._enable_interactions()
        
    def _disable_interactions(self):
        """Désactive les interactions pendant le chargement"""
        for child in self.winfo_children():
            self._set_widget_state(child, "disabled")
            
    def _enable_interactions(self):
        """Réactive les interactions"""
        for child in self.winfo_children():
            self._set_widget_state(child, "normal")
            
    def _set_widget_state(self, widget, state):
        """Définit récursivement l'état d'un widget"""
        try:
            if isinstance(widget, (ctk.CTkButton, ctk.CTkComboBox, ctk.CTkEntry)):
                if widget.winfo_exists():
                    widget.configure(state=state)
        except Exception:
            pass
            
        try:
            for child in widget.winfo_children():
                self._set_widget_state(child, state)
        except Exception:
            pass

    # ── SIDEBAR ──────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=C["bg_panel"])
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        self.sidebar_frame = sb

        brand = ctk.CTkFrame(sb, fg_color="transparent")
        brand.pack(fill="x", padx=24, pady=(32, 0))
        self.sidebar_brand = ctk.CTkLabel(brand, text="TAP",
                                          font=ctk.CTkFont(family="Georgia", size=42, weight="bold"),
                                          text_color=C["accent"])
        self.sidebar_brand.pack(anchor="w")
        self.sidebar_subtitle = ctk.CTkLabel(brand, text="GESTION LOYERS",
                                             font=ctk.CTkFont(size=10, weight="bold"),
                                             text_color=C["text_lo"])
        self.sidebar_subtitle.pack(anchor="w")

        ctk.CTkFrame(sb, height=1, fg_color=C["border"]).pack(fill="x", padx=24, pady=24)

        nav = ctk.CTkScrollableFrame(
            sb,
            fg_color="transparent",
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent_dim"],
        )
        nav.pack(fill="both", expand=True, padx=16)

        self.btn_nav_nouveau = SidebarButton(nav, text="  ➕  Nouveau Souscripteur",
                          fg_color=C["accent"], hover_color=C["accent_dim"],
                          text_color="#000000", font=ctk.CTkFont(size=13, weight="bold"),
                          command=self.ouvrir_formulaire)
        self.btn_nav_records = SidebarButton(nav, text="  📋  Enregistrements",
                          fg_color=C["bg_section"], hover_color=C["border"],
                          text_color=C["text_hi"], command=self._show_records_page)
        self.btn_nav_special = SidebarButton(nav, text="  ⭐  Souscripteurs spéciaux",
                          fg_color=C["bg_section"], hover_color=C["border"],
                          text_color=C["text_hi"], command=self._show_special_subscribers_page)
        self.btn_nav_reminders = SidebarButton(nav, text="  📣  Rappels impayés",
                          fg_color=C["bg_section"], hover_color=C["border"],
                          text_color=C["text_hi"], command=self.envoyer_rappels_impayes)
        self.btn_nav_dashboard = SidebarButton(nav, text="  📊  Tableau de bord",
                          fg_color=C["bg_section"], hover_color=C["border"],
                          text_color=C["text_hi"], command=self._show_dashboard_page)
        self.btn_nav_actualiser = SidebarButton(nav, text="  🔄  Actualiser",
                          command=self.charger_donnees)
        self.btn_nav_pdf = SidebarButton(nav, text="  📄  Exporter PDF",
                          fg_color="#FFF4F4", hover_color="#FDECEC",
                          text_color=C["red"],
                          command=self.generer_pdf)

        self.sidebar_buttons = [
            self.btn_nav_nouveau,
            self.btn_nav_records,
            self.btn_nav_special,
            self.btn_nav_reminders,
            self.btn_nav_actualiser,
            self.btn_nav_pdf,
        ]
        # btn_nav_dashboard sera affiché uniquement sur la page enregistrements
        for button in self.sidebar_buttons:
            button.pack(fill="x", pady=(0, 8))

        self.sidebar_footer = ctk.CTkLabel(sb, text="v3.7  ·  TAP Loyers",
                                           font=ctk.CTkFont(size=10),
                                           text_color=C["text_lo"])
        self.sidebar_footer.pack(pady=20)

    # ── ZONE PRINCIPALE ──────────────────────────────────────────────────────
    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        self.main_frame = main

        # Header commun (toujours visible)
        hdr = ctk.CTkFrame(main, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 16))
        self.header_title = ctk.CTkLabel(hdr, text="Tableau de bord",
                                         font=ctk.CTkFont(family="Georgia", size=24, weight="bold"),
                                         text_color=C["text_hi"])
        self.header_title.pack(side="left")
        self.header_subtitle = ctk.CTkLabel(hdr, text="Souscriptions & Paiements",
                                            font=ctk.CTkFont(size=13), text_color=C["text_lo"])
        self.header_subtitle.pack(side="left", padx=(12, 0), pady=(6, 0))

        self.status_bar = ctk.CTkLabel(
            main,
            textvariable=self.status_var,
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=C["text_lo"],
        )
        self.status_bar.pack(fill="x", pady=(0, 12))

        # ── PAGE DASHBOARD (visible par défaut) ───────────────────────────────
        self.page_dashboard = ctk.CTkFrame(main, fg_color="transparent")
        self.page_dashboard.pack(fill="both", expand=True)

        self.tabs = ctk.CTkTabview(
            self.page_dashboard, fg_color=C["bg_card"],
            segmented_button_fg_color=C["bg_section"],
            segmented_button_selected_color=C["accent"],
            segmented_button_selected_hover_color=C["accent_dim"],
            segmented_button_unselected_color=C["bg_section"],
            segmented_button_unselected_hover_color=C["border"],
            text_color=C["text_hi"],
            text_color_disabled=C["text_lo"],
            border_width=1, border_color=C["border"],
            corner_radius=12
        )
        self.tabs.pack(fill="both", expand=True)

        tab_dash = self.tabs.add("  📊  Analyse  ")
        self._build_tab_dashboard(tab_dash)
        self.tabs.configure(command=self._on_tab_change)

        # ── PAGE ENREGISTREMENTS (cachée par défaut) ───────────────────────────
        records_container = ctk.CTkScrollableFrame if self._records_need_page_scroll else ctk.CTkFrame
        self.page_records = records_container(main, fg_color="transparent")
        # Ne pas packer maintenant — cachée par défaut

        # Filtres dans la page enregistrements
        self._build_filters(self.page_records)
        self._build_tab_table(self.page_records)

    # ── FILTRES GLOBAUX ──────────────────────────────────────────────────────
    def _build_filters(self, parent):
        f = ctk.CTkFrame(parent, fg_color=C["bg_card"], corner_radius=10,
                          border_width=1, border_color=C["border"])
        f.pack(fill="x", pady=(0, 12))
        self.filters_card = f

        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        self.filters_title = ctk.CTkLabel(header, text="Filtres combinables",
                                          font=ctk.CTkFont(size=13, weight="bold"),
                                          text_color=C["text_hi"])
        self.filters_title.pack(side="left")
        self.filters_help = ctk.CTkLabel(header, text="Choisissez un type, ajoutez-le, puis cumulez d'autres critères.",
                                         font=ctk.CTkFont(size=10),
                                         text_color=C["text_lo"])
        self.filters_help.pack(side="left", padx=(12, 0))

        self._build_special_rollover_bar(f)

        self.filter_type_row = ctk.CTkFrame(f, fg_color="transparent")
        self.filter_type_row.pack(fill="x", padx=16, pady=(6, 6))

        self.filter_type_label = ctk.CTkLabel(self.filter_type_row, text="Type",
                                              font=ctk.CTkFont(size=11),
                                              text_color=C["text_lo"])
        self.filter_type_label.pack(side="left", padx=(0, 6))
        self.combo_type_filtre = self._combo(self.filter_type_row, ["Nom", "Mois", "Statut des versements", "Statut souscription", "Devise"], "Nom", 170)
        self.combo_type_filtre.configure(command=self._on_filter_type_change)
        self.combo_type_filtre.pack(side="left", padx=(0, 10))

        self.filter_value_row = ctk.CTkFrame(f, fg_color="transparent")
        self.filter_value_row.pack(fill="x", padx=16, pady=(0, 10))
        self.filter_value_holder = ctk.CTkFrame(self.filter_value_row, fg_color="transparent")
        self.filter_value_holder.pack(side="left", fill="x", expand=True)
        self._build_filter_value_widget("Nom")

        self.filter_actions_row = ctk.CTkFrame(f, fg_color="transparent")
        self.filter_actions_row.pack(fill="x", padx=16, pady=(0, 10))

        self.btn_add_filter = ctk.CTkButton(self.filter_actions_row, text="Ajouter", width=96, height=32,
                                            fg_color=C["accent"], hover_color=C["accent_dim"],
                                            text_color="#000000", font=ctk.CTkFont(size=12, weight="bold"),
                                            corner_radius=6, command=self._add_or_update_filter)
        self.btn_add_filter.pack(side="left", padx=(0, 8))
        self.btn_apply_filters = ctk.CTkButton(self.filter_actions_row, text="Appliquer", width=92, height=32,
                                               fg_color=C["bg_section"], hover_color=C["border"],
                                               text_color=C["text_hi"], font=ctk.CTkFont(size=12, weight="bold"),
                                               corner_radius=6, command=self.charger_donnees)
        self.btn_apply_filters.pack(side="left", padx=(0, 8))
        self.btn_reset_filters = ctk.CTkButton(self.filter_actions_row, text="Tout", width=70, height=32,
                                               fg_color=C["bg_section"], hover_color=C["border"],
                                               text_color=C["text_lo"], corner_radius=6,
                                               command=self._reset_filters)
        self.btn_reset_filters.pack(side="left")
        self.btn_history = ctk.CTkButton(
            self.filter_actions_row,
            text="📋 Historique",
            width=112,
            height=32,
            fg_color=C["bg_section"],
            hover_color=C["border"],
            text_color=C["text_hi"],
            corner_radius=6,
            command=self.afficher_historique_locataire,
        )
        self.btn_history.pack(side="left", padx=(10, 0))
        self.btn_payment_proofs = ctk.CTkButton(
            self.filter_actions_row,
            text="💳 À valider",
            width=100,
            height=32,
            fg_color=C["bg_section"],
            hover_color=C["border"],
            text_color=C["text_hi"],
            corner_radius=6,
            command=self.ouvrir_preuves_paiement,
        )
        self.btn_payment_proofs.pack(side="left", padx=(8, 0))
        
        # Bouton Archives aligné à droite
        self.btn_archives = ctk.CTkButton(self.filter_actions_row, text="🗃️ Archives", width=100, height=32,
                                          fg_color=C["bg_card"], hover_color=C["border"], border_width=1,
                                          border_color=C["border"], text_color=C["text_hi"],
                                          corner_radius=6, command=self._show_archives_page)
        self.btn_archives.pack(side="right")

        chips_header = ctk.CTkFrame(f, fg_color="transparent")
        chips_header.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(chips_header, text="Filtres actifs",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C["text_lo"]).pack(side="left")

        self.active_filters_frame = ctk.CTkFrame(f, fg_color="transparent")
        self.active_filters_frame.pack(fill="x", padx=16, pady=(0, 12))
        self._refresh_active_filters_ui()

    def _build_special_rollover_bar(self, parent):
        """Barre de basculement manuel des souscripteurs Spécial."""
        bar = ctk.CTkFrame(parent, fg_color=C["bg_section"], corner_radius=8)
        bar.pack(fill="x", padx=16, pady=(0, 10))
        self.special_rollover_bar = bar

        header = ctk.CTkFrame(bar, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            header,
            text="Basculement mensuel Spécial",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=C["text_hi"],
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text="Choisissez le mois cible, puis lancez le basculement manuellement.",
            font=ctk.CTkFont(size=10),
            text_color=C["text_lo"],
        ).pack(side="left", padx=(10, 0))

        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(
            row,
            text="Mois cible",
            font=ctk.CTkFont(size=11),
            text_color=C["text_lo"],
        ).pack(side="left", padx=(0, 8))

        rollover_choices = build_special_rollover_month_choices()
        default_month = rollover_choices[0] if rollover_choices else ""
        self.combo_special_rollover_month = self._combo(
            row,
            rollover_choices,
            default_month,
            260,
        )
        self.combo_special_rollover_month.pack(side="left", padx=(0, 10))

        self.btn_special_rollover = ctk.CTkButton(
            row,
            text="Basculement mensuel",
            width=170,
            height=32,
            fg_color=C["accent"],
            hover_color=C["accent_dim"],
            text_color="#000000",
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=6,
            command=self.lancer_basculement_special_manuel,
        )
        self.btn_special_rollover.pack(side="left")

    def lancer_basculement_special_manuel(self):
        """Duplique les souscripteurs Spécial vers le mois choisi."""
        mois_label = self.combo_special_rollover_month.get().strip()
        mois_cible = parse_mois_saisie(mois_label)
        if not mois_cible:
            messagebox.showerror(
                "Basculement Spécial",
                "Veuillez sélectionner un mois cible valide (à partir de 10/2025).",
                parent=self,
            )
            return

        mois_affiche = format_month_label(mois_cible)
        if not messagebox.askyesno(
            "Confirmer le basculement",
            (
                f"Basculement manuel des souscripteurs Spécial vers {mois_affiche} ?\n\n"
                "- Création des lignes du mois choisi pour chaque souscripteur Spécial\n"
                "- Passage en Litigieux des mois antérieurs encore « En attente »\n"
                "- Opération journalisée : un second basculement pour le même mois sera refusé"
            ),
            parent=self,
        ):
            return

        self.btn_special_rollover.configure(state="disabled")
        self._set_status(f"Basculement Spécial en cours pour {mois_affiche}...")
        try:
            rapport = executer_basculement_special_manuel(mois_cible)
            status = rapport.get("status", "unknown")
            message = rapport.get("message", "")

            if status == "done":
                creations = int(rapport.get("created", 0) or 0)
                details = rapport.get("details") or {}
                litigieux = int(details.get("overdue_updates", 0) or 0)
                messagebox.showinfo(
                    "Basculement terminé",
                    message
                    or (
                        f"Basculement vers {mois_affiche} terminé : "
                        f"{creations} création(s), {litigieux} passage(s) en Litigieux."
                    ),
                    parent=self,
                )
                self._set_status(f"Basculement Spécial terminé pour {mois_affiche}.")
                self.charger_donnees()
            elif status == "already_done":
                messagebox.showinfo(
                    "Basculement déjà effectué",
                    message or f"Le basculement pour {mois_affiche} a déjà été exécuté.",
                    parent=self,
                )
                self._set_status(message or f"Basculement déjà traité pour {mois_affiche}.")
            elif status == "running":
                messagebox.showwarning(
                    "Basculement en cours",
                    message or "Une migration est déjà en cours pour ce mois.",
                    parent=self,
                )
                self._set_status(message or "Basculement Spécial déjà en cours.")
            else:
                messagebox.showerror(
                    "Erreur de basculement",
                    message or "Le basculement Spécial a échoué.",
                    parent=self,
                )
                self._set_status(message or "Erreur lors du basculement Spécial.")
        except Exception as exc:
            messagebox.showerror(
                "Erreur de basculement",
                f"Impossible d'exécuter le basculement Spécial : {exc}",
                parent=self,
            )
            self._set_status(f"Erreur basculement Spécial : {exc}")
        finally:
            self.btn_special_rollover.configure(state="normal")

    # ── ONGLET TABLEAU ───────────────────────────────────────────────────────
    def _build_tab_table(self, parent):
        self.tab_table_body = ctk.CTkFrame(parent, fg_color="transparent")
        self.tab_table_body.pack(fill="both", expand=True, padx=10, pady=10)

        # Diviser en deux: gauche pour les stats, droite pour le tableau
        self.left_pane = ctk.CTkFrame(self.tab_table_body, fg_color="transparent", width=250)
        self.left_pane.pack(side="left", fill="y", padx=(0, 10))
        
        self.right_pane = ctk.CTkFrame(self.tab_table_body, fg_color="transparent")
        self.right_pane.pack(side="right", fill="both", expand=True)

        # Cartes stats verticales
        self.table_stats_col = ctk.CTkFrame(self.left_pane, fg_color="transparent")
        self.table_stats_col.pack(fill="x", pady=(8, 12))

        self.card_total     = StatCard(self.table_stats_col, "📋", "Total",         C["blue"])
        self.card_payes     = StatCard(self.table_stats_col, "✅", "En règle",          C["green"])
        self.card_litigieux = StatCard(self.table_stats_col, "⚠️", "Litigieux",      C["orange"])
        self.card_attente   = StatCard(self.table_stats_col, "⏳", "En attente",     C["text_lo"])
        self.table_cards = [self.card_total, self.card_payes, self.card_litigieux, self.card_attente]
        
        for card in self.table_cards:
            card.pack(fill="x", pady=(0, 10))
            if hasattr(card, "set_density"):
                card.set_density(value_size=26, label_size=11, sub_size=10, icon_size=12)

        # Header compteur
        tbl_hdr = ctk.CTkFrame(self.right_pane, fg_color="transparent")
        tbl_hdr.pack(fill="x", padx=4, pady=(0, 6))
        ctk.CTkLabel(tbl_hdr, text="Enregistrements",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C["text_hi"]).pack(side="left")
        self.lbl_count = ctk.CTkLabel(tbl_hdr, text="0 résultat",
                                       font=ctk.CTkFont(size=11),
                                       text_color=C["text_lo"])
        self.lbl_count.pack(side="right")

        self.lbl_table_hint = ctk.CTkLabel(
            self.right_pane,
            text="Page dédiée aux enregistrements : double-clic pour l'historique, clic droit pour changer le statut.",
            font=ctk.CTkFont(size=11),
            text_color=C["text_lo"],
        )
        self.lbl_table_hint.pack(anchor="w", padx=4, pady=(0, 6))

        # Treeview
        tbl_inner = ctk.CTkFrame(self.right_pane, fg_color=C["bg_card"],
                                  corner_radius=8, border_width=1,
                                  border_color=C["border"])
        tbl_inner.pack(fill="both", expand=True)

        cols = ("Nom", "Prénom", "Mois", "Montant", "Devise", "Statut Souscription", "Statut des versements", "Signé")
        self.tableau = ttk.Treeview(tbl_inner, columns=cols, show="headings",
                                    style="TAP.Treeview", height=8)
        widths = {"Nom": 230, "Prénom": 205, "Mois": 150,
                  "Montant": 140, "Devise": 100, "Statut Souscription": 180, "Statut": 130, "Signé": 105}
        anchors = {
            "Nom": "w",
            "Prénom": "w",
            "Mois": "center",
            "Montant": "e",
            "Devise": "center",
            "Statut Souscription": "center",
            "Statut des versements": "center",
            "Signé": "center",
        }
        for col in cols:
            self.tableau.heading(col, text=col.upper(), anchor=anchors.get(col, "center"))
            self.tableau.column(col, width=widths.get(col, 100),
                                anchor=anchors.get(col, "center"),
                                stretch=col in {"Nom", "Prénom", "Statut Souscription"},
                                minwidth=70)

        sb_y = ctk.CTkScrollbar(tbl_inner, command=self.tableau.yview,
                                fg_color=C["bg_section"],
                                button_color=C["border"],
                                button_hover_color=C["accent_dim"])
        sb_x = ctk.CTkScrollbar(tbl_inner, orientation="horizontal", command=self.tableau.xview,
                                fg_color=C["bg_section"],
                                button_color=C["border"],
                                button_hover_color=C["accent_dim"])
        self.tableau.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.pack(side="right", fill="y", padx=(2, 4), pady=4)
        self.tableau.pack(side="left", fill="both", expand=True, padx=4, pady=(4, 0))
        sb_x.pack(side="bottom", fill="x", padx=4, pady=(0, 4))

        # Menu contextuel
        self.context_menu = Menu(self, tearoff=0, bg=C["bg_section"],
                                  fg=C["text_hi"], activebackground=C["border"],
                                  activeforeground=C["accent"], bd=0)
        self.context_menu.add_command(label="  ✏️  Modifier",
                                       command=self.modifier_paiement)
        self.context_menu.add_command(label="  📋  Voir l'historique",
                                       command=self.afficher_historique_locataire)
        self.context_menu.add_command(label="  💰  Ajouter paiement",
                                       command=self.ajouter_paiement)
        self.context_menu.add_command(label="  ✍️  Demander signature QR",
                                       command=self.demander_signature_qr)
        self.context_menu.add_command(label="  📱  Créer lien portail locataire",
                                       command=self.creer_lien_portail_locataire)
        self.context_menu.add_command(label="  💳  Créer lien de paiement",
                                       command=self.creer_lien_paiement)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="  ✅  Marquer En règle",
                                       command=lambda: self.modifier_statut("En règle"))
        self.context_menu.add_command(label="  ⚠️  Marquer Litigieux",
                                       command=lambda: self.modifier_statut("Litigieux"))
        self.context_menu.add_command(label="  ⏳  Marquer En attente",
                                       command=lambda: self.modifier_statut("En attente"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="  🗑️  Supprimer",
                                       command=self.supprimer_paiement)
        self.tableau.bind("<Button-3>", self.afficher_menu_contextuel)
        self.tableau.bind("<Double-1>", self.afficher_historique_locataire)
        self.tableau.bind("<Return>", self.afficher_historique_locataire)

    # ── ONGLET DASHBOARD ─────────────────────────────────────────────────────
    def _build_tab_dashboard(self, parent):
        self.tab_dash_body = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.tab_dash_body.pack(fill="both", expand=True)

        # Filtre devise
        filter_row = ctk.CTkFrame(self.tab_dash_body, fg_color="transparent")
        filter_row.pack(fill="x", pady=(8, 12))
        
        ctk.CTkLabel(filter_row, text="Filtrer par devise :",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C["text_lo"]).pack(side="left", padx=(0, 8))
        
        self.combo_devise_dashboard = self._combo(filter_row, 
                                                   ["Toutes", "CDF", "USD", "EUR", "XAF", "CAD"], 
                                                   "Toutes", 150)
        self.combo_devise_dashboard.pack(side="left", padx=(0, 8))
        
        ctk.CTkButton(filter_row, text="Appliquer", width=80, height=32,
                      fg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="#000000", font=ctk.CTkFont(size=12, weight="bold"),
                      corner_radius=6, command=self._update_dashboard_with_filter
                      ).pack(side="left", padx=(0, 8))
        
        ctk.CTkButton(filter_row, text="✕", width=32, height=32,
                      fg_color=C["bg_section"], hover_color=C["border"],
                      text_color=C["text_lo"], corner_radius=6,
                      command=self._reset_dashboard_filter
                      ).pack(side="left")
        
        # KPIs financiers
        self.kpi_row = ctk.CTkFrame(self.tab_dash_body, fg_color="transparent")
        kpi_row = self.kpi_row
        kpi_row.pack(fill="x", pady=(8, 12))
        kpi_row.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="k")

        self.kpi_montant_total = AnimatedStatCard(kpi_row, "💰", "Montant total",   C["accent"])
        self.kpi_moyenne       = AnimatedStatCard(kpi_row, "📐", "Moyenne/paiement", C["blue"])
        self.kpi_max           = AnimatedStatCard(kpi_row, "📈", "Paiement max",     C["green"])
        self.kpi_mois_actif    = AnimatedStatCard(kpi_row, "📅", "Mois le plus actif", C["orange"])
        self.kpi_count         = AnimatedStatCard(kpi_row, "📊", "Total paiements", C["text_lo"])
        self.kpi_cards = [self.kpi_montant_total, self.kpi_moyenne,
                          self.kpi_max, self.kpi_mois_actif, self.kpi_count]
        self._layout_kpi_cards(5)

        # Zone graphiques (2 colonnes)
        self.charts = ctk.CTkFrame(self.tab_dash_body, fg_color="transparent")
        charts = self.charts
        charts.pack(fill="both", expand=True)
        charts.columnconfigure(0, weight=3)
        charts.columnconfigure(1, weight=2)
        charts.rowconfigure(0, weight=1)

        # Graphique barres (montants par mois)
        self.frame_bar = ctk.CTkFrame(charts, fg_color=C["bg_card"],
                                       corner_radius=12, border_width=1,
                                       border_color=C["border"])
        self.frame_bar.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        bar_hdr = ctk.CTkFrame(self.frame_bar, fg_color="transparent")
        bar_hdr.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkLabel(bar_hdr, text="Montants par mois",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C["text_hi"]).pack(side="left")
        self.lbl_devise_bar = ctk.CTkLabel(bar_hdr, text="",
                                            font=ctk.CTkFont(size=10),
                                            text_color=C["text_lo"])
        self.lbl_devise_bar.pack(side="right")

        ctk.CTkFrame(self.frame_bar, height=1, fg_color=C["border"]).pack(fill="x", padx=0)

        self.canvas_bar_frame = ctk.CTkFrame(self.frame_bar, fg_color="transparent")
        self.canvas_bar_frame.pack(fill="both", expand=True, padx=8, pady=8)
        self._fig_bar = Figure(figsize=(6, 3.4), facecolor=MPL["bg"])
        self._ax_bar  = self._fig_bar.add_subplot(111, facecolor=MPL["axes"])
        self._canvas_bar = FigureCanvasTkAgg(self._fig_bar, self.canvas_bar_frame)
        self._canvas_bar.get_tk_widget().pack(fill="both", expand=True)

        # Graphique camembert (statuts)
        self.frame_pie = ctk.CTkFrame(charts, fg_color=C["bg_card"],
                                       corner_radius=12, border_width=1,
                                       border_color=C["border"])
        self.frame_pie.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(self.frame_pie, text="Répartition des statuts",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C["text_hi"]).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkFrame(self.frame_pie, height=1, fg_color=C["border"]).pack(fill="x")

        self.canvas_pie_frame = ctk.CTkFrame(self.frame_pie, fg_color="transparent")
        self.canvas_pie_frame.pack(fill="both", expand=True, padx=8, pady=8)
        self._fig_pie = Figure(figsize=(4, 3.4), facecolor=MPL["bg"])
        self._ax_pie  = self._fig_pie.add_subplot(111, facecolor=MPL["bg"])
        self._canvas_pie = FigureCanvasTkAgg(self._fig_pie, self.canvas_pie_frame)
        self._canvas_pie.get_tk_widget().pack(fill="both", expand=True)

    # ── STYLES TTK ───────────────────────────────────────────────────────────
    def _apply_table_style(self):
        self._table_style = ttk.Style()
        self._table_style.theme_use("default")
        self._table_style.configure("TAP.Treeview", background=C["bg_card"], foreground=C["text_hi"],
                                    rowheight=44, fieldbackground=C["bg_card"],
                                    borderwidth=0, font=("Segoe UI", 10))
        self._table_style.configure("TAP.Treeview.Heading", background=C["tbl_head"],
                                    foreground=C["text_lo"], relief="flat",
                                    font=("Segoe UI", 10, "bold"), padding=(12, 14))
        self._table_style.map("TAP.Treeview",
                              background=[("selected", C["tbl_select"])],
                              foreground=[("selected", C["text_hi"])])
        self._table_style.map("TAP.Treeview.Heading",
                              background=[("active", C["bg_section"])])
        self.tableau.tag_configure("even",   background=C["tbl_even"])
        self.tableau.tag_configure("odd",    background=C["tbl_odd"])
        self.tableau.tag_configure("paye",   foreground=C["green"])
        self.tableau.tag_configure("litige", foreground=C["orange"])
        self.tableau.tag_configure("attente",foreground=C["blue"])

    def _set_initial_geometry(self):
        self.update_idletasks()
        screen_width = self._screen.width
        screen_height = self._screen.height

        if min(screen_width, screen_height) < 900:
            width_ratio, height_ratio = 0.96, 0.92
            min_width, min_height = 700, 520
        elif screen_width < 1366:
            width_ratio, height_ratio = 0.92, 0.86
            min_width, min_height = 900, 640
        elif screen_width < 1920:
            width_ratio, height_ratio = 0.90, 0.90
            min_width, min_height = 1100, 760
        else:
            width_ratio, height_ratio = 0.86, 0.88
            min_width, min_height = 1200, 820

        width, height = clamp_window_geometry(
            screen_width,
            screen_height,
            width_ratio=width_ratio,
            height_ratio=height_ratio,
            min_width=min_width,
            min_height=min_height,
        )

        x = max((screen_width - width) // 2, 0)
        y = max((screen_height - height) // 2, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _on_window_resize(self, event):
        if event.widget is not self or self._resize_lock:
            return
            
        # Ignorer les changements minimes
        if abs(event.width - self._last_width) < 50:
            return
            
        self._last_width = event.width
        
        if self._responsive_after_id is not None:
            self.after_cancel(self._responsive_after_id)
        self._responsive_after_id = self.after(100, self._apply_responsive_layout)

    def _apply_responsive_layout(self):
        self._responsive_after_id = None
        if not hasattr(self, "frame_bar") or not hasattr(self, "kpi_cards"):
            return

        width = self.winfo_width()
        if width <= 1:
            return

        profile = build_layout_profile(width)
        if self._layout_profile == profile:
            return

        self._resize_lock = True
        try:
            self._layout_profile = profile
            self._layout_sidebar(profile)
            self._layout_main(profile)
            self._layout_filters(profile)
            self._layout_table_cards(profile.table_card_columns)
            self._layout_kpi_cards(profile.kpi_columns)
            self._layout_dashboard_charts(profile.chart_mode)
            self._layout_table_columns(profile)
            self._layout_dashboard_filters(profile)
        finally:
            self._resize_lock = False

    def _layout_sidebar(self, profile):
        if hasattr(self, "sidebar_frame"):
            self.sidebar_frame.configure(width=profile.sidebar_width)
        if hasattr(self, "sidebar_brand"):
            self.sidebar_brand.configure(font=ctk.CTkFont(family="Georgia", size=profile.sidebar_brand_size, weight="bold"))
        if hasattr(self, "sidebar_subtitle"):
            self.sidebar_subtitle.configure(font=ctk.CTkFont(size=profile.sidebar_subtitle_size, weight="bold"))
        if hasattr(self, "sidebar_footer"):
            self.sidebar_footer.configure(font=ctk.CTkFont(size=max(9, profile.sidebar_subtitle_size - 1)))
        for button in getattr(self, "sidebar_buttons", []):
            try:
                button.configure(font=ctk.CTkFont(size=profile.sidebar_button_size, weight="bold" if button is self.sidebar_buttons[0] else "normal"))
            except Exception:
                pass

    def _layout_main(self, profile):
        if hasattr(self, "main_frame"):
            self.main_frame.pack_configure(padx=profile.main_padding, pady=profile.main_padding)
        if hasattr(self, "header_title"):
            self.header_title.configure(font=ctk.CTkFont(family="Georgia", size=profile.header_title_size, weight="bold"))
        if hasattr(self, "header_subtitle"):
            self.header_subtitle.configure(font=ctk.CTkFont(size=profile.header_subtitle_size))
        if hasattr(self, "status_bar"):
            self.status_bar.configure(font=ctk.CTkFont(size=max(10, profile.header_subtitle_size - 1)))
        if hasattr(self, "filters_title"):
            self.filters_title.configure(font=ctk.CTkFont(size=max(12, profile.header_subtitle_size), weight="bold"))
        if hasattr(self, "filters_help"):
            self.filters_help.configure(font=ctk.CTkFont(size=max(9, profile.header_subtitle_size - 2)))
        if hasattr(self, "lbl_count"):
            self.lbl_count.configure(font=ctk.CTkFont(size=max(10, profile.header_subtitle_size - 1)))
        if hasattr(self, "lbl_table_hint"):
            self.lbl_table_hint.configure(font=ctk.CTkFont(size=max(9, profile.header_subtitle_size - 2)))

    def _layout_filters(self, profile):
        if not hasattr(self, "combo_type_filtre"):
            return

        try:
            self.combo_type_filtre.configure(width=150 if profile.name == "compact" else 170)
            self.combo_type_filtre.pack_configure(side="left", padx=(0, 10))
        except Exception:
            pass

        try:
            self.filter_value_holder.pack_configure(side="left" if profile.filter_mode == "inline" else "left", fill="x", expand=True)
        except Exception:
            pass

        for button in (getattr(self, "btn_add_filter", None), getattr(self, "btn_apply_filters", None), getattr(self, "btn_reset_filters", None)):
            if button:
                try:
                    button.configure(height=30 if profile.name == "compact" else 32)
                except Exception:
                    pass

        if hasattr(self, "filters_card"):
            try:
                if profile.filter_mode == "inline":
                    self.filters_card.configure(corner_radius=10)
                else:
                    self.filters_card.configure(corner_radius=12)
            except Exception:
                pass

    def _layout_dashboard_filters(self, profile):
        if hasattr(self, "combo_devise_dashboard"):
            try:
                self.combo_devise_dashboard.configure(width=130 if profile.name == "compact" else 150)
            except Exception:
                pass

    def _layout_table_columns(self, profile):
        if not hasattr(self, "tableau"):
            return

        try:
            self._table_style.configure(
                "TAP.Treeview",
                rowheight=profile.table_row_height,
                font=("Segoe UI", profile.table_body_font_size),
            )
            self._table_style.configure(
                "TAP.Treeview.Heading",
                font=("Segoe UI", profile.table_head_font_size, "bold"),
            )
        except Exception:
            pass

        for column, width in profile.table_widths.items():
            try:
                self.tableau.column(column, width=width, minwidth=max(60, width - 40))
            except Exception:
                pass

        # Garder les enregistrements lisibles sur les écrans étroits. Les
        # colonnes secondaires restent disponibles dans l'historique et via
        # la barre horizontale, mais ne réduisent plus la liste à quelques
        # pixels de largeur.
        try:
            self.tableau.configure(displaycolumns=table_display_columns(profile.name))
        except Exception:
            pass

        if hasattr(self, "left_pane") and hasattr(self, "right_pane"):
            try:
                if records_page_uses_full_width(profile.name):
                    self.left_pane.pack_forget()
                    self.right_pane.pack(side="top", fill="both", expand=True)
                    self.lbl_table_hint.configure(
                        text="Écran étroit : la liste occupe toute la largeur. Les colonnes secondaires restent accessibles avec la barre horizontale et dans l'historique."
                    )
                else:
                    self.right_pane.pack_forget()
                    self.left_pane.pack(side="left", fill="y", padx=(0, 10))
                    self.right_pane.pack(side="right", fill="both", expand=True)
            except Exception:
                pass

    def _layout_table_cards(self, columns: int):
        self._current_table_card_columns = columns

    def _layout_kpi_cards(self, columns: int):
        if self._current_kpi_columns == columns:
            return

        for card in self.kpi_cards:
            card.grid_forget()

        for index in range(columns):
            self.kpi_row.columnconfigure(index, weight=1, uniform="k")
        for index in range(columns, 5):
            self.kpi_row.columnconfigure(index, weight=0, minsize=0)

        self.kpi_row.rowconfigure(0, weight=1)
        self.kpi_row.rowconfigure(1, weight=1 if columns < 5 else 0)
        self.kpi_row.rowconfigure(2, weight=1 if columns == 2 else 0)

        if columns >= 5:
            positions = [(0, index, 1) for index in range(5)]
        elif columns == 3:
            positions = [(0, 0, 1), (0, 1, 1), (0, 2, 1), (1, 0, 1), (1, 1, 1)]
        else:
            positions = [(0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 1), (2, 0, 2)]

        for card, (row, column, columnspan) in zip(self.kpi_cards, positions):
            card.grid(row=row, column=column, columnspan=columnspan, sticky="nsew",
                      padx=(0, 10) if columnspan == 1 and column < columns - 1 else 0,
                      pady=(0, 10) if columns < 5 else 0)
            if hasattr(card, "set_density"):
                if columns == 2:
                    card.set_density(value_size=22, label_size=10, sub_size=9, icon_size=11)
                elif columns == 3:
                    card.set_density(value_size=24, label_size=10, sub_size=9, icon_size=11)
                else:
                    card.set_density(value_size=28, label_size=11, sub_size=10, icon_size=12)

        self._current_kpi_columns = columns

    def _layout_dashboard_charts(self, mode: str):
        if self._current_chart_layout == mode:
            return

        self.frame_bar.grid_forget()
        self.frame_pie.grid_forget()

        for index in range(2):
            self.charts.rowconfigure(index, weight=0, minsize=0)
            self.charts.columnconfigure(index, weight=0, minsize=0)

        if mode == "stacked":
            self.charts.columnconfigure(0, weight=1)
            self.charts.rowconfigure(0, weight=1)
            self.charts.rowconfigure(1, weight=1)
            self.frame_bar.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
            self.frame_pie.grid(row=1, column=0, sticky="nsew")
        else:
            self.charts.columnconfigure(0, weight=3)
            self.charts.columnconfigure(1, weight=2)
            self.charts.rowconfigure(0, weight=1)
            self.frame_bar.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
            self.frame_pie.grid(row=0, column=1, sticky="nsew")

        self._current_chart_layout = mode

    def _schedule_automatic_maintenance(self):
        """Planifie l'entretien automatique périodique."""
        if self._maintenance_after_id is not None:
            try:
                self.after_cancel(self._maintenance_after_id)
            except Exception:
                pass
        self._maintenance_after_id = self.after(30 * 60 * 1000, self._run_automatic_maintenance)

    def _run_automatic_maintenance(self):
        """Relance la maintenance automatique et la replanifie."""
        self._maintenance_after_id = None
        try:
            rapport = executer_mise_a_jour_automatique()

            message_statut = "🔄 Maintenance automatique effectuée."
            notifications = []
            quiet_notes = []

            rollover_status = rapport.get("rollover_special_status")
            rollover_month = rapport.get("rollover_special_month") or rapport.get("date", "")
            if rollover_status == "manual_only":
                pass
            elif rollover_status == "done":
                rollover_message = rapport.get("rollover_special_message")
                if rollover_message:
                    notifications.append(rollover_message)
                else:
                    creations = int(rapport.get("creations_speciales", 0) or 0)
                    notifications.append(
                        f"Migration mensuelle terminée pour {rollover_month} : "
                        f"{creations} souscripteur(s) spécial(aux) dupliqué(s)."
                    )
            elif rollover_status == "already_done":
                quiet_notes.append(f"Migration mensuelle déjà traitée pour {rollover_month}.")

            reminder_count = int(rapport.get("litigieux_reminder_count", 0) or 0)
            reminder_status = rapport.get("litigieux_reminder_status")
            reminder_month = rapport.get("litigieux_reminder_month") or rapport.get("date", "")
            if reminder_status == "done" and reminder_count > 0:
                reminder_message = rapport.get("litigieux_reminder_message")
                if reminder_message:
                    notifications.append(reminder_message)
                else:
                    reminder_details = rapport.get("litigieux_reminder_details", {})
                    reminder_sample = reminder_details.get("sample", [])
                    reminder_text = (
                        f"Rappel litigieux pour {reminder_month} : "
                        f"{reminder_count} paiement(s) encore à traiter."
                    )
                    if reminder_sample:
                        reminder_text += "\n\nExemples:\n" + "\n".join(
                            f"- {item}" for item in reminder_sample[:5]
                        )
                    notifications.append(reminder_text)
            elif reminder_status == "already_done" and reminder_count > 0:
                quiet_notes.append(f"Rappel litigieux déjà envoyé pour {reminder_month}.")

            if rapport.get("erreurs", 0):
                message_statut = f"⚠️ Maintenance terminée avec {rapport['erreurs']} erreur(s)."
                if notifications:
                    message_statut += " " + " | ".join(notifications)
                if quiet_notes:
                    message_statut += " " + " | ".join(quiet_notes)
                self.after(
                    0,
                    lambda msg=message_statut: messagebox.showwarning(
                        "Maintenance automatique",
                        msg,
                    ),
                )
            elif notifications:
                message_statut = "📣 " + " | ".join(notifications)
                if quiet_notes:
                    message_statut += " | " + " | ".join(quiet_notes)
                self.after(
                    0,
                    lambda msg=message_statut: messagebox.showinfo(
                        "Maintenance automatique",
                        msg,
                    ),
                )
            elif quiet_notes:
                message_statut = "ℹ️ " + " | ".join(quiet_notes)

            if not self._is_loading:
                self._set_status(message_statut)
        except Exception as e:
            self._set_status(f"⚠️ Maintenance automatique en erreur: {e}")
        finally:
            if self.winfo_exists():
                self._schedule_automatic_maintenance()

    # ── LOGIQUE PRINCIPALE ───────────────────────────────────────────────────
    def ouvrir_formulaire(self):
        # Sécurité : fermer tout dialogue existant avant d'en ouvrir un nouveau
        self._fermer_dialogues_ouverts()

        def _apres_creation(details=None):
            """Recharge les données et navigue vers la page enregistrements."""
            self._reset_filters()
            self._show_records_page()
            if details and self._montant_positif(details.get("montant_paye", 0)):
                paiement_id = details.get("paiement_id")
                if paiement_id:
                    self._ouvrir_signature_apres_paiement(
                        paiement_id,
                        details.get("montant_paye"),
                    )
            # Nettoyer la référence après fermeture
            if self._current_dialog is not None and not self._current_dialog.winfo_exists():
                self._current_dialog = None

        # Garder une référence pour éviter le garbage collection
        self._current_dialog = NouveauSouscripteurDialog(self, callback_maj_tableau=_apres_creation)

    def _fermer_dialogues_ouverts(self):
        """Ferme proprement tous les dialogues référencés avant d'en ouvrir de nouveaux."""
        dialog_attrs = [
            '_current_dialog',
            '_export_pdf_dialog',
            '_archives_dialog',
            '_portal_qr_dialog',
            '_payment_qr_dialog',
            '_signature_qr_dialog',
            '_payment_proofs_dialog',
            '_history_dialog',
        ]
        for attr in dialog_attrs:
            dialog = getattr(self, attr, None)
            if dialog is not None:
                try:
                    if dialog.winfo_exists():
                        try:
                            dialog.grab_release()
                        except Exception:
                            pass
                        dialog.destroy()
                except Exception:
                    pass
                setattr(self, attr, None)

    def charger_donnees(self):
        if self._is_loading:
            return
            
        self._show_loading("Chargement des données...")
        self.update_idletasks()
        
        try:
            lignes = [
                SubscriptionRecord.from_row(row)
                for row in self.payment_service.list_subscriptions(
                    SubscriptionFilters(
                        name=self.active_filters["nom"],
                        status=self.active_filters["statut"],
                        currency=self.active_filters["devise"],
                        month=self.active_filters["mois"],
                        subscription_status=self.active_filters["statut_souscription"],
                    )
                )
            ]

            self._all_data = lignes
            self._row_meta.clear()
            # ── Remplir le tableau par lots
            items = self.tableau.get_children()
            if items:
                self.tableau.delete(*items)
                
            batch_size = 100
            for i in range(0, len(lignes), batch_size):
                batch = lignes[i:i+batch_size]
                for j, record in enumerate(batch):
                    idx = i + j
                    paiement_id = record.payment_id
                    valeurs_visibles = (
                        record.last_name,
                        record.first_name,
                        record.month,
                        record.amount,
                        record.currency,
                        record.subscription_status,
                        record.status,
                        "✓ Signé" if record.is_signed else "—",
                    )
                    tag = "even" if idx % 2 == 0 else "odd"
                    sv = record.status
                    st  = {"En règle": "paye", "Litigieux": "litige",
                           "En attente": "attente"}.get(sv, "")
                    item_id = str(paiement_id)
                    self.tableau.insert("", "end", iid=item_id, values=valeurs_visibles, tags=(tag, st))
                    self._row_meta[item_id] = record.to_metadata()
                self.update_idletasks()

            if lignes:
                first_item = self.tableau.get_children()[0]
                self.tableau.selection_set(first_item)
                self.tableau.focus(first_item)
                self.lbl_table_hint.configure(
                    text="Astuce : double-clic pour l'historique, clic droit pour modifier/ajouter paiement/supprimer/changer le statut. Le statut est aussi automatique selon le paiement."
                )
            else:
                self.lbl_table_hint.configure(
                    text="Aucun résultat. Retirez un filtre ou cliquez sur « Tout » pour élargir la recherche."
                )

            # ── Stats cartes tableau
            total     = len(lignes)
            payes     = sum(1 for record in lignes if record.status == "En règle")
            litigieux = sum(1 for record in lignes if record.status == "Litigieux")
            attente   = sum(1 for record in lignes if record.status == "En attente")
            self.card_total.update(total)
            self.card_payes.update(payes)
            self.card_litigieux.update(litigieux)
            self.card_attente.update(attente)
            self.lbl_count.configure(
                text=f"{total} résultat{'s' if total != 1 else ''}" if total else "Aucun résultat")

            # ── Mettre à jour le dashboard différé
            self.after(50, lambda: self._update_dashboard(lignes))
            
            if total:
                self._set_status(f"✅ {total} résultat{'s' if total != 1 else ''} chargé{'s' if total != 1 else ''}.")
            else:
                self._set_status("ℹ️ Aucun résultat chargé.")

        except Exception as e:
            self._set_status(f"❌ Erreur de chargement : {str(e)}")
            messagebox.showerror("Erreur", f"Impossible de charger les données : {str(e)}")
        finally:
            self._hide_loading()

    def _update_dashboard_with_filter(self):
        """Met à jour le dashboard avec le filtre de devise"""
        devise_filtre = self.combo_devise_dashboard.get()
        lignes = self._all_data
        
        if devise_filtre != "Toutes":
            lignes = [record for record in lignes if record.currency.upper() == devise_filtre.upper()]
        
        self._update_dashboard(lignes)
    
    def _reset_dashboard_filter(self):
        """Réinitialise le filtre de devise"""
        self.combo_devise_dashboard.set("Toutes")
        self._update_dashboard(self._all_data)

    def _update_dashboard(self, lignes: list):
        """Recalcule les KPIs et redessine les graphiques."""
        metrics = calculate_dashboard_metrics(lignes)
        devise_unique = metrics.currencies[0] if len(metrics.currencies) == 1 else ""
        devises_multiples = metrics.has_multiple_currencies

        if devises_multiples:
            self.kpi_montant_total.update("—", f"{len(metrics.currencies)} devises")
            self.kpi_moyenne.update("—", "Filtrer une devise")
            self.kpi_max.update("—", "Filtrer une devise")
        else:
            self.kpi_montant_total.update(f"{metrics.total_amount:,.0f}", devise_unique)
            self.kpi_moyenne.update(f"{metrics.average_amount:,.0f}", devise_unique)
            self.kpi_max.update(f"{metrics.maximum_amount:,.0f}", devise_unique)
        self.kpi_mois_actif.update(metrics.busiest_month, f"{metrics.busiest_month_count} paiement(s)")
        self.kpi_count.update(metrics.count, "paiements")

        self._draw_bar_chart(lignes, devise_unique, devises_multiples)
        self._draw_pie_chart(lignes)

    def _draw_bar_chart(self, lignes: list, dev_label: str, devises_multiples: bool):
        ax = self._ax_bar
        ax.clear()
        ax.set_facecolor(MPL["axes"])
        self._fig_bar.patch.set_facecolor(MPL["bg"])

        if devises_multiples:
            ax.text(0.5, 0.5,
                    "Filtrez une devise pour voir les montants",
                    ha="center", va="center",
                    color=MPL["text"], fontsize=12, transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.spines[:].set_visible(False)
            self._fig_bar.tight_layout(pad=0.5)
            self._canvas_bar.draw()
            self.lbl_devise_bar.configure(text="Devises multiples")
            return

        # Agréger montants par mois
        sums: dict = defaultdict(float)
        for record in lignes:
            try:
                sums[str(record.month)] += float(str(record.amount).replace(",", "."))
            except (TypeError, ValueError):
                pass

        if not sums:
            ax.text(0.5, 0.5, "Aucune donnée", ha="center", va="center",
                    color=MPL["text"], fontsize=12, transform=ax.transAxes)
            self._canvas_bar.draw()
            self.lbl_devise_bar.configure(text="")
            return

        # Limiter aux 10 derniers mois en ordre chronologique réel
        sorted_items = sorted(sums.items(), key=lambda x: month_sort_key(x[0]))[-10:]
        labels = [it[0] for it in sorted_items]
        values = [it[1] for it in sorted_items]

        bars = ax.bar(labels, values, color=MPL["accent"], width=0.6,
                      edgecolor="none", zorder=3)

        # Couleur dégradée
        max_v = max(values) or 1
        for bar, val in zip(bars, values):
            ratio = val / max_v
            r = int(0x8A + ratio * (0xC9 - 0x8A))
            g = int(0x70 + ratio * (0xA8 - 0x70))
            b = int(0x35 + ratio * (0x4C - 0x35))
            bar.set_color(f"#{r:02x}{g:02x}{b:02x}")

        # Valeurs au-dessus des barres
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.02,
                    f"{val:,.0f}", ha="center", va="bottom",
                    color=MPL["text"], fontsize=7.5)

        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=30, ha="right",
                           color=MPL["text"], fontsize=8)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(
            lambda x, _: f"{x:,.0f}"))
        ax.tick_params(axis="y", colors=MPL["text"], labelsize=8)
        ax.spines[:].set_visible(False)
        ax.yaxis.grid(True, color=MPL["grid"], linewidth=0.5, zorder=0)
        ax.set_axisbelow(True)
        self._fig_bar.tight_layout(pad=0.5)
        self._canvas_bar.draw()
        self.lbl_devise_bar.configure(text=dev_label)

    def _draw_pie_chart(self, lignes: list):
        ax = self._ax_pie
        ax.clear()
        ax.set_facecolor(MPL["bg"])
        self._fig_pie.patch.set_facecolor(MPL["bg"])

        counts = Counter(record.status for record in lignes)
        if not counts:
            ax.text(0.5, 0.5, "Aucune donnée", ha="center", va="center",
                    color=MPL["text"], fontsize=12, transform=ax.transAxes)
            self._canvas_pie.draw()
            return

        labels = list(counts.keys())
        values = list(counts.values())
        colors = [STATUS_COLORS.get(lbl, MPL["text"]) for lbl in labels]

        wedges, texts, autotexts = ax.pie(
            values, labels=None, colors=colors,
            autopct="%1.0f%%", startangle=90,
            pctdistance=0.75,
            wedgeprops=dict(width=0.55, edgecolor=MPL["bg"], linewidth=2)
        )
        for at in autotexts:
            at.set_color(MPL["bg"])
            at.set_fontsize(9)
            at.set_fontweight("bold")

        ax.legend(wedges, [f"{l}  ({v})" for l, v in zip(labels, values)],
                  loc="lower center", bbox_to_anchor=(0.5, -0.15),
                  ncol=1, frameon=False,
                  labelcolor=MPL["text"], fontsize=9)

        self._fig_pie.tight_layout(pad=0.5)
        self._canvas_pie.draw()

    # ── ÉVÉNEMENTS ──────────────────────────────────────────────────────────
    def _on_tab_change(self):
        tab = self.tabs.get()
        if "Analyse" in tab:
            self._update_dashboard_with_filter()

    def _show_records_page(self):
        """Bascule vers la page des enregistrements intégrée."""
        # Cacher la page dashboard
        self.page_dashboard.pack_forget()
        # Afficher la page enregistrements
        self.page_records.pack(fill="both", expand=True)
        # Mettre à jour le header
        self.header_title.configure(text="Enregistrements")
        self.header_subtitle.configure(text="Liste des souscriptions & paiements")
        # Mettre à jour la sidebar : afficher le bouton retour, masquer le bouton enregistrements
        self.btn_nav_records.pack_forget()
        self.btn_nav_dashboard.pack(fill="x", pady=(0, 8), before=self.btn_nav_actualiser)
        # Recharger les données pour que le tableau soit à jour
        self.charger_donnees()

    def _show_special_subscribers_page(self):
        """Affiche directement les souscripteurs dont le statut est Spécial."""
        self.active_filters = {
            "nom": "",
            "mois": "",
            "statut": "Tous",
            "statut_souscription": "Spécial",
            "devise": "Toutes",
        }
        self.combo_type_filtre.set("Statut souscription")
        self._build_filter_value_widget("Statut souscription")
        self.filter_value_widget.set("Spécial")
        self._refresh_active_filters_ui()
        self._show_records_page()
        self.header_title.configure(text="Souscripteurs spéciaux")
        self.header_subtitle.configure(
            text="Basculement manuel du mois via la barre ci-dessous (à partir de 10/2025)"
        )
        self._set_status("⭐ Souscripteurs spéciaux affichés — choisissez le mois cible pour basculer.")

    def _show_dashboard_page(self):
        """Bascule vers la page du tableau de bord."""
        # Cacher la page enregistrements
        self.page_records.pack_forget()
        # Afficher la page dashboard
        self.page_dashboard.pack(fill="both", expand=True)
        # Mettre à jour le header
        self.header_title.configure(text="Tableau de bord")
        self.header_subtitle.configure(text="Souscriptions & Paiements")
        # Mettre à jour la sidebar : afficher le bouton enregistrements, masquer le bouton retour
        self.btn_nav_dashboard.pack_forget()
        self.btn_nav_records.pack(fill="x", pady=(0, 8), before=self.btn_nav_actualiser)

    def _show_archives_page(self):
        """Affiche une boîte de dialogue pour les archives."""
        try:
            # Garder une référence pour éviter le garbage collection
            self._archives_dialog = DialogArchives(self)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir les archives: {e}")

    def _reset_filters(self):
        self.active_filters = {
            "nom": "",
            "mois": "",
            "statut": "Tous",
            "statut_souscription": "Tous",
            "devise": "Toutes",
        }
        self.combo_type_filtre.set("Nom")
        self._build_filter_value_widget("Nom")
        self._refresh_active_filters_ui()
        self.charger_donnees()
        self._set_status("🔄 Filtres réinitialisés.")

    def afficher_menu_contextuel(self, event):
        item = self.tableau.identify_row(event.y)
        if item:
            self.tableau.selection_set(item)
            self.selected_item = item
            self.context_menu.post(event.x_root, event.y_root)
            values = self.tableau.item(item).get("values", [])
            if values:
                self._set_status(f"Statut prêt à modifier : {values[0]} {values[1] if len(values) > 1 else ''}".strip())

    def _get_selected_row(self):
        """Retourne l'identifiant et les métadonnées de la ligne sélectionnée."""
        item_id = getattr(self, "selected_item", None)
        if item_id and self.tableau.exists(item_id):
            meta = self._row_meta.get(str(item_id))
            if meta:
                return item_id, meta

        selection = self.tableau.selection()
        if selection:
            item_id = selection[0]
            self.selected_item = item_id
            meta = self._row_meta.get(str(item_id))
            if meta:
                return item_id, meta

        return None, None

    def modifier_statut(self, nouveau_statut: str):
        if nouveau_statut not in {"En règle", "Litigieux", "En attente"}:
            messagebox.showerror("Erreur", f"Statut invalide : {nouveau_statut}")
            return

        item_id, meta = self._get_selected_row()
        if not item_id or not meta:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement.")
            return

        self._show_loading("Mise à jour du statut...")
        try:
            success, message = self.payment_service.update_status(
                meta["paiement_id"], nouveau_statut)
            if success:
                # Animation flash sur l'item modifié
                status_colors = {
                    "En règle": "#00cc66",
                    "Litigieux": "#ff8800",
                    "En attente": "#4488ff"
                }
                if nouveau_statut in status_colors:
                    self.tableau.tag_configure("flash", background=status_colors[nouveau_statut])
                    current_tags = list(self.tableau.item(item_id, "tags"))
                    current_tags.append("flash")
                    self.tableau.item(item_id, tags=tuple(current_tags))
                    self.after(500, lambda item=item_id: self._reset_item_flash(item))

                self.charger_donnees()
                if meta.get("statut") != nouveau_statut:
                    self._set_status(
                        f"✅ {meta['nom']} {meta['prenom']} : {meta.get('statut', '')} → {nouveau_statut}"
                    )
                else:
                    self._set_status(f"ℹ️ {meta['nom']} {meta['prenom']} est déjà en {nouveau_statut}.")
            else:
                messagebox.showerror("Erreur", message)
                self._set_status("❌ La mise à jour du statut a échoué.")
        finally:
            self._hide_loading()

    def _reset_item_flash(self, item_id):
        """Réinitialise l'animation flash sur un item"""
        try:
            if self.tableau.exists(item_id):
                current_tags = list(self.tableau.item(item_id, "tags"))
                current_tags = [t for t in current_tags if t != "flash"]
                self.tableau.item(item_id, tags=tuple(current_tags))
        except Exception:
            pass

    def modifier_paiement(self):
        """Ouvre le formulaire de modification pour le paiement sélectionné"""
        item_id, meta = self._get_selected_row()
        if not item_id or not meta:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement à modifier.")
            return

        # Récupérer les données complètes du paiement
        paiement_id = meta["paiement_id"]
        record = SubscriptionRecord(
            payment_id=meta["paiement_id"],
            tenant_id=meta["locataire_id"],
            last_name=meta["nom"],
            first_name=meta["prenom"],
            month=meta["mois"],
            amount=meta["montant"],
            currency=meta["devise"],
            subscription_status=meta["statut_souscription"],
            status=meta["statut"],
            total_amount=meta.get("montant_total", meta["montant"]),
            paid_amount=meta.get("montant_paye", 0),
            remaining_amount=meta.get("reste_a_payer", 0),
            payment_status=meta.get("statut_paiement", "En attente"),
        )

        # Ouvrir le formulaire en mode édition (référence stockée pour éviter GC)
        self._current_dialog = FormulaireSouscription(self, self.charger_donnees, paiement_id, record.to_edit_tuple())

    def supprimer_paiement(self):
        """Supprime le paiement sélectionné après confirmation"""
        item_id, meta = self._get_selected_row()
        if not item_id or not meta:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement à supprimer.")
            return

        paiement_id = meta["paiement_id"]
        nom = meta["nom"]
        prenom = meta["prenom"]
        mois = meta["mois"]

        # Confirmation
        reponse = messagebox.askyesno(
            "Confirmation de suppression",
            f"Êtes-vous sûr de vouloir supprimer le paiement de {nom} {prenom} pour {mois} ?\n\nCette action est irréversible."
        )

        if reponse:
            self._show_loading("Suppression du paiement...")
            try:
                success, message = self.payment_service.delete(paiement_id)
                if success:
                    self.charger_donnees()
                    self._set_status(f"✅ {message}")
                else:
                    messagebox.showerror("Erreur", message)
                    self._set_status("❌ La suppression a échoué.")
            finally:
                self._hide_loading()

    def ajouter_paiement(self):
        """Ajoute un paiement complémentaire au paiement sélectionné"""
        item_id, meta = self._get_selected_row()
        if not item_id or not meta:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement.")
            return

        paiement_id = meta["paiement_id"]
        nom = meta["nom"]
        prenom = meta["prenom"]
        mois = meta["mois"]
        montant_total = meta.get("montant_total", meta["montant"])
        montant_paye = meta.get("montant_paye", meta["montant"])
        reste_a_payer = meta.get("reste_a_payer", 0)

        statut_souscription = meta.get("statut_souscription", "Simple")

        # Pour un souscripteur Spécial, le paiement peut devoir solder un mois
        # antérieur même si la ligne sélectionnée est déjà complète.
        if reste_a_payer <= 0 and statut_souscription != "Spécial":
            messagebox.showinfo("Information", f"Le paiement de {nom} {prenom} pour {mois} est déjà complet.\n\nMontant total : {montant_total}\nMontant payé : {montant_paye}")
            return

        # Demander le montant à ajouter
        from tkinter import simpledialog
        montant_additionnel = simpledialog.askfloat(
            "Ajouter un paiement",
            f"Montant à ajouter pour {nom} {prenom}\n\n"
            f"Montant total : {montant_total}\n"
            f"Déjà payé : {montant_paye}\n"
            f"Reste à payer sur cette ligne : {reste_a_payer}\n"
            f"Pour une souscription Spéciale, le montant sera affecté au plus ancien mois impayé.\n\n"
            f"Entrez le montant à ajouter :",
            minvalue=0.01,
        )

        if montant_additionnel is not None:
            self._show_loading("Ajout du paiement...")
            try:
                success, message = self.payment_service.add_payment(paiement_id, montant_additionnel)
                if success:
                    self.charger_donnees()
                    self._set_status(f"✅ {message}")
                    self._ouvrir_signature_apres_paiement(paiement_id, montant_additionnel)
                else:
                    messagebox.showerror("Erreur", message)
                    self._set_status("❌ L'ajout du paiement a échoué.")
            finally:
                self._hide_loading()

    @staticmethod
    def _montant_positif(value) -> bool:
        try:
            return float(str(value).replace(",", ".")) > 0
        except (TypeError, ValueError):
            return False

    def _ouvrir_signature_apres_paiement(self, paiement_id: int, montant_versement=None):
        meta = self._row_meta.get(str(paiement_id))
        if not meta:
            return
        if montant_versement is not None:
            meta = dict(meta)
            meta["montant_versement"] = montant_versement
        if not messagebox.askyesno(
            "Signature du reçu",
            "Le paiement est enregistré.\n\nVoulez-vous faire signer le reçu maintenant ?",
            parent=self,
        ):
            return
        self._demarrer_signature_qr(meta)

    def demander_signature_qr(self):
        """Ouvre une demande de signature locale pour le paiement sélectionné."""
        item_id, meta = self._get_selected_row()
        if not item_id or not meta:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement.")
            return

        if not self._montant_positif(meta.get("montant_paye", 0)):
            messagebox.showwarning(
                "Signature non disponible",
                "La signature du reçu est possible seulement quand un paiement a été enregistré.",
                parent=self,
            )
            return
        if meta.get("est_signe"):
            messagebox.showinfo(
                "Reçu déjà signé",
                "Ce paiement possède déjà une signature.",
                parent=self,
            )
            return
        self._demarrer_signature_qr(meta)

    def creer_lien_portail_locataire(self):
        """Crée un lien temporaire donnant accès au portail du locataire."""
        item_id, meta = self._get_selected_row()
        if not item_id or not meta:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement.", parent=self)
            return
        try:
            token, expires_at = create_portal_token(int(meta["locataire_id"]), days=30)
            configure_mobile_environment()
            url = portal_url(token)
            self.clipboard_clear()
            self.clipboard_append(url)
            # Garder une référence pour éviter le garbage collection
            self._portal_qr_dialog = PortalQRDialog(
                self,
                url,
                expires_at.strftime("%d/%m/%Y %H:%M"),
            )
            self._set_status("✅ Portail locataire créé : QR affiché et lien copié.")
        except Exception as exc:
            messagebox.showerror("Portail locataire", f"Impossible de créer le lien : {exc}", parent=self)

    def creer_lien_paiement(self):
        """Crée un lien public temporaire pour transmettre une preuve de paiement."""
        item_id, meta = self._get_selected_row()
        if not item_id or not meta:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement.", parent=self)
            return
        try:
            token, expires_at, remaining, currency = create_payment_link(
                int(meta["paiement_id"]), days=7
            )
            configure_mobile_environment()
            url = payment_link_url(token)
            self.clipboard_clear()
            self.clipboard_append(url)
            # Garder une référence pour éviter le garbage collection
            self._payment_qr_dialog = PortalQRDialog(
                self,
                url,
                expires_at.strftime("%d/%m/%Y %H:%M"),
                title="Paiement par lien prêt",
                description=(
                    f"Le locataire peut envoyer sa preuve depuis son téléphone. "
                    f"Montant attendu : {remaining} {currency}."
                ),
            )
            self._set_status("✅ Lien de paiement créé : QR affiché et lien copié.")
        except Exception as exc:
            messagebox.showerror("Paiement par lien", f"Impossible de créer le lien : {exc}", parent=self)

    def ouvrir_preuves_paiement(self):
        """Ouvre la file des preuves envoyées par les locataires."""
        try:
            self._payment_proofs_dialog = PaymentProofsDialog(self)
            self._set_status("💳 File des preuves de paiement ouverte.")
        except Exception as exc:
            messagebox.showerror(
                "Preuves de paiement",
                f"Impossible d'ouvrir les preuves : {exc}",
                parent=self,
            )

    def _demarrer_signature_qr(self, meta: dict):
        """Démarre la signature QR pour un paiement déjà payé."""
        montant_signature = meta.get("montant_versement", meta.get("montant_paye", 0))
        meta = dict(meta)
        meta["montant_paye_signature"] = montant_signature
        try:
            session = start_signature_session(meta)
            self._set_status(
                f"Signature QR prête pour {meta['nom']} {meta['prenom']}."
            )
            # Garder une référence pour éviter le garbage collection
            self._signature_qr_dialog = SignatureQRDialog(
                self,
                session,
                on_signed=lambda: self._apres_signature_recue(meta),
            )
        except Exception as exc:
            messagebox.showerror(
                "Signature numérique",
                f"Impossible de créer la signature QR : {exc}",
                parent=self,
            )
            self._set_status("Impossible de créer la signature QR.")

    def _apres_signature_recue(self, meta: dict):
        self.charger_donnees()
        self._set_status(f"Signature enregistrée pour {meta['nom']} {meta['prenom']}.")

    def afficher_historique_locataire(self, event=None):
        """Affiche l'historique des paiements d'un locataire au double-clic"""
        if self._is_loading:
            return
        item = ""
        if event is not None and hasattr(event, "y"):
            item = self.tableau.identify_row(event.y)
        if not item:
            selection = self.tableau.selection()
            item = selection[0] if selection else ""
        if not item:
            item, meta = self._get_selected_row()
            if not item or not meta:
                return
        else:
            meta = self._row_meta.get(str(item))
            if not meta:
                return
        
        nom = meta["nom"]
        prenom = meta["prenom"]
        
        self._show_loading(f"Chargement de l'historique de {nom} {prenom}...")
        try:
            paiements = self.payment_service.history(meta["locataire_id"])
            if not paiements:
                messagebox.showinfo(
                    "Historique",
                    f"Aucun paiement trouvé pour {nom} {prenom}.",
                    parent=self,
                )
                self._set_status(f"ℹ️ Aucun historique pour {nom} {prenom}.")
                return
            # Garder une référence pour éviter le garbage collection
            self._history_dialog = HistoriqueDialog(self, nom, prenom, paiements)
            self._set_status(f"📋 Historique ouvert pour {nom} {prenom}.")

        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger l'historique : {e}")
            self._set_status("❌ Impossible d'ouvrir l'historique.")
        finally:
            self._hide_loading()

    def generer_pdf(self):
        # Récupérer les données actuellement affichées dans le tableau
        lignes = [self.tableau.item(c)["values"] for c in self.tableau.get_children()]
        description_filtres = self._describe_active_filters()
        self._set_status("📄 Préparation de l’export PDF...")
        # Garder une référence pour éviter le garbage collection
        self._export_pdf_dialog = ExportPDFDialog(self, table_data=lignes, filter_summary=description_filtres)

    def envoyer_rappels_impayes(self):
        """Envoie manuellement les rappels configurés pour les paiements en retard."""
        if self._is_loading:
            return
        if not messagebox.askyesno(
            "Confirmation",
            "Envoyer les rappels aux locataires ayant un paiement en retard ?\n\n"
            "Chaque locataire ne recevra qu'un rappel par mois et par canal.",
            parent=self,
        ):
            return

        self._show_loading("Envoi des rappels impayés...")
        try:
            result = send_overdue_payment_reminders()
            status = result.get("status")
            if status == "disabled":
                messagebox.showinfo(
                    "Rappels désactivés",
                    "Activez overdue_reminders.enabled dans config.json et configurez le canal d'envoi.",
                    parent=self,
                )
            elif status == "no_data":
                messagebox.showinfo("Rappels impayés", result.get("message", "Aucun rappel à envoyer."), parent=self)
            elif status in {"completed", "dry_run"}:
                messagebox.showinfo(
                    "Rappels impayés",
                    f"Rappels envoyés automatiquement : {result.get('sent', 0)}\n"
                    f"Messages WhatsApp ouverts : {result.get('opened', 0)}\n"
                    f"Déjà traités ou ignorés : {result.get('skipped', 0)}\n"
                    f"Erreurs : {result.get('errors', 0)}",
                    parent=self,
                )
            else:
                messagebox.showwarning(
                    "Rappels impayés",
                    result.get("message", "Certains rappels n'ont pas été envoyés."),
                    parent=self,
                )
            self._set_status(f"📣 Rappels : {status or 'inconnu'}.")
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible d'envoyer les rappels : {exc}", parent=self)
            self._set_status("❌ Envoi des rappels interrompu.")
        finally:
            self._hide_loading()

    # ── Helpers ─────────────────────────────────────────────────────────────
    @staticmethod
    def _combo(master, values, default, width):
        cb = ctk.CTkComboBox(
            master, values=values, width=width,
            fg_color=C["bg_section"], border_color=C["border"],
            text_color=C["text_hi"], dropdown_fg_color=C["bg_section"],
            dropdown_text_color=C["text_hi"],
            dropdown_hover_color=C["border"],
            button_color=C["border"], button_hover_color=C["accent_dim"])
        cb.set(default)
        return cb

    @staticmethod
    def _vline(parent):
        ctk.CTkFrame(parent, width=1, fg_color=C["border"]).pack(
            side="left", fill="y", pady=8)

    def _on_filter_type_change(self, selected_type):
        self.current_filter_type = selected_type
        self._build_filter_value_widget(selected_type)

    def _build_filter_value_widget(self, filter_type):
        for child in self.filter_value_holder.winfo_children():
            child.destroy()

        self.current_filter_type = filter_type

        if filter_type == "Nom":
            name_values = ["Tous", *self._get_nom_filter_values()]
            default_name = self.active_filters["nom"] or "Tous"
            if default_name not in name_values:
                name_values.insert(1, default_name)
            widget = self._combo(self.filter_value_holder, name_values, default_name, 260)
            widget.pack(fill="x", expand=True)
            widget.configure(command=lambda _: self._add_or_update_filter())
            self.filter_value_widget = widget
            return

        if filter_type == "Mois":
            month_values = ["Tous", *build_month_choices(start_year=2025, years_ahead=5)]
            widget = self._combo(self.filter_value_holder, month_values, "Tous", 260)
            widget.pack(fill="x", expand=True)
            widget.configure(command=lambda _: self._add_or_update_filter())
            self.filter_value_widget = widget
            return

        if filter_type == "Statut des versements":
            widget = self._combo(self.filter_value_holder, ["Tous", "En règle", "Litigieux", "En attente"], "Tous", 220)
            widget.pack(fill="x", expand=True)
            widget.configure(command=lambda _: self._add_or_update_filter())
            self.filter_value_widget = widget
            return

        if filter_type == "Statut souscription":
            widget = self._combo(self.filter_value_holder, ["Tous", "Spécial", "Simple"], "Tous", 220)
            widget.pack(fill="x", expand=True)
            widget.configure(command=lambda _: self._add_or_update_filter())
            self.filter_value_widget = widget
            return

        widget = self._combo(self.filter_value_holder, ["Toutes", "CDF", "USD", "EUR", "XAF", "CAD"], "Toutes", 220)
        widget.pack(fill="x", expand=True)
        widget.configure(command=lambda _: self._add_or_update_filter())
        self.filter_value_widget = widget

    def _on_filter_input_change(self, event=None):
        """Debounce pour la recherche en temps réel"""
        filter_type = self.combo_type_filtre.get()
        # Uniquement pour les champs texte éventuels
        if filter_type == "Nom" and isinstance(getattr(self, "filter_value_widget", None), ctk.CTkEntry):
            if self._filter_debounce_id:
                self.after_cancel(self._filter_debounce_id)
            self._filter_debounce_id = self.after(
                self._filter_debounce_delay, self._add_or_update_filter
            )

    def _add_or_update_filter(self):
        filter_type = self.combo_type_filtre.get()
        value = ""
        if hasattr(self, "filter_value_widget"):
            value = self.filter_value_widget.get().strip()

        if filter_type == "Nom":
            self.active_filters["nom"] = value if value and value != "Tous" else ""
        elif filter_type == "Mois":
            self.active_filters["mois"] = value if value and value != "Tous" else ""
        elif filter_type == "Statut des versements":
            self.active_filters["statut"] = value if value and value != "Tous" else "Tous"
        elif filter_type == "Statut souscription":
            self.active_filters["statut_souscription"] = value if value and value != "Tous" else "Tous"
        elif filter_type == "Devise":
            self.active_filters["devise"] = value if value and value != "Toutes" else "Toutes"

        self._refresh_active_filters_ui()
        self.charger_donnees()
        self._set_status(f"🔍 Filtre {filter_type.lower()} appliqué.")

    def _refresh_active_filters_ui(self):
        for child in self.active_filters_frame.winfo_children():
            child.destroy()

        chips = [
            ("Nom", self.active_filters["nom"]),
            ("Mois", self.active_filters["mois"]),
            ("Statut des versements", self.active_filters["statut"]),
            ("Statut souscription", self.active_filters["statut_souscription"]),
            ("Devise", self.active_filters["devise"]),
        ]
        visible = [(label, value) for label, value in chips if value and value not in {"Tous", "Toutes"}]

        if not visible:
            ctk.CTkLabel(
                self.active_filters_frame,
                text="Aucun filtre actif. Choisissez un type pour commencer.",
                font=ctk.CTkFont(size=10),
                text_color=C["text_lo"]
            ).pack(anchor="w")
            return

        for label, value in visible:
            if label == "Mois":
                display_value = format_month_label(value)
            else:
                display_value = value
            chip = ctk.CTkFrame(
                self.active_filters_frame,
                fg_color=C["bg_section"],
                corner_radius=16,
                border_width=1,
                border_color=C["border"]
            )
            chip.pack(side="left", padx=(0, 8), pady=2)
            ctk.CTkLabel(
                chip,
                text=f"{label}: {display_value}",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=C["text_hi"]
            ).pack(side="left", padx=(12, 6), pady=6)
            ctk.CTkButton(
                chip,
                text="✕",
                width=24,
                height=24,
                fg_color=C["border"],
                hover_color=C["red_hover"],
                text_color=C["text_hi"],
                corner_radius=12,
                command=lambda key=label.replace(" ", "_").lower(): self._remove_filter(key)
            ).pack(side="left", padx=(0, 6), pady=4)

    def _remove_filter(self, key: str):
        if key == "nom":
            self.active_filters["nom"] = ""
        elif key == "mois":
            self.active_filters["mois"] = ""
        elif key == "statut":
            self.active_filters["statut"] = "Tous"
        elif key == "statut_souscription":
            self.active_filters["statut_souscription"] = "Tous"
        elif key == "devise":
            self.active_filters["devise"] = "Toutes"
        self._refresh_active_filters_ui()
        self.charger_donnees()
        self._set_status(f"❌ Filtre {key} retiré.")

    def _describe_active_filters(self) -> str:
        labels = []
        if self.active_filters["nom"]:
            labels.append(f"Nom = {self.active_filters['nom']}")
        if self.active_filters["mois"]:
            labels.append(f"Mois = {format_month_label(self.active_filters['mois'])}")
        if self.active_filters["statut"] != "Tous":
            labels.append(f"Statut = {self.active_filters['statut']}")
        if self.active_filters["statut_souscription"] != "Tous":
            labels.append(f"Statut souscription = {self.active_filters['statut_souscription']}")
        if self.active_filters["devise"] != "Toutes":
            labels.append(f"Devise = {self.active_filters['devise']}")
        return " | ".join(labels) if labels else "Aucun filtre actif"

    def _get_nom_filter_values(self) -> list[str]:
        """Retourne les noms complets distincts disponibles pour le filtre guidé."""
        values = []
        seen = set()

        for record in getattr(self, "_all_data", []):
            nom = record.last_name.strip()
            prenom = record.first_name.strip()
            full_name = " ".join(part for part in (nom, prenom) if part).strip()
            if not full_name:
                continue
            key = full_name.casefold()
            if key in seen:
                continue
            seen.add(key)
            values.append(full_name)

        return sorted(values, key=str.casefold)

    def _set_status(self, message: str):
        self.status_var.set(message)

    # ── Gestion de la fermeture ─────────────────────────────────────────────
    def _on_close(self):
        """Fermeture propre de l'application"""
        try:
            if self._startup_maintenance_after_id is not None:
                try:
                    self.after_cancel(self._startup_maintenance_after_id)
                except Exception:
                    pass
            if self._maintenance_after_id is not None:
                try:
                    self.after_cancel(self._maintenance_after_id)
                except Exception:
                    pass
            # Nettoyer les figures matplotlib
            import matplotlib.pyplot as plt
            if hasattr(self, '_fig_bar'):
                plt.close(self._fig_bar)
            if hasattr(self, '_fig_pie'):
                plt.close(self._fig_pie)
        except Exception:
            pass
            
        self.destroy()


# ── Point d'entrée ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AppGestionLoyers()
    app.mainloop()
