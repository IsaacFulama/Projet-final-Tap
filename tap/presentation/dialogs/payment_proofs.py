"""Validation des preuves de paiement envoyées par lien mobile."""

from __future__ import annotations

import os
import tempfile
from tkinter import messagebox, ttk

import customtkinter as ctk

from tap.config.theme import C
from tap.mobile.payment_links import (
    list_pending_payment_proofs,
    read_payment_proof,
    review_payment_proof,
)


class PaymentProofsDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self._closed = False
        self.title("Preuves de paiement à valider")
        self.geometry("920x520")
        self.minsize(720, 420)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

        ctk.CTkLabel(
            self,
            text="💳 Preuves de paiement à valider",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=C["accent"],
        ).pack(anchor="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(
            self,
            text="Ouvrez la preuve, vérifiez le montant, puis validez ou refusez la demande.",
            text_color=C["text_lo"],
        ).pack(anchor="w", padx=20, pady=(0, 12))

        body = ctk.CTkFrame(self, fg_color=C["bg_card"], corner_radius=12)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        columns = ("ID", "Locataire", "Mois", "Montant", "Envoyée", "Format", "Intégrité", "Note")
        self.tree = ttk.Treeview(body, columns=columns, show="headings", selectmode="browse")
        widths = {"ID": 55, "Locataire": 180, "Mois": 90, "Montant": 110, "Envoyée": 145, "Format": 100, "Intégrité": 110, "Note": 220}
        for column in columns:
            self.tree.heading(column, text=column)
            self.tree.column(column, width=widths[column], minwidth=55, anchor="center")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scrollbar.pack(side="right", fill="y", padx=(0, 8), pady=8)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(0, 18))
        ctk.CTkButton(actions, text="Ouvrir la preuve", command=self._open_proof).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="Valider", fg_color=C["green"], hover_color=C["green"], command=lambda: self._review(True)).pack(side="left", padx=8)
        ctk.CTkButton(actions, text="Refuser", fg_color=C["orange"], hover_color=C["orange"], command=lambda: self._review(False)).pack(side="left", padx=8)
        ctk.CTkButton(actions, text="Actualiser", command=self.load_data).pack(side="right")
        self.load_data()

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in list_pending_payment_proofs():
            submitted = row.get("soumis_at") or ""
            if hasattr(submitted, "strftime"):
                submitted = submitted.strftime("%d/%m/%Y %H:%M")
            self.tree.insert(
                "", "end", iid=str(row["id"]),
                values=(
                    row["id"],
                    f"{row.get('prenom', '')} {row.get('nom', '')}".strip(),
                    row.get("mois", ""),
                    f"{row.get('montant_demande', '')} {row.get('devise', '')}",
                    submitted,
                    row.get("preuve_mime", ""),
                    str(row.get("verification_status", "pending_review")),
                    row.get("note_locataire", "") or "",
                ),
            )

    def _selected_id(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def _open_proof(self):
        proof_id = self._selected_id()
        if not proof_id:
            messagebox.showwarning("Preuve", "Sélectionnez une preuve.", parent=self)
            return
        proof = read_payment_proof(proof_id)
        if not proof:
            messagebox.showerror("Preuve", "La preuve est introuvable.", parent=self)
            return
        data, mime = proof
        suffix = ".pdf" if mime == "application/pdf" else ".jpg" if mime == "image/jpeg" else ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(data)
            path = handle.name
        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror("Preuve", f"Impossible d'ouvrir la preuve : {exc}", parent=self)

    def _review(self, approve: bool):
        proof_id = self._selected_id()
        if not proof_id:
            messagebox.showwarning("Preuve", "Sélectionnez une preuve.", parent=self)
            return
        action = "valider" if approve else "refuser"
        if not messagebox.askyesno("Confirmation", f"Voulez-vous {action} cette preuve ?", parent=self):
            return
        ok, message = review_payment_proof(proof_id, approve)
        if ok:
            messagebox.showinfo("Paiement", message, parent=self)
            self.load_data()
            if hasattr(self.master, "charger_donnees"):
                self.master.charger_donnees()
        else:
            messagebox.showerror("Paiement", message, parent=self)

    def _close(self):
        if getattr(self, '_closed', False):
            return
        self._closed = True
        # Nettoyer la référence dans le parent si elle existe
        try:
            if hasattr(self.master, '_payment_proofs_dialog') and self.master._payment_proofs_dialog == self:
                self.master._payment_proofs_dialog = None
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
