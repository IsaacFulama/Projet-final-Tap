import customtkinter as ctk
from tkinter import ttk, messagebox, Menu, StringVar, filedialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as mticker
from collections import Counter, defaultdict
import time
import csv

from tap.config.theme import C, MPL, STATUS_COLORS
from tap.core.utils import month_sort_key
from tap.infrastructure.database import (
    ajouter_paiement_complementaire,
    get_historique_locataire,
    get_souscriptions,
    mettre_a_jour_statut,
    modifier_souscription,
    supprimer_souscription,
)
from tap.presentation.components.widgets import SidebarButton, StatCard
from tap.presentation.dialogs.export_pdf import ExportPDFDialog
from tap.presentation.dialogs.formulaire import FormulaireSouscription

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# ── Cache pour les calculs du dashboard ─────────────────────────────────────

class DashboardCache:
    """Cache avec TTL pour les calculs coûteux du dashboard"""
    def __init__(self, ttl=5):
        self.cache = {}
        self.ttl = ttl
        self.hits = 0
        self.misses = 0
        
    def get(self, key, compute_func):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                self.hits += 1
                return value
                
        self.misses += 1
        value = compute_func()
        self.cache[key] = (value, time.time())
        return value
    
    def invalidate(self):
        """Invalide tout le cache"""
        self.cache.clear()
    
    def get_stats(self):
        """Retourne les statistiques du cache"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return f"Cache: {self.hits} hits, {self.misses} misses ({hit_rate:.1f}% hit rate)"


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
    def __init__(self, parent, nom, prenom, paiements):
        super().__init__(parent)
        self.title(f"Historique - {nom} {prenom}")
        
        # Géométrie responsive
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        
        # Dimensions adaptatives
        if screen_w < 1024:
            width = screen_w - 40
            height = screen_h - 60
        else:
            width = min(max(600, int(screen_w * 0.45)), 800)
            height = min(max(450, int(screen_h * 0.6)), 650)
        
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(500, 350)  # Réduit pour petits écrans
        self.configure(fg_color=C["bg_deep"])
        self.transient(parent)
        self.grab_set()
        
        # Raccourcis clavier
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-w>", lambda e: self.destroy())
        
        self.nom = nom
        self.prenom = prenom
        self.paiements = paiements
        self._sort_column = None
        self._sort_reverse = False
        
        self._build_ui()
        
    def _build_ui(self):
        """Construit l'interface du dialogue"""
        # Frame principal
        frame = ctk.CTkFrame(self, fg_color=C["bg_card"], corner_radius=16,
                              border_width=1, border_color=C["border"])
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 16))
        
        ctk.CTkLabel(header, text="📊 Historique des paiements",
                     font=ctk.CTkFont(family="Georgia", size=20, weight="bold"),
                     text_color=C["accent"]).pack(anchor="w")
        
        ctk.CTkLabel(header, text=f"{self.nom} {self.prenom}",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C["text_hi"]).pack(anchor="w", pady=(8, 0))
        
        ctk.CTkFrame(frame, height=1, fg_color=C["border"]).pack(fill="x", padx=0)
        
        # Actions
        actions_frame = ctk.CTkFrame(frame, fg_color="transparent")
        actions_frame.pack(fill="x", padx=24, pady=(12, 0))
        
        ctk.CTkButton(actions_frame, text="📄 Exporter CSV",
                      fg_color=C["bg_section"], hover_color=C["border"],
                      text_color=C["text_hi"], height=32, width=140,
                      corner_radius=6,
                      command=self._export_csv).pack(side="left", padx=(0, 8))
        
        ctk.CTkButton(actions_frame, text="📊 Graphique",
                      fg_color=C["bg_section"], hover_color=C["border"],
                      text_color=C["text_hi"], height=32, width=120,
                      corner_radius=6,
                      command=self._show_evolution_chart).pack(side="left", padx=(0, 8))
        
        # Stats
        self.stats_frame = ctk.CTkFrame(frame, fg_color=C["bg_section"], corner_radius=8)
        self.stats_frame.pack(fill="x", padx=24, pady=12)
        self._update_stats()
        
        # Tableau
        self.tbl_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.tbl_frame.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        self._build_table()
        
        # Bouton fermer
        ctk.CTkButton(frame, text="Fermer", width=120, height=35,
                      fg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="#000000",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      corner_radius=6,
                      command=self.destroy).pack(pady=(0, 20))
        
    def _update_stats(self):
        """Met à jour les statistiques"""
        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        stats_row = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        stats_row.pack(fill="x", padx=16, pady=12)

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
                if len(p) >= 9:
                    total_montant += float(str(p[5]).replace(",", "."))
                    total_paye += float(str(p[6]).replace(",", "."))
                    total_reste += float(str(p[7]).replace(",", "."))
                else:
                    total_montant += float(str(p[1]).replace(",", "."))
            except (ValueError, IndexError):
                pass
            if len(p) > 4:
                if p[4] == "En règle":
                    payes += 1
                elif p[4] == "Litigieux":
                    litigieux += 1
                elif p[4] == "En attente":
                    attente += 1
            if len(p) > 8:
                if p[8] == "Complet":
                    complets += 1
                elif p[8] == "Partiel":
                    partiels += 1

        self._stat_label(stats_row, f"Total: {len(self.paiements)}", C["text_hi"])
        self._stat_label(stats_row, f"En règle: {payes}", C["green"])
        self._stat_label(stats_row, f"Litigieux: {litigieux}", C["orange"])
        self._stat_label(stats_row, f"Complet: {complets}", C["green"])
        self._stat_label(stats_row, f"Partiel: {partiels}", C["orange"])
        self._stat_label(stats_row, f"Total payé: {total_paye:,.0f}", C["accent"])
        self._stat_label(stats_row, f"Reste: {total_reste:,.0f}", C["red"])
        
    @staticmethod
    def _stat_label(parent, text, color):
        """Crée un label de statistique"""
        ctk.CTkLabel(parent, text=text,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=color).pack(side="left", padx=(0, 24))
        
    def _build_table(self):
        """Construit le tableau des paiements"""
        cols = ("Mois", "Montant Total", "Montant Payé", "Reste", "Devise", "Statut Souscription", "Statut", "Statut Paiement")
        self.tree = ttk.Treeview(self.tbl_frame, columns=cols,
                                 show="headings", style="TAP.Treeview")

        widths = {"Mois": 100, "Montant Total": 100, "Montant Payé": 100, "Reste": 90,
                  "Devise": 70, "Statut Souscription": 130, "Statut": 100, "Statut Paiement": 100}

        for col in cols:
            self.tree.heading(
                col, text=col.upper(),
                command=lambda c=col: self._sort_by_column(c)
            )
            self.tree.column(col, width=widths.get(col, 100),
                           anchor="e" if "Montant" in col or col == "Reste" else "center",
                           minwidth=60)

        # Remplir
        for i, paiement in enumerate(self.paiements):
            tag = "even" if i % 2 == 0 else "odd"
            st = str(paiement[4]) if len(paiement) > 4 else ""
            status_tag = {"En règle": "paye", "Litigieux": "litige",
                         "En attente": "attente"}.get(st, "")

            # Statut paiement tag
            statut_paiement = str(paiement[8]) if len(paiement) > 8 else "Complet"
            paiement_tag = {"Complet": "complet", "Partiel": "partiel", "En attente": "attente_paiement"}.get(statut_paiement, "")

            # N'afficher que les colonnes nécessaires
            if len(paiement) >= 9:
                values = (paiement[0], paiement[5], paiement[6], paiement[7], paiement[2], paiement[3], paiement[4], paiement[8])
            else:
                # Fallback pour les anciennes données
                values = (paiement[0], paiement[1], paiement[1], 0, paiement[2], paiement[3], paiement[4], "Complet")

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
        if column == "Montant":
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
                writer = csv.writer(f)
                writer.writerow(["Mois", "Montant Total", "Montant Payé", "Reste à Payer", "Devise",
                               "Statut Souscription", "Statut", "Statut Paiement"])
                # Adapter les données pour l'export
                for p in self.paiements:
                    if len(p) >= 9:
                        row = [p[0], p[5], p[6], p[7], p[2], p[3], p[4], p[8]]
                    else:
                        row = [p[0], p[1], p[1], 0, p[2], p[3], p[4], "Complet"]
                    writer.writerow(row)

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
        if screen_w < 1024:
            chart_width = screen_w - 60
            chart_height = screen_h - 80
        else:
            chart_width = min(700, screen_w - 100)
            chart_height = min(450, screen_h - 100)
        
        chart_dialog.geometry(f"{chart_width}x{chart_height}")
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
                mois_list.append(str(p[0]))
                montants.append(float(str(p[1]).replace(",", ".")))
            except (ValueError, IndexError):
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
        self.configure(fg_color=C["bg_deep"])
        self.title("TAP · Gestion des Loyers")
        self._set_initial_geometry()
        self.minsize(700, 500)  # Réduit pour supporter les petits écrans
        
        # Cache des données
        self._all_data: list = []
        self._row_meta: dict[str, dict] = {}
        
        # Cache pour les calculs du dashboard
        self.dash_cache = DashboardCache(ttl=5)
        
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
        
        # État de chargement
        self._is_loading = False
        self._loading_after_id = None

        self._build_sidebar()
        self._build_main()
        self._apply_table_style()
        self._setup_keyboard_shortcuts()
        
        self.bind("<Configure>", self._on_window_resize)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.after(250, self._apply_responsive_layout)
        self.charger_donnees()

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

        brand = ctk.CTkFrame(sb, fg_color="transparent")
        brand.pack(fill="x", padx=24, pady=(32, 0))
        ctk.CTkLabel(brand, text="TAP",
                     font=ctk.CTkFont(family="Georgia", size=42, weight="bold"),
                     text_color=C["accent"]).pack(anchor="w")
        ctk.CTkLabel(brand, text="GESTION LOYERS",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=C["text_lo"]).pack(anchor="w")

        ctk.CTkFrame(sb, height=1, fg_color=C["border"]).pack(fill="x", padx=24, pady=24)

        nav = ctk.CTkFrame(sb, fg_color="transparent")
        nav.pack(fill="x", padx=16)

        SidebarButton(nav, text="  ➕  Nouveau Paiement",
                      fg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="#000000", font=ctk.CTkFont(size=13, weight="bold"),
                      command=self.ouvrir_formulaire).pack(fill="x", pady=(0, 8))
        SidebarButton(nav, text="  🔄  Actualiser",
                      command=self.charger_donnees).pack(fill="x", pady=(0, 8))
        SidebarButton(nav, text="  📄  Exporter PDF",
                      fg_color="#2A1A1A", hover_color="#3D1F1F",
                      text_color=C["red"],
                      command=self.generer_pdf).pack(fill="x", pady=(0, 8))

        ctk.CTkFrame(sb, fg_color="transparent").pack(fill="both", expand=True)
        ctk.CTkLabel(sb, text="v3.3  ·  TAP Loyers",
                     font=ctk.CTkFont(size=10),
                     text_color=C["text_lo"]).pack(pady=20)

    # ── ZONE PRINCIPALE ──────────────────────────────────────────────────────
    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="right", fill="both", expand=True, padx=24, pady=24)

        # Header
        hdr = ctk.CTkFrame(main, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(hdr, text="Tableau de bord",
                     font=ctk.CTkFont(family="Georgia", size=24, weight="bold"),
                     text_color=C["text_hi"]).pack(side="left")
        ctk.CTkLabel(hdr, text="Souscriptions & Paiements",
                     font=ctk.CTkFont(size=13), text_color=C["text_lo"]
                     ).pack(side="left", padx=(12, 0), pady=(6, 0))

        self.status_bar = ctk.CTkLabel(
            main,
            textvariable=self.status_var,
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=C["text_lo"],
        )
        self.status_bar.pack(fill="x", pady=(0, 12))

        # ── FILTRES GLOBAUX ──────────────────────────────────────────────────
        self._build_filters(main)

        # ── ONGLETS ──────────────────────────────────────────────────────────
        self.tabs = ctk.CTkTabview(
            main, fg_color=C["bg_card"],
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

        tab_table = self.tabs.add("  📋  Tableau  ")
        tab_dash  = self.tabs.add("  📊  Analyse  ")

        self._build_tab_table(tab_table)
        self._build_tab_dashboard(tab_dash)

        self.tabs.configure(command=self._on_tab_change)

    # ── FILTRES GLOBAUX ──────────────────────────────────────────────────────
    def _build_filters(self, parent):
        f = ctk.CTkFrame(parent, fg_color=C["bg_card"], corner_radius=10,
                          border_width=1, border_color=C["border"])
        f.pack(fill="x", pady=(0, 12))

        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(header, text="Filtres combinables",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C["text_hi"]).pack(side="left")
        ctk.CTkLabel(header, text="Choisissez un type, ajoutez-le, puis cumulez d'autres critères.",
                     font=ctk.CTkFont(size=10),
                     text_color=C["text_lo"]).pack(side="left", padx=(12, 0))

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(6, 10))

        ctk.CTkLabel(row, text="Type", font=ctk.CTkFont(size=11),
                     text_color=C["text_lo"]).pack(side="left", padx=(0, 6))
        self.combo_type_filtre = self._combo(row, ["Nom", "Mois", "Statut", "Statut souscription", "Devise"], "Nom", 170)
        self.combo_type_filtre.configure(command=self._on_filter_type_change)
        self.combo_type_filtre.pack(side="left", padx=(0, 10))

        self.filter_value_holder = ctk.CTkFrame(row, fg_color="transparent")
        self.filter_value_holder.pack(side="left", fill="x", expand=True)
        self._build_filter_value_widget("Nom")

        ctk.CTkButton(row, text="Ajouter", width=96, height=32,
                      fg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="#000000", font=ctk.CTkFont(size=12, weight="bold"),
                      corner_radius=6, command=self._add_or_update_filter
                      ).pack(side="left", padx=(10, 8))
        ctk.CTkButton(row, text="Appliquer", width=92, height=32,
                      fg_color=C["bg_section"], hover_color=C["border"],
                      text_color=C["text_hi"], font=ctk.CTkFont(size=12, weight="bold"),
                      corner_radius=6, command=self.charger_donnees
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Tout", width=70, height=32,
                      fg_color=C["bg_section"], hover_color=C["border"],
                      text_color=C["text_lo"], corner_radius=6,
                      command=self._reset_filters
                      ).pack(side="left")

        chips_header = ctk.CTkFrame(f, fg_color="transparent")
        chips_header.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(chips_header, text="Filtres actifs",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C["text_lo"]).pack(side="left")

        self.active_filters_frame = ctk.CTkFrame(f, fg_color="transparent")
        self.active_filters_frame.pack(fill="x", padx=16, pady=(0, 12))
        self._refresh_active_filters_ui()

    # ── ONGLET TABLEAU ───────────────────────────────────────────────────────
    def _build_tab_table(self, parent):
        self.tab_table_body = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.tab_table_body.pack(fill="both", expand=True)

        # Cartes stats
        self.table_stats_row = ctk.CTkFrame(self.tab_table_body, fg_color="transparent")
        self.table_stats_row.pack(fill="x", pady=(8, 12))
        self.table_stats_row.columnconfigure((0, 1, 2, 3), weight=1, uniform="c")

        self.card_total     = StatCard(self.table_stats_row, "📋", "Total",         C["blue"])
        self.card_payes     = StatCard(self.table_stats_row, "✅", "En règle",          C["green"])
        self.card_litigieux = StatCard(self.table_stats_row, "⚠️", "Litigieux",      C["orange"])
        self.card_attente   = StatCard(self.table_stats_row, "⏳", "En attente",     C["text_lo"])
        self.table_cards = [self.card_total, self.card_payes, self.card_litigieux, self.card_attente]
        self._layout_table_cards(4)

        # Header compteur
        tbl_hdr = ctk.CTkFrame(self.tab_table_body, fg_color="transparent")
        tbl_hdr.pack(fill="x", padx=4, pady=(0, 6))
        ctk.CTkLabel(tbl_hdr, text="Enregistrements",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C["text_hi"]).pack(side="left")
        self.lbl_count = ctk.CTkLabel(tbl_hdr, text="0 résultat",
                                       font=ctk.CTkFont(size=11),
                                       text_color=C["text_lo"])
        self.lbl_count.pack(side="right")

        self.lbl_table_hint = ctk.CTkLabel(
            self.tab_table_body,
            text="Astuce : double-clic pour l'historique, clic droit pour changer le statut.",
            font=ctk.CTkFont(size=10),
            text_color=C["text_lo"],
        )
        self.lbl_table_hint.pack(anchor="w", padx=4, pady=(0, 6))

        # Treeview
        tbl_inner = ctk.CTkFrame(parent, fg_color=C["bg_section"],
                                  corner_radius=8, border_width=1,
                                  border_color=C["border"])
        tbl_inner.pack(fill="both", expand=True)

        cols = ("Nom", "Prénom", "Mois", "Montant", "Devise", "Statut Souscription", "Statut")
        self.tableau = ttk.Treeview(tbl_inner, columns=cols, show="headings",
                                    style="TAP.Treeview")
        widths = {"Nom": 160, "Prénom": 140, "Mois": 120,
                  "Montant": 110, "Devise": 90, "Statut Souscription": 160, "Statut": 120}
        anchors = {"Nom": "w", "Prénom": "w", "Montant": "e"}
        for col in cols:
            self.tableau.heading(col, text=col.upper())
            self.tableau.column(col, width=widths.get(col, 100),
                                anchor=anchors.get(col, "center"),
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
        self.context_menu.add_command(label="  💰  Ajouter paiement",
                                       command=self.ajouter_paiement)
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
        s = ttk.Style()
        s.theme_use("default")
        s.configure("TAP.Treeview", background=C["bg_section"], foreground=C["text_hi"],
                    rowheight=34, fieldbackground=C["bg_section"],
                    borderwidth=0, font=("Consolas", 11))
        s.configure("TAP.Treeview.Heading", background=C["tbl_head"],
                    foreground=C["text_lo"], relief="flat",
                    font=("Consolas", 10, "bold"), padding=(8, 10))
        s.map("TAP.Treeview",
              background=[("selected", C["tbl_select"])],
              foreground=[("selected", C["text_hi"])])
        s.map("TAP.Treeview.Heading",
              background=[("active", C["bg_section"])])
        self.tableau.tag_configure("even",   background=C["tbl_even"])
        self.tableau.tag_configure("odd",    background=C["tbl_odd"])
        self.tableau.tag_configure("paye",   foreground=C["green"])
        self.tableau.tag_configure("litige", foreground=C["orange"])
        self.tableau.tag_configure("attente",foreground=C["blue"])

    def _set_initial_geometry(self):
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Dimensions adaptatives pour tous types d'écrans
        if screen_width < 1024:
            # Écran très petit
            width = screen_width - 20
            height = screen_height - 40
        elif screen_width < 1366:
            # Écran petit
            width = min(int(screen_width * 0.95), 900)
            height = min(int(screen_height * 0.85), 650)
        else:
            # Écran standard ou large
            width = min(max(int(screen_width * 0.92), 960), screen_width)
            height = min(max(int(screen_height * 0.9), 680), screen_height)
        
        # S'assurer que les dimensions sont raisonnables
        width = max(width, 800)
        height = max(height, 600)
        
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

        self._resize_lock = True
        try:
            table_columns = 4 if width >= 1450 else 2
            kpi_columns = 5 if width >= 1550 else 3 if width >= 1180 else 2
            chart_mode = "side" if width >= 1500 else "stacked"

            self._layout_table_cards(table_columns)
            self._layout_kpi_cards(kpi_columns)
            self._layout_dashboard_charts(chart_mode)
        finally:
            self._resize_lock = False

    def _layout_table_cards(self, columns: int):
        if self._current_table_card_columns == columns:
            return

        for card in self.table_cards:
            card.grid_forget()

        for index in range(columns):
            self.table_stats_row.columnconfigure(index, weight=1, uniform="c")
        for index in range(columns, 4):
            self.table_stats_row.columnconfigure(index, weight=0, minsize=0)

        self.table_stats_row.rowconfigure(0, weight=1)
        self.table_stats_row.rowconfigure(1, weight=1 if columns < 4 else 0)

        if columns >= 4:
            positions = [(0, index, 1) for index in range(4)]
        else:
            positions = [(index // 2, index % 2, 1) for index in range(4)]

        for card, (row, column, columnspan) in zip(self.table_cards, positions):
            card.grid(row=row, column=column, columnspan=columnspan, sticky="nsew",
                      padx=(0, 10) if columnspan == 1 and column < columns - 1 else 0,
                      pady=(0, 10) if columns < 4 else 0)

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

    # ── LOGIQUE PRINCIPALE ───────────────────────────────────────────────────
    def ouvrir_formulaire(self):
        FormulaireSouscription(self, callback_maj_tableau=self.charger_donnees)

    def charger_donnees(self):
        if self._is_loading:
            return
            
        self._show_loading("Chargement des données...")
        self.update_idletasks()
        
        try:
            lignes = get_souscriptions(
                self.active_filters["nom"],
                self.active_filters["statut"],
                self.active_filters["devise"],
                self.active_filters["mois"],
                self.active_filters["statut_souscription"],
            )

            self._all_data = lignes
            self._row_meta.clear()
            self.dash_cache.invalidate()

            # ── Remplir le tableau par lots
            items = self.tableau.get_children()
            if items:
                self.tableau.delete(*items)
                
            batch_size = 100
            for i in range(0, len(lignes), batch_size):
                batch = lignes[i:i+batch_size]
                for j, ligne in enumerate(batch):
                    idx = i + j
                    paiement_id = ligne[0]
                    locataire_id = ligne[1]
                    valeurs_visibles = ligne[2:9]
                    tag = "even" if idx % 2 == 0 else "odd"
                    sv  = str(ligne[8]) if len(ligne) > 8 else ""
                    st  = {"En règle": "paye", "Litigieux": "litige",
                           "En attente": "attente"}.get(sv, "")
                    item_id = str(paiement_id)
                    self.tableau.insert("", "end", iid=item_id, values=valeurs_visibles, tags=(tag, st))
                    self._row_meta[item_id] = {
                        "paiement_id": paiement_id,
                        "locataire_id": locataire_id,
                        "nom": ligne[2],
                        "prenom": ligne[3],
                        "mois": ligne[4],
                        "montant": ligne[5],
                        "devise": ligne[6],
                        "statut_souscription": ligne[7],
                        "statut": ligne[8],
                        "montant_total": ligne[9] if len(ligne) > 9 else ligne[5],
                        "montant_paye": ligne[10] if len(ligne) > 10 else ligne[5],
                        "reste_a_payer": ligne[11] if len(ligne) > 11 else 0,
                        "statut_paiement": ligne[12] if len(ligne) > 12 else "Complet",
                    }
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
            payes     = sum(1 for l in lignes if len(l) > 8 and l[8] == "En règle")
            litigieux = sum(1 for l in lignes if len(l) > 8 and l[8] == "Litigieux")
            attente   = sum(1 for l in lignes if len(l) > 8 and l[8] == "En attente")
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
            lignes = [l for l in lignes if str(l[6]).upper() == devise_filtre.upper()]
        
        self._update_dashboard(lignes)
    
    def _reset_dashboard_filter(self):
        """Réinitialise le filtre de devise"""
        self.combo_devise_dashboard.set("Toutes")
        self._update_dashboard(self._all_data)

    def _update_dashboard(self, lignes: list):
        """Recalcule les KPIs et redessine les graphiques."""
        montants = []
        for l in lignes:
            try:
                montants.append(float(str(l[5]).replace(",", ".")))
            except (ValueError, IndexError):
                pass

        devises = sorted({str(l[6]).upper() for l in lignes if len(l) > 6 and str(l[6]).strip()})
        devise_unique = devises[0] if len(devises) == 1 else ""
        devises_multiples = len(devises) > 1

        # Calculs avec cache
        total_m   = self.dash_cache.get("total_m", lambda: sum(montants))
        moy_m     = self.dash_cache.get("moy_m", lambda: total_m / len(montants) if montants else 0)
        max_m     = self.dash_cache.get("max_m", lambda: max(montants) if montants else 0)
        count     = len(lignes)

        # Mois le plus actif
        ctr_mois  = Counter(str(l[4]) for l in lignes)
        top_mois  = ctr_mois.most_common(1)[0] if ctr_mois else ("—", 0)

        if devises_multiples:
            self.kpi_montant_total.update("—", f"{len(devises)} devises")
            self.kpi_moyenne.update("—", "Filtrer une devise")
            self.kpi_max.update("—", "Filtrer une devise")
        else:
            self.kpi_montant_total.update(f"{total_m:,.0f}", devise_unique)
            self.kpi_moyenne.update(f"{moy_m:,.0f}", devise_unique)
            self.kpi_max.update(f"{max_m:,.0f}", devise_unique)
        self.kpi_mois_actif.update(top_mois[0], f"{top_mois[1]} paiement(s)")
        self.kpi_count.update(count, "paiements")

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
        for l in lignes:
            try:
                sums[str(l[4])] += float(str(l[5]).replace(",", "."))
            except (ValueError, IndexError):
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

        counts = Counter(str(l[8]) for l in lignes if len(l) > 8)
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

    def modifier_statut(self, nouveau_statut: str):
        if not hasattr(self, "selected_item"):
            return
        meta = self._row_meta.get(str(self.selected_item))
        if not meta:
            return

        self._show_loading("Mise à jour du statut...")
        try:
            success, message = mettre_a_jour_statut(
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
                    current_tags = list(self.tableau.item(self.selected_item, "tags"))
                    current_tags.append("flash")
                    self.tableau.item(self.selected_item, tags=tuple(current_tags))
                    self.after(500, lambda: self._reset_item_flash(self.selected_item))

                self.charger_donnees()
                self._set_status(f"✅ {message}")
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
        if not hasattr(self, "selected_item"):
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement à modifier.")
            return

        meta = self._row_meta.get(str(self.selected_item))
        if not meta:
            messagebox.showerror("Erreur", "Impossible de trouver les données du paiement.")
            return

        # Récupérer les données complètes du paiement
        paiement_id = meta["paiement_id"]
        donnees = (
            paiement_id,
            meta["locataire_id"],
            meta["nom"],
            meta["prenom"],
            meta["mois"],
            meta["montant"],
            meta["devise"],
            meta["statut_souscription"],
            meta["statut"],
            meta.get("montant_total", meta["montant"]),
            meta.get("montant_paye", meta["montant"]),
            meta.get("reste_a_payer", 0),
            meta.get("statut_paiement", "Complet"),
        )

        # Ouvrir le formulaire en mode édition
        FormulaireSouscription(self, self.charger_donnees, paiement_id, donnees)

    def supprimer_paiement(self):
        """Supprime le paiement sélectionné après confirmation"""
        if not hasattr(self, "selected_item"):
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement à supprimer.")
            return

        meta = self._row_meta.get(str(self.selected_item))
        if not meta:
            messagebox.showerror("Erreur", "Impossible de trouver les données du paiement.")
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
                success, message = supprimer_souscription(paiement_id)
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
        if not hasattr(self, "selected_item"):
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement.")
            return

        meta = self._row_meta.get(str(self.selected_item))
        if not meta:
            messagebox.showerror("Erreur", "Impossible de trouver les données du paiement.")
            return

        paiement_id = meta["paiement_id"]
        nom = meta["nom"]
        prenom = meta["prenom"]
        mois = meta["mois"]
        montant_total = meta.get("montant_total", meta["montant"])
        montant_paye = meta.get("montant_paye", meta["montant"])
        reste_a_payer = meta.get("reste_a_payer", 0)

        # Si le paiement est déjà complet, informer l'utilisateur
        if reste_a_payer <= 0:
            messagebox.showinfo("Information", f"Le paiement de {nom} {prenom} pour {mois} est déjà complet.\n\nMontant total : {montant_total}\nMontant payé : {montant_paye}")
            return

        # Demander le montant à ajouter
        from tkinter import simpledialog
        montant_additionnel = simpledialog.askfloat(
            "Ajouter un paiement",
            f"Montant à ajouter pour {nom} {prenom}\n\n"
            f"Montant total : {montant_total}\n"
            f"Déjà payé : {montant_paye}\n"
            f"Reste à payer : {reste_a_payer}\n\n"
            f"Entrez le montant à ajouter :",
            minvalue=0.01,
            maxvalue=float(reste_a_payer)
        )

        if montant_additionnel is not None:
            self._show_loading("Ajout du paiement...")
            try:
                success, message = ajouter_paiement_complementaire(paiement_id, montant_additionnel)
                if success:
                    self.charger_donnees()
                    self._set_status(f"✅ {message}")
                else:
                    messagebox.showerror("Erreur", message)
                    self._set_status("❌ L'ajout du paiement a échoué.")
            finally:
                self._hide_loading()

    def afficher_historique_locataire(self, event=None):
        """Affiche l'historique des paiements d'un locataire au double-clic"""
        item = ""
        if event is not None and hasattr(event, "y"):
            item = self.tableau.identify_row(event.y)
        if not item:
            selection = self.tableau.selection()
            item = selection[0] if selection else ""
        if not item:
            return
        
        values = self.tableau.item(item)["values"]
        nom = values[0]
        prenom = values[1]
        meta = self._row_meta.get(str(item))
        if not meta:
            return
        
        self._show_loading(f"Chargement de l'historique de {nom} {prenom}...")
        try:
            paiements = get_historique_locataire(meta["locataire_id"])
            HistoriqueDialog(self, nom, prenom, paiements)
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
        self._set_status("📄 Préparation de l'export PDF...")
        ExportPDFDialog(self, table_data=lignes, filter_summary=description_filtres)

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
            widget = ctk.CTkEntry(
                self.filter_value_holder, placeholder_text="Ex: Dupont",
                fg_color=C["bg_section"], border_color=C["border"],
                text_color=C["text_hi"], placeholder_text_color=C["text_lo"])
            widget.pack(fill="x", expand=True)
            widget.bind("<Return>", lambda _: self._add_or_update_filter())
            widget.bind("<KeyRelease>", self._on_filter_input_change)
            self.filter_value_widget = widget
            return

        if filter_type == "Mois":
            widget = ctk.CTkEntry(
                self.filter_value_holder, placeholder_text="Ex: 2026-01 ou 01/2026",
                fg_color=C["bg_section"], border_color=C["border"],
                text_color=C["text_hi"], placeholder_text_color=C["text_lo"])
            widget.pack(fill="x", expand=True)
            widget.bind("<Return>", lambda _: self._add_or_update_filter())
            widget.bind("<KeyRelease>", self._on_filter_input_change)
            self.filter_value_widget = widget
            return

        if filter_type == "Statut":
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
        # Uniquement pour les champs texte (Nom, Mois)
        if filter_type in ("Nom", "Mois"):
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
            self.active_filters["nom"] = value
        elif filter_type == "Mois":
            self.active_filters["mois"] = value
        elif filter_type == "Statut":
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
            ("Statut", self.active_filters["statut"]),
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
                text=f"{label}: {value}",
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
            labels.append(f"Nom contient '{self.active_filters['nom']}'")
        if self.active_filters["mois"]:
            labels.append(f"Mois = {self.active_filters['mois']}")
        if self.active_filters["statut"] != "Tous":
            labels.append(f"Statut = {self.active_filters['statut']}")
        if self.active_filters["statut_souscription"] != "Tous":
            labels.append(f"Statut souscription = {self.active_filters['statut_souscription']}")
        if self.active_filters["devise"] != "Toutes":
            labels.append(f"Devise = {self.active_filters['devise']}")
        return " | ".join(labels) if labels else "Aucun filtre actif"

    def _set_status(self, message: str):
        self.status_var.set(message)

    # ── Gestion de la fermeture ─────────────────────────────────────────────
    def _on_close(self):
        """Fermeture propre de l'application"""
        try:
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