"""Centre d'administration opérationnel de TAP."""

from __future__ import annotations

from decimal import Decimal
import customtkinter as ctk

from tap.config.theme import C


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
        total = sum((self._amount(r, "total_amount") for r in records), Decimal("0"))
        paid = sum((self._amount(r, "paid_amount") for r in records), Decimal("0"))
        overdue = sum(1 for r in records if str(getattr(r, "payment_status", "")).lower() in {"litigieux", "en attente"})
        pending = sum(1 for r in records if not getattr(r, "is_signed", False))
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
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=22, weight="bold"), text_color=color).pack(anchor="w", padx=14, pady=(0, 14))
        body = ctk.CTkFrame(self, fg_color=C["bg_section"], corner_radius=12)
        body.pack(fill="both", expand=True, padx=28, pady=12)
        ctk.CTkLabel(body, text="Actions prioritaires", font=ctk.CTkFont(size=16, weight="bold"), text_color=C["text_hi"]).pack(anchor="w", padx=18, pady=(18, 10))
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", padx=18)
        for label, command in (("Voir les enregistrements", self._records), ("Actualiser les données", self._refresh), ("Envoyer les rappels impayés", self._reminders), ("Exporter le rapport PDF", self._pdf)):
            ctk.CTkButton(actions, text=label, command=command, fg_color=C["bg_card"], hover_color=C["border"], text_color=C["text_hi"], border_width=1, border_color=C["border"], height=38).pack(fill="x", pady=4)
        ctk.CTkLabel(body, text="Commencez chaque journée par les dossiers à traiter, puis vérifiez les sauvegardes et les rappels envoyés.", text_color=C["text_lo"], wraplength=760, justify="left").pack(anchor="w", padx=18, pady=(18, 10))

    def _records(self):
        self.destroy(); self.parent._show_records_page()

    def _refresh(self):
        self.destroy(); self.parent.charger_donnees()

    def _reminders(self):
        self.destroy(); self.parent.envoyer_rappels_impayes()

    def _pdf(self):
        self.destroy(); self.parent.generer_pdf()
