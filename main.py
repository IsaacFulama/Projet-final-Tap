import customtkinter as ctk
from tkinter import ttk, messagebox, Menu, filedialog
from fpdf import FPDF
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as mticker
from collections import Counter, defaultdict
import re
import database
from formulaire import FormulaireSouscription
from export_pdf import ExportPDFDialog
from login import LoginDialog

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ── Palette ────────────────────────────────────────────────────────────────────
C = {
    "bg_deep":    "#0B0F14",
    "bg_panel":   "#111820",
    "bg_card":    "#161E28",
    "bg_section": "#1A2332",
    "border":     "#243042",
    "accent":     "#C9A84C",
    "accent_dim": "#8A7035",
    "text_hi":    "#EDF2F7",
    "text_lo":    "#6B7C93",
    "green":      "#3ECF8E",
    "orange":     "#F59E0B",
    "blue":       "#3B82F6",
    "red":        "#EF4444",
    "red_hover":  "#DC2626",
    "tbl_even":   "#161E28",
    "tbl_odd":    "#1A2332",
    "tbl_select": "#1E3A5F",
    "tbl_head":   "#0F1923",
}

MPL = {                      # palette matplotlib (fond transparent)
    "bg":     "#161E28",
    "axes":   "#1A2332",
    "grid":   "#243042",
    "text":   "#6B7C93",
    "accent": "#C9A84C",
    "green":  "#3ECF8E",
    "orange": "#F59E0B",
    "blue":   "#3B82F6",
    "red":    "#EF4444",
}

STATUS_COLORS = {
    "Payé":       MPL["green"],
    "Litigieux":  MPL["orange"],
    "En attente": MPL["blue"],
}

MONTH_ALIASES = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}


def _month_sort_key(value: str):
    text = str(value).strip().lower()

    match = re.match(r"^(\d{4})[-/](\d{1,2})$", text)
    if match:
        return int(match.group(1)), int(match.group(2)), text

    match = re.match(r"^(\d{1,2})[-/](\d{4})$", text)
    if match:
        return int(match.group(2)), int(match.group(1)), text

    parts = text.split()
    year = next((int(part) for part in parts if part.isdigit() and len(part) == 4), 9999)
    month = next((MONTH_ALIASES[part] for part in parts if part in MONTH_ALIASES), 99)
    return year, month, text


# ── Widgets réutilisables ──────────────────────────────────────────────────────

class StatCard(ctk.CTkFrame):
    def __init__(self, master, icon: str, label: str, color: str, **kwargs):
        super().__init__(master, fg_color=C["bg_card"], corner_radius=12,
                         border_width=1, border_color=C["border"], **kwargs)
        ctk.CTkFrame(self, height=3, fg_color=color, corner_radius=3).pack(fill="x")
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)
        self.lbl_value = ctk.CTkLabel(inner, text="0",
                                      font=ctk.CTkFont(family="Georgia", size=28, weight="bold"),
                                      text_color=color)
        self.lbl_value.pack(anchor="w")
        self.lbl_sub = ctk.CTkLabel(inner, text="—",
                                     font=ctk.CTkFont(size=10),
                                     text_color=C["text_lo"])
        self.lbl_sub.pack(anchor="w")
        bottom = ctk.CTkFrame(inner, fg_color="transparent")
        bottom.pack(fill="x", anchor="w", pady=(4, 0))
        ctk.CTkLabel(bottom, text=icon, font=ctk.CTkFont(size=12),
                     text_color=C["text_lo"]).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(bottom, text=label, font=ctk.CTkFont(size=11),
                     text_color=C["text_lo"]).pack(side="left")

    def update(self, value, sub: str = ""):
        self.lbl_value.configure(text=str(value))
        self.lbl_sub.configure(text=sub)


class SidebarButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        d = dict(height=42, corner_radius=8, font=ctk.CTkFont(size=13), anchor="w",
                 fg_color=C["bg_section"], hover_color=C["border"],
                 text_color=C["text_hi"], border_spacing=12)
        d.update(kwargs)
        super().__init__(master, **d)


# ── Application ────────────────────────────────────────────────────────────────

