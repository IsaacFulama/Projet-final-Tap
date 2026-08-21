"""Centre d'administration opérationnel de TAP."""

from __future__ import annotations

from decimal import Decimal
import customtkinter as ctk

from tap.config.theme import C
from tap.core.admin_insights import build_admin_insights


class AdminCenterDialog(ctk.CTkToplevel):
    """Vue synthétique pour piloter les opérations quotidiennes."""

    def __init__(self, parent, records: list, username: str = "Administrateur"):
        super().__init__(parent)
        self.parent = parent
        self.title("Centre d'administration · TAP")
        self.geometry("900x650")
        self.minsize(760, 520)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
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
        header.pack(fill="x", padx=28, pady=(24, 12))
        ctk.CTkLabel(header, text="Centre d'administration", font=ctk.CTkFont(family="Georgia", size=28, weight="bold"), text_color=C["text_hi"]).pack(anchor="w")
        ctk.CTkLabel(header, text=f"Pilotage opérationnel · session {username}", text_color=C["text_lo"]).pack(anchor="w", pady=(4, 0))
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=28, pady=10)
        cards = [("LOYERS À SUIVRE", f"{total:,.2f}", C["accent"]), ("DÉJÀ ENCAISSÉ", f"{paid:,.2f}", C["green"]), ("DOSSIERS À TRAITER", str(overdue), C["orange"]), ("REÇUS À SIGNER", str(pending), C["blue"])]
        for column, (label, value, color) in enumerate(cards):
            card = ctk.CTkFrame(grid, fg_color=C["bg_card"], border_width=1, border_color=C["border"], corner_radius=12)
            card.grid(row=0, column=column, padx=(0 if column == 0 else 8, 0), sticky="nsew")
            grid.grid_columnconfigure(column, weight=1)
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=10, weight="bold"), text_color=C["text_lo"]).pack(anchor="w", padx=14, pady=(14, 4))
            value_label = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=22, weight="bold"), text_color=color)
            value_label.pack(anchor="w", padx=14, pady=(0, 14))
            self._animate_value(value_label, value, suffix="")
        body = ctk.CTkFrame(self, fg_color=C["bg_section"], corner_radius=12)
        body.pack(fill="both", expand=True, padx=28, pady=12)
        ctk.CTkLabel(body, text="Actions prioritaires", font=ctk.CTkFont(size=16, weight="bold"), text_color=C["text_hi"]).pack(anchor="w", padx=18, pady=(18, 10))
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", padx=18)
        for label, command in (("Voir les enregistrements", self._records), ("Actualiser les données", self._refresh), ("Envoyer les rappels impayés", self._reminders), ("Exporter le rapport PDF", self._pdf)):
            ctk.CTkButton(actions, text=label, command=command, fg_color=C["bg_card"], hover_color=C["border"], text_color=C["text_hi"], border_width=1, border_color=C["border"], height=38).pack(fill="x", pady=4)
        ctk.CTkLabel(body, text="Commencez chaque journée par les dossiers à traiter, puis vérifiez les sauvegardes et les rappels envoyés.", text_color=C["text_lo"], wraplength=760, justify="left").pack(anchor="w", padx=18, pady=(18, 10))
        intelligence = ctk.CTkFrame(body, fg_color=C["bg_card"], corner_radius=10, border_width=1, border_color=C["border"])
        intelligence.pack(fill="x", padx=18, pady=(4, 18))
        ctk.CTkLabel(intelligence, text="✦ Intelligence opérationnelle", font=ctk.CTkFont(size=14, weight="bold"), text_color=C["accent"]).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(intelligence, text=f"Taux d'encaissement : {insights['collection_rate']:.1f}% · Reste à encaisser : {insights['remaining']:,.2f}", text_color=C["text_hi"]).pack(anchor="w", padx=14)
        progress = ctk.CTkProgressBar(intelligence, height=8, progress_color=C["green"])
        progress.pack(fill="x", padx=14, pady=8)
        progress.set(max(0.0, min(1.0, insights["collection_rate"] / 100)))
        ctk.CTkLabel(intelligence, text="\n".join(f"• {item}" for item in insights["recommendations"]), text_color=C["text_lo"], justify="left", anchor="w").pack(fill="x", padx=14, pady=(0, 12))
        self._build_alert_radar(body, insights)

    def _build_alert_radar(self, parent, insights: dict) -> None:
        colors = {"critique": C["red"], "surveillance": C["orange"], "sain": C["green"], "inconnu": C["text_lo"]}
        radar = ctk.CTkFrame(parent, fg_color=colors.get(insights["health"], C["border"]), corner_radius=10)
        radar.pack(fill="x", padx=18, pady=(0, 18))
        title = ctk.CTkLabel(radar, text=f"◉ RADAR · PORTEFEUILLE {insights['health'].upper()}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#FFFFFF")
        title.pack(anchor="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(radar, text=insights["alert"], text_color="#FFFFFF", anchor="w", justify="left").pack(fill="x", padx=14, pady=(0, 10))
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
        steps = 16
        def tick(step=0):
            if not label.winfo_exists():
                return
            current = target * min(1, (step + 1) / steps)
            label.configure(text=f"{current:,.2f}{suffix}" if abs(target) >= 100 or "." in str(value) else f"{current:.0f}{suffix}")
            if step + 1 < steps:
                label.after(24, lambda: tick(step + 1))
        tick()

    def _records(self):
        self.destroy(); self.parent._show_records_page()

    def _refresh(self):
        self.destroy(); self.parent.charger_donnees()

    def _reminders(self):
        self.destroy(); self.parent.envoyer_rappels_impayes()

    def _pdf(self):
        self.destroy(); self.parent.generer_pdf()
