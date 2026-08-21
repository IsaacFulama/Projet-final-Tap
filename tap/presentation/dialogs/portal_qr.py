"""Fenêtre de partage du portail locataire."""

from __future__ import annotations

import logging
import webbrowser

import customtkinter as ctk
import qrcode

from tap.config.theme import C

logger = logging.getLogger("tap.portal_qr")


class PortalQRDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        url: str,
        expires_text: str,
        title: str = "Portail locataire prêt",
        description: str = "Le locataire peut scanner ce QR code avec son téléphone.",
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("430x650")
        self.minsize(380, 560)
        self.transient(parent)
        self.grab_set()
        self.url = url
        self.configure(fg_color=C["bg_deep"])

        frame = ctk.CTkFrame(self, fg_color=C["bg_card"], corner_radius=12)
        frame.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(
            frame, text=title, font=ctk.CTkFont(size=21, weight="bold"),
            text_color=C["accent"],
        ).pack(pady=(22, 4))
        ctk.CTkLabel(
            frame, text=description,
            wraplength=340, justify="center", text_color=C["text_lo"],
        ).pack(pady=(0, 12))

        try:
            qr = qrcode.make(url).convert("RGB")
            self.qr_image = ctk.CTkImage(light_image=qr, dark_image=qr, size=(270, 270))
            ctk.CTkLabel(frame, image=self.qr_image, text="").pack(pady=8)
        except Exception:
            logger.exception("Échec de génération du QR du portail")
            ctk.CTkLabel(frame, text="QR indisponible : utilisez le lien ci-dessous.", text_color=C["orange"]).pack(pady=20)

        ctk.CTkLabel(frame, text=f"Expire le {expires_text}", text_color=C["text_lo"]).pack(pady=4)
        self.link = ctk.CTkTextbox(frame, height=58, wrap="word")
        self.link.pack(fill="x", padx=20, pady=10)
        self.link.insert("1.0", url)
        self.link.configure(state="disabled")
        ctk.CTkButton(frame, text="Copier le lien", command=self._copy).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(frame, text="Ouvrir sur ce PC", command=self._open).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(frame, text="Fermer", fg_color=C["accent"], text_color="#000000", command=self._close).pack(fill="x", padx=20, pady=(5, 20))

    def _close(self):
        # Nettoyer la référence dans le parent si elle existe
        if hasattr(self.master, '_portal_qr_dialog') and self.master._portal_qr_dialog == self:
            self.master._portal_qr_dialog = None
        if hasattr(self.master, '_payment_qr_dialog') and self.master._payment_qr_dialog == self:
            self.master._payment_qr_dialog = None
        self.grab_release()
        self.destroy()

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.url)

    def _open(self):
        webbrowser.open(self.url)