class AppGestionLoyers(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.configure(fg_color=C["bg_deep"])
        self.title("TAP · Gestion des Loyers")
        self.geometry("1340x860")
        self.state('zoomed')  # Fullscreen
        self.minsize(1100, 720)
        self._all_data: list = []   # cache des données courantes
        self._row_meta: dict[str, dict] = {}

        self._build_sidebar()
        self._build_main()
        self._apply_table_style()
        self.charger_donnees()

    # ── SIDEBAR ────────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=C["bg_panel"])
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
        ctk.CTkLabel(sb, text="v3.0  ·  TAP Loyers",
                     font=ctk.CTkFont(size=10),
                     text_color=C["text_lo"]).pack(pady=20)

    # ── ZONE PRINCIPALE ────────────────────────────────────────────────────────
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

        # ── FILTRES GLOBAUX ────────────────────────────────────────────────────
        self._build_filters(main)

        # ── ONGLETS ────────────────────────────────────────────────────────────
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

        # Recharger les graphiques quand on switche sur Analyse
        self.tabs.configure(command=self._on_tab_change)

    # ── FILTRES GLOBAUX ────────────────────────────────────────────────────────
    def _build_filters(self, parent):
        f = ctk.CTkFrame(parent, fg_color=C["bg_card"], corner_radius=10,
                          border_width=1, border_color=C["border"])
        f.pack(fill="x", pady=(0, 12))

        # Recherche
        ctk.CTkLabel(f, text="🔍", text_color=C["text_lo"],
                     font=ctk.CTkFont(size=14)).pack(side="left", padx=(16, 4), pady=12)
        self.entry_recherche = ctk.CTkEntry(
            f, placeholder_text="Rechercher par nom...", width=220,
            fg_color=C["bg_section"], border_color=C["border"],
            text_color=C["text_hi"], placeholder_text_color=C["text_lo"])
        self.entry_recherche.pack(side="left", padx=(4, 8), pady=10)
        self.entry_recherche.bind("<Return>", lambda _: self.charger_donnees())

        self._vline(f)

        # Statut
        ctk.CTkLabel(f, text="Statut", font=ctk.CTkFont(size=11),
                     text_color=C["text_lo"]).pack(side="left", padx=(12, 6))
        self.combo_statut = self._combo(f, ["Tous", "Payé", "Litigieux", "En attente"], "Tous", 150)
        self.combo_statut.pack(side="left", padx=(0, 8))

        self._vline(f)

        # Devise
        ctk.CTkLabel(f, text="Devise", font=ctk.CTkFont(size=11),
                     text_color=C["text_lo"]).pack(side="left", padx=(12, 6))
        self.combo_devise_filtre = self._combo(f, ["Toutes", "CDF", "USD", "EUR", "XAF", "CAD"], "Toutes", 120)
        self.combo_devise_filtre.pack(side="left", padx=(0, 8))

        self._vline(f)

        # Mois
        ctk.CTkLabel(f, text="Mois contient", font=ctk.CTkFont(size=11),
                     text_color=C["text_lo"]).pack(side="left", padx=(12, 6))
        self.entry_mois_filtre = ctk.CTkEntry(
            f, placeholder_text="ex: 2026-01 ou Janvier 2026", width=180,
            fg_color=C["bg_section"], border_color=C["border"],
            text_color=C["text_hi"], placeholder_text_color=C["text_lo"])
        self.entry_mois_filtre.pack(side="left", padx=(0, 8))

        # Boutons
        ctk.CTkButton(f, text="Filtrer", width=80, height=32,
                      fg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="#000000", font=ctk.CTkFont(size=12, weight="bold"),
                      corner_radius=6, command=self.charger_donnees
                      ).pack(side="left", padx=(4, 4))
        ctk.CTkButton(f, text="✕", width=32, height=32,
                      fg_color=C["bg_section"], hover_color=C["border"],
                      text_color=C["text_lo"], corner_radius=6,
                      command=self._reset_filters
                      ).pack(side="left", padx=(0, 12))

    # ── ONGLET TABLEAU ────────────────────────────────────────────────────────
    def _build_tab_table(self, parent):
        # Cartes stats
        stats_row = ctk.CTkFrame(parent, fg_color="transparent")
        stats_row.pack(fill="x", pady=(8, 12))
        stats_row.columnconfigure((0, 1, 2, 3), weight=1, uniform="c")

        self.card_total     = StatCard(stats_row, "📋", "Total",         C["blue"])
        self.card_payes     = StatCard(stats_row, "✅", "Payés",          C["green"])
        self.card_litigieux = StatCard(stats_row, "⚠️", "Litigieux",      C["orange"])
        self.card_attente   = StatCard(stats_row, "⏳", "En attente",     C["text_lo"])
        for i, c in enumerate([self.card_total, self.card_payes,
                                self.card_litigieux, self.card_attente]):
            c.grid(row=0, column=i, padx=(0, 10) if i < 3 else 0, sticky="nsew")

        # Header compteur
        tbl_hdr = ctk.CTkFrame(parent, fg_color="transparent")
        tbl_hdr.pack(fill="x", padx=4, pady=(0, 6))
        ctk.CTkLabel(tbl_hdr, text="Enregistrements",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C["text_hi"]).pack(side="left")
        self.lbl_count = ctk.CTkLabel(tbl_hdr, text="0 résultat",
                                       font=ctk.CTkFont(size=11),
                                       text_color=C["text_lo"])
        self.lbl_count.pack(side="right")

        # Treeview
        tbl_inner = ctk.CTkFrame(parent, fg_color=C["bg_section"],
                                  corner_radius=8, border_width=1,
                                  border_color=C["border"])
        tbl_inner.pack(fill="both", expand=True)

        cols = ("Nom", "Prénom", "Mois", "Montant", "Devise", "Statut")
        self.tableau = ttk.Treeview(tbl_inner, columns=cols, show="headings",
                                    style="TAP.Treeview")
        widths = {"Nom": 160, "Prénom": 140, "Mois": 120,
                  "Montant": 110, "Devise": 90, "Statut": 120}
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
        self.tableau.configure(yscrollcommand=sb_y.set)
        sb_y.pack(side="right", fill="y", padx=(2, 4), pady=4)
        self.tableau.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        # Menu contextuel
        self.context_menu = Menu(self, tearoff=0, bg=C["bg_section"],
                                  fg=C["text_hi"], activebackground=C["border"],
                                  activeforeground=C["accent"], bd=0)
        self.context_menu.add_command(label="  ✅  Marquer Payé",
                                       command=lambda: self.modifier_statut("Payé"))
        self.context_menu.add_command(label="  ⚠️  Marquer Litigieux",
                                       command=lambda: self.modifier_statut("Litigieux"))
        self.context_menu.add_command(label="  ⏳  Marquer En attente",
                                       command=lambda: self.modifier_statut("En attente"))
        self.tableau.bind("<Button-3>", self.afficher_menu_contextuel)
        self.tableau.bind("<Double-1>", self.afficher_historique_locataire)

    # ── ONGLET DASHBOARD ──────────────────────────────────────────────────────
    def _build_tab_dashboard(self, parent):
        # Filtre devise
        filter_row = ctk.CTkFrame(parent, fg_color="transparent")
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
        kpi_row = ctk.CTkFrame(parent, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(8, 12))
        kpi_row.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="k")

        self.kpi_montant_total = StatCard(kpi_row, "💰", "Montant total",   C["accent"])
        self.kpi_moyenne       = StatCard(kpi_row, "📐", "Moyenne/paiement", C["blue"])
        self.kpi_max           = StatCard(kpi_row, "📈", "Paiement max",     C["green"])
        self.kpi_mois_actif    = StatCard(kpi_row, "📅", "Mois le plus actif", C["orange"])
        self.kpi_count         = StatCard(kpi_row, "📊", "Total paiements", C["text_lo"])
        for i, k in enumerate([self.kpi_montant_total, self.kpi_moyenne,
                                self.kpi_max, self.kpi_mois_actif, self.kpi_count]):
            k.grid(row=0, column=i, padx=(0, 10) if i < 4 else 0, sticky="nsew")

        # Zone graphiques (2 colonnes)
        charts = ctk.CTkFrame(parent, fg_color="transparent")
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

    # ── STYLES TTK ─────────────────────────────────────────────────────────────
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

    # ── LOGIQUE PRINCIPALE ─────────────────────────────────────────────────────
    def ouvrir_formulaire(self):
        FormulaireSouscription(self, callback_maj_tableau=self.charger_donnees)

    def charger_donnees(self):
        nom           = self.entry_recherche.get().strip()
        statut        = self.combo_statut.get()
        devise_filtre = self.combo_devise_filtre.get()
        mois_filtre   = self.entry_mois_filtre.get().strip()

        lignes = database.get_souscriptions(nom, statut)

        # Filtres côté client (devise & mois)
        if devise_filtre != "Toutes":
            lignes = [l for l in lignes if str(l[6]).upper() == devise_filtre.upper()]
        if mois_filtre:
            lignes = [l for l in lignes if mois_filtre.lower() in str(l[4]).lower()]

        self._all_data = lignes
        self._row_meta.clear()

        # ── Remplir le tableau
        for row in self.tableau.get_children():
            self.tableau.delete(row)
        for i, ligne in enumerate(lignes):
            paiement_id = ligne[0]
            locataire_id = ligne[1]
            valeurs_visibles = ligne[2:8]
            tag = "even" if i % 2 == 0 else "odd"
            sv  = str(ligne[7]) if len(ligne) > 7 else ""
            st  = {"Payé": "paye", "Litigieux": "litige",
                   "En attente": "attente"}.get(sv, "")
            item_id = str(paiement_id)
            self.tableau.insert("", "end", iid=item_id, values=valeurs_visibles, tags=(tag, st))
            self._row_meta[item_id] = {
                "paiement_id": paiement_id,
                "locataire_id": locataire_id,
            }

        # ── Stats cartes tableau
        total     = len(lignes)
        payes     = sum(1 for l in lignes if l[7] == "Payé")
        litigieux = sum(1 for l in lignes if l[7] == "Litigieux")
        attente   = sum(1 for l in lignes if l[7] == "En attente")
        self.card_total.update(total)
        self.card_payes.update(payes)
        self.card_litigieux.update(litigieux)
        self.card_attente.update(attente)
        self.lbl_count.configure(
            text=f"{total} résultat{'s' if total != 1 else ''}")

        # ── Mettre à jour le dashboard si visible
        self._update_dashboard(lignes)

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

        total_m   = sum(montants)
        moy_m     = total_m / len(montants) if montants else 0
        max_m     = max(montants) if montants else 0
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
        sorted_items = sorted(sums.items(), key=lambda x: _month_sort_key(x[0]))[-10:]
        labels = [it[0] for it in sorted_items]
        values = [it[1] for it in sorted_items]

        bars = ax.bar(labels, values, color=MPL["accent"], width=0.6,
                      edgecolor="none", zorder=3)

        # Couleur dégradée : plus la barre est haute, plus elle est lumineuse
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

        counts = Counter(str(l[7]) for l in lignes if len(l) > 7)
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

    # ── ÉVÉNEMENTS ────────────────────────────────────────────────────────────
    def _on_tab_change(self):
        tab = self.tabs.get()
        if "Analyse" in tab:
            self._update_dashboard_with_filter()

    def _reset_filters(self):
        self.entry_recherche.delete(0, "end")
        self.combo_statut.set("Tous")
        self.combo_devise_filtre.set("Toutes")
        self.entry_mois_filtre.delete(0, "end")
        self.charger_donnees()

    def afficher_menu_contextuel(self, event):
        item = self.tableau.identify_row(event.y)
        if item:
            self.tableau.selection_set(item)
            self.selected_item = item
            self.context_menu.post(event.x_root, event.y_root)

    def modifier_statut(self, nouveau_statut: str):
        if not hasattr(self, "selected_item"):
            return
        meta = self._row_meta.get(str(self.selected_item))
        if not meta:
            return
        success, message = database.mettre_a_jour_statut(
            meta["paiement_id"], nouveau_statut)
        if success:
            messagebox.showinfo("Mise à jour", message)
            self.charger_donnees()
        else:
            messagebox.showerror("Erreur", message)

    def afficher_historique_locataire(self, event):
        """Affiche l'historique des paiements d'un locataire au double-clic"""
        item = self.tableau.identify_row(event.y)
        if not item:
            return
        
        values = self.tableau.item(item)["values"]
        nom = values[0]
        prenom = values[1]
        meta = self._row_meta.get(str(item))
        if not meta:
            return
        
        # Récupérer tous les paiements de ce locataire
        try:
            conn = database.obtenir_connexion()
            cursor = conn.cursor()
            query = '''SELECT p.mois, p.montant, p.devise, p.statut
                      FROM paiements p
                      WHERE p.locataire_id = %s
                      ORDER BY p.id DESC'''
            cursor.execute(query, (meta["locataire_id"],))
            paiements = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # Créer une fenêtre pour afficher l'historique
            self._show_historique_dialog(nom, prenom, paiements)
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger l'historique : {e}")

    def _show_historique_dialog(self, nom, prenom, paiements):
        """Affiche une boîte de dialogue avec l'historique des paiements"""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Historique - {nom} {prenom}")
        dialog.geometry("700x500")
        dialog.configure(fg_color=C["bg_deep"])
        dialog.transient(self)
        dialog.grab_set()
        
        # Frame principal
        frame = ctk.CTkFrame(dialog, fg_color=C["bg_card"], corner_radius=16,
                              border_width=1, border_color=C["border"])
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 16))
        ctk.CTkLabel(header, text="Historique des paiements",
                     font=ctk.CTkFont(family="Georgia", size=20, weight="bold"),
                     text_color=C["accent"]).pack(anchor="w")
        ctk.CTkLabel(header, text=f"{nom} {prenom}",
                     font=ctk.CTkFont(size=12),
                     text_color=C["text_lo"]).pack(anchor="w", pady=(4, 0))
        
        ctk.CTkFrame(frame, height=1, fg_color=C["border"]).pack(fill="x", padx=0)
        
        # Statistiques
        stats_frame = ctk.CTkFrame(frame, fg_color=C["bg_section"], corner_radius=8)
        stats_frame.pack(fill="x", padx=16, pady=16)
        
        total_montant = 0
        payes = 0
        for p in paiements:
            try:
                total_montant += float(str(p[1]).replace(",", "."))
            except:
                pass
            if p[3] == "Payé":
                payes += 1
        
        stats_row = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_row.pack(fill="x", padx=12, pady=8)
        
        ctk.CTkLabel(stats_row, text=f"Total paiements: {len(paiements)}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C["text_hi"]).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(stats_row, text=f"Payés: {payes}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C["green"]).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(stats_row, text=f"Montant total: {total_montant:,.0f}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C["accent"]).pack(side="left")
        
        # Tableau des paiements
        tbl_frame = ctk.CTkFrame(frame, fg_color="transparent")
        tbl_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        
        cols = ("Mois", "Montant", "Devise", "Statut")
        tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", style="TAP.Treeview")
        
        for col in cols:
            tree.heading(col, text=col.upper())
            if col == "Montant":
                tree.column(col, width=100, anchor="e")
            elif col == "Statut":
                tree.column(col, width=100, anchor="center")
            else:
                tree.column(col, width=120, anchor="center")
        
        for paiement in paiements:
            tree.insert("", "end", values=paiement)
        
        tree.pack(fill="both", expand=True)
        
        # Bouton fermer
        ctk.CTkButton(frame, text="Fermer", width=120, height=35,
                      fg_color=C["bg_section"], hover_color=C["border"],
                      text_color=C["text_hi"],
                      command=dialog.destroy).pack(pady=16)

    def generer_pdf(self):
        # Récupérer les données actuellement affichées dans le tableau
        lignes = [self.tableau.item(c)["values"] for c in self.tableau.get_children()]
        ExportPDFDialog(self, table_data=lignes)

    # ── Helpers ───────────────────────────────────────────────────────────────
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


if __name__ == "__main__":
    # Afficher le dialogue de login
    login_dialog = LoginDialog(None)
    
    # Lancer la boucle principale pour afficher le login
    login_dialog.mainloop()
    
    # Vérifier si l'authentification a réussi
    if login_dialog.authenticated:
        app = AppGestionLoyers()
        app.mainloop()
