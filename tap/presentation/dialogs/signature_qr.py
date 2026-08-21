from __future__ import annotations

import logging
import time
import webbrowser

import customtkinter as ctk
import qrcode

from tap.config.theme import C
from tap.config.responsive import clamp_window_geometry, detect_screen_profile
from tap.core.local_signature import SignatureSession, get_signature_status

logger = logging.getLogger("tap")

# Couleurs de statut. On retombe sur C["accent"] si une clé de thème
# spécifique n'existe pas, pour ne jamais planter l'affichage à cause d'un
# thème incomplet.
_STATUS_COLOR_SIGNED = C.get("green", C["accent"])
_STATUS_COLOR_WARN = C.get("orange", C["accent"])
_STATUS_COLOR_ERROR = C.get("red", C["accent"])
_STATUS_COLOR_PENDING = C["accent"]

# Après une copie de lien, on garde le message de confirmation affiché
# pendant cette durée avant de laisser le cycle de polling reprendre la
# main sur le texte du statut (auparavant le message de confirmation était
# écrasé quasi instantanément par le prochain rafraîchissement, ~1.2s
# après le clic, le rendant illisible en pratique).
_COPY_CONFIRMATION_SECONDS = 2.5

# Nombre d'échecs consécutifs de vérification du statut tolérés avant
# d'informer clairement l'utilisateur d'un problème de connexion, plutôt
# que de rester bloqué indéfiniment sur "En attente..." sans explication.
_MAX_POLL_ERRORS_BEFORE_WARNING = 3


