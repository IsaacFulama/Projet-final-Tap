"""Centre d'administration opérationnel de TAP."""

from __future__ import annotations

from decimal import Decimal
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from tap.config.theme import C
from tap.core.admin_insights import build_admin_insights


class AdminCenterDialog(ctk.CTkToplevel):
    """Vue synthétique pour piloter les opérations quotidiennes."""

    def __init__(self, parent, records: list, username: str = "Administrateur"):
        super().__init__(parent)
        self.parent = parent
        self.title("Centre d'administration · TAP")
        self.geometry("950x780")
        self.minsize(800, 600)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        
        # Raccourcis clavier
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._refresh())
        
        self._build(records, username)

    @staticmethod
    def _amount(record, field: str) -> Decimal:
        try:
            return Decimal(str(getattr(record, field, 0) or 0).replace(",", "."))
        except Exception:
            return Decimal("0")

    def _build(self, records: list, username: str) -> None:
        records = list(records or [])
        insights = build_admin_insights(records)
        total, paid = insights["total"], insights["paid"]
        overdue, pending = insights["overdue"], insights["unsigned"]
        
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 16))
        ctk.CTkLabel(header, text="Centre d'administration", font=ctk.CTkFont(family="Georgia", size=32, weight="bold"), text_color=C["text_hi"]).pack(anchor="w")
        ctk.CTkLabel(header, text=f"Pilotage opérationnel · session {username}", font=ctk.CTkFont(size=14), text_color=C["text_lo"]).pack(anchor="w", pady=(4, 0))
        
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=32, pady=10)
        
        cards = [("LOYERS À SUIVRE", f"{total:,.2f}", C["accent"]), ("DÉJÀ ENCAISSÉ", f"{paid:,.2f}", C["green"]), ("DOSSIERS À TRAITER", str(overdue), C["orange"]), ("REÇUS À SIGNER", str(pending), C["blue"])]
        for column, (label, value, color) in enumerate(cards):
            card = ctk.CTkFrame(grid, fg_color=C["bg_card"], border_width=1, border_color=C["border"], corner_radius=12)
            card.grid(row=0, column=column, padx=(0 if column == 0 else 12, 0), sticky="nsew")
            grid.grid_columnconfigure(column, weight=1)
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=11, weight="bold"), text_color=C["text_lo"]).pack(anchor="w", padx=16, pady=(16, 4))
            value_label = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=26, weight="bold"), text_color=color)
            value_label.pack(anchor="w", padx=16, pady=(0, 16))
            self._animate_value(value_label, value, suffix="")
            
        body = ctk.CTkFrame(self, fg_color=C["bg_section"], corner_radius=12)
        body.pack(fill="both", expand=True, padx=32, pady=16)
        
        # Split body into left (actions/insights) and right (chart)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        
        left_panel = ctk.CTkFrame(body, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        
        right_panel = ctk.CTkFrame(body, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        
        ctk.CTkLabel(left_panel, text="Actions prioritaires", font=ctk.CTkFont(size=18, weight="bold"), text_color=C["text_hi"]).pack(anchor="w", pady=(0, 12))
        
        actions = ctk.CTkFrame(left_panel, fg_color="transparent")
        actions.pack(fill="x")
        
        for label, command in (("Voir les enregistrements", self._records), ("Actualiser les données", self._refresh), ("Envoyer les rappels impayés", self._reminders), ("Exporter le rapport PDF", self._pdf)):
            btn = ctk.CTkButton(actions, text=label, command=command, fg_color=C["bg_card"], hover_color=C["accent_dim"], text_color=C["text_hi"], font=ctk.CTkFont(size=13, weight="bold"), border_width=1, border_color=C["border"], height=42)
            btn.pack(fill="x", pady=6)
            
        intelligence = ctk.CTkFrame(left_panel, fg_color=C["bg_card"], corner_radius=10, border_width=1, border_color=C["border"])
        intelligence.pack(fill="x", pady=(24, 18))
        ctk.CTkLabel(intelligence, text="✦ Intelligence opérationnelle", font=ctk.CTkFont(size=15, weight="bold"), text_color=C["accent"]).pack(anchor="w", padx=16, pady=(16, 6))
        ctk.CTkLabel(intelligence, text=f"Taux d'encaissement : {insights['collection_rate']:.1f}% · Reste : {insights['remaining']:,.2f}", font=ctk.CTkFont(size=12), text_color=C["text_hi"]).pack(anchor="w", padx=16)
        
        progress = ctk.CTkProgressBar(intelligence, height=10, progress_color=C["green"])
        progress.pack(fill="x", padx=16, pady=10)
        progress.set(max(0.0, min(1.0, insights["collection_rate"] / 100)))
        
        ctk.CTkLabel(intelligence, text="\n".join(f"• {item}" for item in insights["recommendations"]), text_color=C["text_lo"], font=ctk.CTkFont(size=12), justify="left", anchor="w").pack(fill="x", padx=16, pady=(0, 16))
        
        self._build_alert_radar(left_panel, insights)
        
        # --- Right Panel: Chart ---
        ctk.CTkLabel(right_panel, text="Répartition des Encaissements", font=ctk.CTkFont(size=18, weight="bold"), text_color=C["text_hi"]).pack(anchor="w", pady=(0, 12))
        self._build_chart(right_panel, insights)

    def _build_chart(self, parent, insights: dict) -> None:
        chart_frame = ctk.CTkFrame(parent, fg_color=C["bg_card"], corner_radius=10, border_width=1, border_color=C["border"])
        chart_frame.pack(fill="both", expand=True)
        
        fig = Figure(figsize=(4, 3), dpi=100, facecolor=C["bg_card"])
        ax = fig.add_subplot(111)
        
        paid = float(insights["paid"])
        remaining = float(insights["remaining"])
        
        labels = ['Encaissé', 'À recouvrer']
        sizes = [paid, remaining]
        colors = [C["green"], C["orange"]]
        
        if paid == 0 and remaining == 0:
            sizes = [1]
            labels = ['Aucune donnée']
            colors = [C["border"]]
            
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90, textprops=dict(color=C["text_hi"], fontsize=10))
        
        for w in wedges:
            w.set_edgecolor(C["bg_card"])
            w.set_linewidth(1.5)
            
        fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _build_alert_radar(self, parent, insights: dict) -> None:
        colors = {"critique": C["red"], "surveillance": C["orange"], "sain": C["green"], "inconnu": C["text_lo"]}
        radar = ctk.CTkFrame(parent, fg_color=colors.get(insights["health"], C["border"]), corner_radius=10)
        radar.pack(fill="x", pady=(0, 18))
        title = ctk.CTkLabel(radar, text=f"◉ RADAR · PORTEFEUILLE {insights['health'].upper()}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#FFFFFF")
        title.pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(radar, text=insights["alert"], font=ctk.CTkFont(size=12), text_color="#FFFFFF", anchor="w", justify="left").pack(fill="x", padx=16, pady=(0, 12))
        if insights["health"] in {"critique", "surveillance"}:
            self._pulse_alert(title, colors[insights["health"]])

    def _pulse_alert(self, label, color: str, visible: bool = True) -> None:
        if not label.winfo_exists():
            return
        label.configure(text_color="#FFFFFF" if visible else "#FDE68A")
        label.after(650, lambda: self._pulse_alert(label, color, not visible))

    def _animate_value(self, label, value: str, suffix: str = ""):
        try:
            target = float(str(value).replace(",", ""))
        except ValueError:
            label.configure(text=value)
            return
        steps = 20
        def tick(step=0):
            if not label.winfo_exists():
                return
            progress = (step + 1) / steps
            eased = progress * progress * (3 - 2 * progress)
            current = target * eased
            label.configure(text=f"{current:,.2f}{suffix}" if abs(target) >= 100 or "." in str(value) else f"{current:.0f}{suffix}")
            if step + 1 < steps:
                label.after(20, lambda: tick(step + 1))
        tick()

    def _records(self):
        self.destroy(); self.parent._show_records_page()

    def _refresh(self):
        self.destroy(); self.parent.charger_donnees()

    def _reminders(self):
        self.destroy(); self.parent.envoyer_rappels_impayes()

    def _pdf(self):
        self.destroy(); self.parent.generer_pdf()