class SignatureQRDialog(ctk.CTkToplevel):
    """Fenetre QR pour faire signer un paiement depuis un telephone local."""

    def __init__(self, parent, session: SignatureSession, on_signed=None):
        super().__init__(parent)
        self.session = session
        self.on_signed = on_signed
        self._poll_id = None
        self._completed = False
        self._poll_error_count = 0
        self._status_override_until = 0.0

        self.title("Signature numerique")
        self._set_responsive_geometry()
        self.configure(fg_color=C["bg_deep"])
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())

        self._build_ui()
        self._poll_status()

    def _set_responsive_geometry(self):
        """
        Calcule une taille de fenêtre adaptée à l'écran plutôt qu'une taille
        fixe (430x610), qui pouvait dépasser la hauteur disponible sur les
        petits écrans (netbooks, portables 13"/14" en 1366x768), et centre
        la fenêtre sur l'écran comme les autres dialogues de l'application.
        """
        try:
            screen = detect_screen_profile()
            screen_w, screen_h = screen.width, screen.height
        except Exception:
            logger.debug("Impossible de détecter le profil d'écran", exc_info=True)
            screen_w, screen_h = 1366, 768

        try:
            width, height = clamp_window_geometry(
                screen_w,
                screen_h,
                width_ratio=0.32,
                height_ratio=0.80,
                min_width=360,
                min_height=520,
            )
        except Exception:
            logger.debug("clamp_window_geometry indisponible, repli sur taille fixe", exc_info=True)
            width, height = 430, 610

        # Ne jamais dépasser l'écran disponible, avec une marge de sécurité.
        width = min(width, max(360, screen_w - 40))
        height = min(height, max(480, screen_h - 60))

        x = max((screen_w - width) // 2, 0)
        y = max((screen_h - height) // 2, 0)

        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min(360, width), min(480, height))

    def _build_ui(self):
        frame = ctk.CTkScrollableFrame(
            self,
            fg_color=C["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=C["border"],
        )
        frame.pack(fill="both", expand=True, padx=18, pady=18)

        title = ctk.CTkLabel(
            frame,
            text="Signature par QR code",
            font=ctk.CTkFont(family="Georgia", size=20, weight="bold"),
            text_color=C["accent"],
        )
        title.pack(anchor="w", padx=18, pady=(18, 8))

        p = self.session.payload
        details = (
            f"{p.get('signataire_nom', '')}\n"
            f"Mois : {p.get('mois', '')}\n"
            f"Montant : {p.get('montant_total', '')} {p.get('devise', '')}\n"
            f"Reste : {p.get('reste_a_payer', '')} {p.get('devise', '')}"
        )
        ctk.CTkLabel(
            frame,
            text=details,
            justify="left",
            font=ctk.CTkFont(size=13),
            text_color=C["text_hi"],
        ).pack(anchor="w", padx=18, pady=(0, 14))

        self._build_qr_section(frame)

        hint = (
            "Le telephone doit etre connecte au meme Wi-Fi que ce PC.\n"
            "Windows peut demander une autorisation pare-feu sur reseau prive."
        )
        ctk.CTkLabel(
            frame,
            text=hint,
            justify="center",
            font=ctk.CTkFont(size=12),
            text_color=C["text_lo"],
        ).pack(padx=18, pady=(0, 12))

        self.url_box = ctk.CTkTextbox(
            frame,
            height=54,
            fg_color=C["bg_section"],
            text_color=C["text_hi"],
            border_color=C["border"],
            border_width=1,
            wrap="word",
        )
        self.url_box.pack(fill="x", padx=18, pady=(0, 10))
        self.url_box.insert("1.0", self.session.url)
        self.url_box.configure(state="disabled")

        ctk.CTkButton(
            frame,
            text="Copier le lien",
            height=34,
            fg_color=C["bg_section"],
            hover_color=C["border"],
            text_color=C["text_hi"],
            corner_radius=6,
            command=self._copy_url,
        ).pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkButton(
            frame,
            text="Ouvrir le lien sur ce PC",
            height=34,
            fg_color=C["bg_section"],
            hover_color=C["border"],
            text_color=C["text_hi"],
            corner_radius=6,
            command=self._open_url,
        ).pack(fill="x", padx=18, pady=(0, 12))

        self.status_label = ctk.CTkLabel(
            frame,
            text="En attente de signature...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=C["accent"],
        )
        self.status_label.pack(padx=18, pady=(0, 12))

        ctk.CTkButton(
            frame,
            text="Fermer",
            height=38,
            fg_color=C["accent"],
            hover_color=C["accent_dim"],
            text_color="#000000",
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=6,
            command=self._close,
        ).pack(fill="x", padx=18, pady=(4, 18))

    def _build_qr_section(self, frame):
        """
        Génère l'image du QR code. Si `qrcode` échoue (URL trop longue pour
        le niveau de correction d'erreur par défaut, dépendance Pillow
        manquante, etc.), on n'empêche pas l'ouverture du dialogue : on
        affiche un message clair et l'utilisateur peut toujours copier le
        lien manuellement.
        """
        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=8,
                border=4,
            )
            qr.add_data(self.session.url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            qr_size = 220 if self.winfo_screenheight() < 900 else 260
            self.qr_image = ctk.CTkImage(
                light_image=qr_img,
                dark_image=qr_img,
                size=(qr_size, qr_size),
            )
            ctk.CTkLabel(frame, image=self.qr_image, text="").pack(pady=(4, 12))
        except Exception:
            logger.exception("Échec de la génération du QR code de signature")
            self.qr_image = None
            ctk.CTkLabel(
                frame,
                text="⚠️ QR code indisponible.\nUtilisez le lien ci-dessous.",
                justify="center",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=_STATUS_COLOR_WARN,
            ).pack(pady=(4, 12))

    def _copy_url(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.session.url)
        except Exception:
            logger.exception("Échec de la copie du lien de signature")
            self.status_label.configure(
                text="⚠️ Impossible de copier automatiquement. Sélectionnez le lien manuellement.",
                text_color=_STATUS_COLOR_WARN,
            )
            return

        # Le prochain cycle de `_poll_status` ne réécrira pas ce message
        # avant l'expiration du délai ci-dessous, sinon la confirmation
        # disparaissait quasi instantanément (cycle de polling ~1.2s).
        self._status_override_until = time.monotonic() + _COPY_CONFIRMATION_SECONDS
        self.status_label.configure(
            text="✅ Lien copié. Vous pouvez aussi scanner le QR.",
            text_color=_STATUS_COLOR_SIGNED,
        )

    def _open_url(self):
        try:
            if not webbrowser.open(self.session.url):
                raise RuntimeError("le navigateur n'a pas accepté le lien")
            self._status_override_until = time.monotonic() + _COPY_CONFIRMATION_SECONDS
            self.status_label.configure(
                text="✅ Lien ouvert dans le navigateur.",
                text_color=_STATUS_COLOR_SIGNED,
            )
        except Exception:
            logger.exception("Échec de l'ouverture du lien de signature")
            self.status_label.configure(
                text="⚠️ Ouverture impossible. Copiez le lien ou scannez le QR.",
                text_color=_STATUS_COLOR_WARN,
            )

    def _poll_status(self):
        """
        Vérifie périodiquement l'état de la signature.

        Contrairement à la version précédente, une erreur lors de l'appel à
        `get_signature_status` (service local temporairement indisponible,
        erreur réseau, etc.) n'arrête plus silencieusement le cycle de
        vérification : elle est comptabilisée, journalisée, et le polling
        continue avec une nouvelle tentative. L'utilisateur n'est informé
        d'un problème persistant qu'après plusieurs échecs consécutifs,
        pour ne pas afficher une fausse alerte sur un simple ralentissement
        ponctuel.
        """
        try:
            status = get_signature_status(self.session.token)
            self._poll_error_count = 0
        except Exception:
            self._poll_error_count += 1
            logger.exception(
                "Échec de la vérification du statut de signature (tentative %s)",
                self._poll_error_count,
            )
            if self._poll_error_count >= _MAX_POLL_ERRORS_BEFORE_WARNING:
                self._set_status(
                    "⚠️ Connexion au service de signature instable. Nouvelle tentative...",
                    _STATUS_COLOR_WARN,
                )
            self._poll_id = self.after(1500, self._poll_status)
            return

        code = status.get("status")
        message = status.get("message", "En attente...")

        if code == "signed":
            self._completed = True
            self._set_status("✅ Signature reçue et enregistrée.", _STATUS_COLOR_SIGNED)
            if self.on_signed:
                try:
                    self.on_signed()
                except Exception:
                    logger.exception("Erreur dans le callback on_signed")
            return

        if code in {"expired", "missing"}:
            self._set_status(f"⏳ {message}", _STATUS_COLOR_WARN)
            return

        if code == "error":
            self._set_status(f"⚠️ {message}", _STATUS_COLOR_ERROR)
            return

        self._set_status(message, _STATUS_COLOR_PENDING)
        self._poll_id = self.after(1200, self._poll_status)

    def _set_status(self, text: str, color: str):
        """
        Met à jour le libellé de statut, sauf si un message temporaire
        (ex : confirmation de copie du lien) est encore affiché.
        """
        if time.monotonic() < self._status_override_until:
            return
        try:
            self.status_label.configure(text=text, text_color=color)
        except Exception:
            logger.debug("Impossible de mettre à jour le libellé de statut", exc_info=True)

    def _close(self):
        if self._poll_id:
            try:
                self.after_cancel(self._poll_id)
            except Exception:
                logger.debug("Impossible d'annuler le polling de signature en cours", exc_info=True)
            self._poll_id = None
        # Nettoyer la référence dans le parent si elle existe
        if hasattr(self.master, '_signature_qr_dialog') and self.master._signature_qr_dialog == self:
            self.master._signature_qr_dialog = None
        self.grab_release()
        self.destroy()
