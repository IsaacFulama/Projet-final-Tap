import csv
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Dict, Iterable, List, Sequence, Tuple

import customtkinter as ctk
from fpdf import FPDF

from tap.config.theme import C
from tap.config.responsive import clamp_window_geometry, detect_screen_profile

def _safe_text(value) -> str:
    return str(value).encode("latin-1", "replace").decode("latin-1")


def _safe_filename_fragment(value: str) -> str:
    fragment = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    return fragment.strip("_") or "rapport"


def _parse_amount(value) -> float:
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def _normalize_rows(rows: Iterable[Sequence]) -> List[Tuple]:
    normalized: List[Tuple] = []
    for row in rows:
        values = tuple(row)
        if len(values) >= 7:
            normalized.append((values[0], values[1], values[2], values[3], values[4], values[5], values[6]))
        elif len(values) == 6:
            normalized.append((values[0], values[1], values[2], values[3], values[4], "Simple", values[5]))
        else:
            continue
    return normalized


def _alphabetical_name_key(value) -> str:
    """Retourne une clé de tri insensible à la casse et aux accents."""
    text = str(value or "").strip().casefold()
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def _build_summary(rows: List[Tuple]) -> Dict[str, object]:
    montants_souscrits = 0.0
    montants_verses = 0.0
    souscripteurs_en_regle = 0
    souscripteurs_litigieux = 0
    devises = Counter()

    for _, _, mois, montant, devise, statut_souscription, statut in rows:
        montant_float = _parse_amount(montant)
        devise = str(devise).strip().upper() or "N/A"
        statut = str(statut).strip()

        montants_souscrits += montant_float
        devises[devise] += 1

        if statut == "En règle":
            montants_verses += montant_float
            souscripteurs_en_regle += 1
        elif statut == "Litigieux":
            souscripteurs_litigieux += 1

    return {
        "montants_souscrits": montants_souscrits,
        "montants_verses": montants_verses,
        "souscripteurs_en_regle": souscripteurs_en_regle,
        "souscripteurs_litigieux": souscripteurs_litigieux,
        "montant_restant": max(montants_souscrits - montants_verses, 0.0),
        "devises": devises,
    }


def _build_breakdown(rows: List[Tuple]) -> Dict[str, Dict[str, float]]:
    breakdown: Dict[str, Dict[str, float]] = {}

    for _, _, _, montant, devise, statut_souscription, statut in rows:
        devise = str(devise).strip().upper() or "N/A"
        montant_float = _parse_amount(montant)
        statut = str(statut).strip()

        if devise not in breakdown:
            breakdown[devise] = {
                "montants_souscrits": 0.0,
                "montants_verses": 0.0,
                "en_regle": 0.0,
                "litigieux": 0.0,
            }

        breakdown[devise]["montants_souscrits"] += montant_float
        if statut == "En règle":
            breakdown[devise]["montants_verses"] += montant_float
            breakdown[devise]["en_regle"] += 1
        elif statut == "Litigieux":
            breakdown[devise]["litigieux"] += 1

    for devise, data in breakdown.items():
        data["restant"] = max(data["montants_souscrits"] - data["montants_verses"], 0.0)

    return breakdown


def _format_amount(value: float, currency_suffix: str = "") -> str:
    if currency_suffix:
        return f"{value:,.0f} {currency_suffix}".strip()
    return f"{value:,.0f}"


class PDFReportService:
    # ── Palette ───────────────────────────────────────────────────────────────
    _ACCENT      = (180, 145, 50)    # Gold accent
    _ACCENT_DARK = (120, 95, 30)     # Darker gold for header bar
    _TEXT_DARK   = (30, 30, 35)      # Near-black body text
    _TEXT_MID    = (80, 85, 95)      # Secondary text / labels
    _TEXT_LIGHT  = (255, 255, 255)   # White text on dark bg
    _BG_PAGE     = (255, 255, 255)   # White page background
    _BG_HEADER   = (240, 240, 240)   # Light header bar to save ink
    _BG_SECTION  = (245, 246, 248)   # Light grey section bg
    _BG_ROW_EVEN = (255, 255, 255)   # White row
    _BG_ROW_ODD  = (245, 247, 250)   # Very light blue-grey row
    _TBL_HEAD_BG = (235, 235, 235)   # Table header background (light)
    _TBL_BORDER  = (210, 215, 222)   # Subtle table border
    _GREEN       = (30, 160, 100)    # En règle
    _ORANGE      = (210, 130, 20)    # Litigieux
    _BLUE        = (50, 110, 200)    # En attente
    _RED_SOFT    = (200, 60, 60)     # Restant / alert

    @classmethod
    def _draw_page_bg(cls, pdf: FPDF) -> None:
        """White page background + subtle gold accent line at top."""
        pdf.set_fill_color(*cls._BG_PAGE)
        pdf.rect(0, 0, 210, 297, "F")
        # Top accent bar
        pdf.set_fill_color(*cls._BG_HEADER)
        pdf.rect(0, 0, 210, 28, "F")
        # Gold accent stripe
        pdf.set_fill_color(*cls._ACCENT)
        pdf.rect(0, 28, 210, 1.2, "F")

    @classmethod
    def _draw_table_headers(cls, pdf: FPDF, widths, headers) -> None:
        pdf.set_font("Arial", "B", 8.5)
        pdf.set_fill_color(*cls._TBL_HEAD_BG)
        pdf.set_text_color(*cls._TEXT_DARK)
        pdf.set_draw_color(*cls._TBL_BORDER)
        for width, header in zip(widths, headers):
            pdf.cell(width, 9, _safe_text(header), border=1, fill=True, align="C")
        pdf.ln()

    @classmethod
    def _status_color(cls, statut: str):
        s = str(statut).strip()
        if s == "En règle":
            return cls._GREEN
        if s == "Litigieux":
            return cls._ORANGE
        if s == "En attente":
            return cls._BLUE
        return cls._TEXT_DARK

    @classmethod
    def generate_pdf_report(
        cls,
        rows: Iterable[Sequence],
        filepath: str,
        filter_summary: str = "",
        title: str = "TAP - Rapport des Souscriptions",
    ) -> bool:
        normalized_rows = _normalize_rows(rows)
        normalized_rows.sort(
            key=lambda row: (
                _alphabetical_name_key(row[0]),
                _alphabetical_name_key(row[1]),
            )
        )
        summary = _build_summary(normalized_rows)
        breakdown = _build_breakdown(normalized_rows)

        try:
            pdf = FPDF(orientation="P", unit="mm", format="A4")
            pdf.set_auto_page_break(auto=True, margin=18)
            pdf.alias_nb_pages()
            pdf.add_page()

            # ── Page background + header bar ──────────────────────────────
            cls._draw_page_bg(pdf)

            # Title inside header bar
            pdf.set_y(6)
            pdf.set_text_color(*cls._TEXT_DARK)
            pdf.set_font("Arial", "B", 17)
            pdf.cell(0, 9, _safe_text(title), ln=True, align="C")
            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(*cls._TEXT_MID)
            pdf.cell(0, 5, _safe_text(datetime.now().strftime("Genere le %d/%m/%Y a %H:%M")), ln=True, align="C")

            pdf.set_y(33)

            # Filter summary
            if filter_summary:
                pdf.set_font("Arial", "I", 9)
                pdf.set_text_color(*cls._TEXT_MID)
                pdf.multi_cell(0, 5, _safe_text(f"Filtres actifs : {filter_summary}"), align="C")
                pdf.ln(2)

            # ── RÉSUMÉ ────────────────────────────────────────────────────
            pdf.set_font("Arial", "B", 12)
            pdf.set_text_color(*cls._ACCENT_DARK)
            pdf.cell(0, 8, _safe_text("Resume"), ln=True)
            pdf.set_draw_color(*cls._ACCENT)
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 45, pdf.get_y())
            pdf.ln(3)

            devise_label = ""
            if len(summary["devises"]) == 1:
                devise_label = next(iter(summary["devises"].keys()))
            elif len(summary["devises"]) > 1:
                devise_label = "MULTI-DEVISES"

            devise_suffix = "" if not devise_label or devise_label == "MULTI-DEVISES" else devise_label

            if devise_label == "MULTI-DEVISES":
                pdf.set_font("Arial", "I", 8)
                pdf.set_text_color(*cls._TEXT_MID)
                pdf.multi_cell(
                    0, 4,
                    _safe_text("Plusieurs devises presentes. Les montants sont additionnes tels que saisis."),
                )
                pdf.ln(2)

            def summary_row(label: str, value: str, highlight: tuple | None = None) -> None:
                y = pdf.get_y()
                pdf.set_fill_color(*cls._BG_SECTION)
                pdf.set_draw_color(*cls._TBL_BORDER)
                pdf.set_font("Arial", "", 10)
                pdf.set_text_color(*cls._TEXT_DARK)
                pdf.cell(120, 8, _safe_text(f"   {label}"), border="TB", fill=True)
                if highlight:
                    pdf.set_text_color(*highlight)
                pdf.set_font("Arial", "B", 10)
                pdf.cell(0, 8, _safe_text(value), border="TB", ln=True, fill=True, align="R")

            summary_row("Total des montants souscrits",
                        _format_amount(summary["montants_souscrits"], devise_suffix))
            summary_row("Total des montants verses",
                        _format_amount(summary["montants_verses"], devise_suffix),
                        cls._GREEN)
            summary_row("Souscripteurs en regle",
                        str(summary["souscripteurs_en_regle"]),
                        cls._GREEN)
            summary_row("Souscripteurs litigieux",
                        str(summary["souscripteurs_litigieux"]),
                        cls._ORANGE)
            summary_row("Montant restant a recouvrer",
                        _format_amount(summary["montant_restant"], devise_suffix),
                        cls._RED_SOFT)

            pdf.ln(6)

            # ── SYNTHÈSE PAR DEVISE ───────────────────────────────────────
            if len(breakdown) > 1:
                pdf.set_font("Arial", "B", 12)
                pdf.set_text_color(*cls._ACCENT_DARK)
                pdf.cell(0, 8, _safe_text("Synthese par devise"), ln=True)
                pdf.set_draw_color(*cls._ACCENT)
                pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 65, pdf.get_y())
                pdf.ln(3)

                bd_widths = [24, 34, 34, 32, 32, 34]
                bd_headers = ["Devise", "Souscrits", "Verses", "En regle", "Litigieux", "Restant"]
                cls._draw_table_headers(pdf, bd_widths, bd_headers)

                pdf.set_font("Arial", "", 9)
                for index, (devise, data) in enumerate(sorted(breakdown.items())):
                    bg = cls._BG_ROW_EVEN if index % 2 == 0 else cls._BG_ROW_ODD
                    pdf.set_fill_color(*bg)
                    pdf.set_draw_color(*cls._TBL_BORDER)
                    pdf.set_text_color(*cls._TEXT_DARK)
                    row_values = [
                        devise,
                        _format_amount(data["montants_souscrits"]),
                        _format_amount(data["montants_verses"]),
                        str(int(data["en_regle"])),
                        str(int(data["litigieux"])),
                        _format_amount(data["restant"]),
                    ]
                    for width, value in zip(bd_widths, row_values):
                        pdf.cell(width, 8, _safe_text(value), border="TB", fill=True, align="C")
                    pdf.ln()
                pdf.ln(6)

            # ── DÉTAIL DES PAIEMENTS ──────────────────────────────────────
            pdf.set_font("Arial", "B", 12)
            pdf.set_text_color(*cls._ACCENT_DARK)
            pdf.cell(0, 8, _safe_text("Detail des paiements"), ln=True)
            pdf.set_draw_color(*cls._ACCENT)
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 65, pdf.get_y())
            pdf.ln(3)

            widths = [28, 26, 28, 24, 18, 30, 26]
            headers = ["Nom", "Prenom", "Mois", "Montant", "Dev", "Souscription", "Statut"]
            cls._draw_table_headers(pdf, widths, headers)

            pdf.set_font("Arial", "", 8.5)
            for index, row in enumerate(normalized_rows):
                if pdf.get_y() > 262:
                    pdf.add_page()
                    cls._draw_page_bg(pdf)
                    pdf.set_y(33)
                    # Re-draw section title + headers
                    pdf.set_font("Arial", "B", 10)
                    pdf.set_text_color(*cls._ACCENT_DARK)
                    pdf.cell(0, 7, _safe_text("Detail des paiements (suite)"), ln=True)
                    pdf.ln(2)
                    cls._draw_table_headers(pdf, widths, headers)
                    pdf.set_font("Arial", "", 8.5)

                bg = cls._BG_ROW_EVEN if index % 2 == 0 else cls._BG_ROW_ODD
                pdf.set_fill_color(*bg)
                pdf.set_draw_color(*cls._TBL_BORDER)

                values = [
                    row[0], row[1], row[2],
                    _format_amount(_parse_amount(row[3])),
                    row[4], row[5], row[6],
                ]
                for col_idx, (width, value) in enumerate(zip(widths, values)):
                    # Colorize the Statut column
                    if col_idx == 6:
                        pdf.set_text_color(*cls._status_color(value))
                        pdf.set_font("Arial", "B", 8.5)
                    else:
                        pdf.set_text_color(*cls._TEXT_DARK)
                        pdf.set_font("Arial", "", 8.5)
                    pdf.cell(width, 8, _safe_text(value), border="TB", fill=True, align="C")
                pdf.ln()

            # ── Footer line ───────────────────────────────────────────────
            pdf.ln(4)
            pdf.set_draw_color(*cls._TBL_BORDER)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)
            pdf.set_font("Arial", "I", 7.5)
            pdf.set_text_color(*cls._TEXT_MID)
            pdf.cell(0, 5, _safe_text(f"TAP Gestion des Loyers - {len(normalized_rows)} enregistrement(s)"), align="C")

            pdf.output(filepath)
            return True
        except Exception as exc:
            print(f"Erreur PDF : {exc}")
            return False


def export_current_view_to_pdf(
    parent,
    rows: Iterable[Sequence],
    filter_summary: str = "",
    suggested_filename: str | None = None,
) -> bool:
    normalized_rows = _normalize_rows(rows)
    if not normalized_rows:
        messagebox.showwarning("Export vide", "Aucune ligne à exporter.", parent=parent)
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    default_name = suggested_filename or f"rapport_souscriptions_{timestamp}.pdf"

    filepath = filedialog.asksaveasfilename(
        parent=parent,
        title="Enregistrer le rapport PDF",
        defaultextension=".pdf",
        initialfile=default_name,
        filetypes=[("Fichiers PDF", "*.pdf")],
    )

    if not filepath:
        return False

    if PDFReportService.generate_pdf_report(normalized_rows, filepath, filter_summary):
        messagebox.showinfo("Succès", f"Le rapport a été exporté vers :\n{Path(filepath).name}", parent=parent)
        return True

    messagebox.showerror("Erreur", "Impossible de générer le PDF.", parent=parent)
    return False


def export_current_view_to_csv(
    parent,
    rows: Iterable[Sequence],
    filter_summary: str = "",
    suggested_filename: str | None = None,
) -> bool:
    normalized_rows = _normalize_rows(rows)
    if not normalized_rows:
        messagebox.showwarning("Export vide", "Aucune ligne à exporter.", parent=parent)
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    default_name = suggested_filename or f"rapport_souscriptions_{timestamp}.csv"

    filepath = filedialog.asksaveasfilename(
        parent=parent,
        title="Enregistrer le fichier CSV",
        defaultextension=".csv",
        initialfile=default_name,
        filetypes=[("Fichiers CSV", "*.csv")],
    )

    if not filepath:
        return False

    try:
        with open(filepath, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(["Nom", "Prénom", "Mois", "Montant", "Devise", "Statut Souscription", "Statut"])
            writer.writerows(normalized_rows)
            writer.writerow([])
            writer.writerow(["Filtres actifs", filter_summary or "Aucun filtre actif"])

        messagebox.showinfo("Succès", f"Le CSV a été exporté vers :\n{Path(filepath).name}", parent=parent)
        return True
    except Exception as exc:
        messagebox.showerror("Erreur", f"Impossible de générer le CSV : {exc}", parent=parent)
        return False


class ExportPDFDialog(ctk.CTkToplevel):
    def __init__(self, parent, table_data=None, filter_summary: str = ""):
        super().__init__(parent)
        self._screen = detect_screen_profile()
        self._compact_mode = self._screen.width < 1100
        self.table_data = list(table_data or [])
        self.filter_summary = filter_summary
        self.title("TAP · Export")
        self._set_initial_geometry()
        self.minsize(
            max(340, min(460, self._screen.width - 20)),
            max(240, min(320, self._screen.height - 20)),
        )
        self.resizable(True, True)
        self.configure(fg_color=C["bg_deep"])
        self.transient(parent)
        self.grab_set()

        card = ctk.CTkFrame(self, fg_color=C["bg_card"], corner_radius=16,
                            border_width=1, border_color=C["border"])
        card.pack(fill="both", expand=True, padx=16 if self._compact_mode else 20,
                  pady=16 if self._compact_mode else 20)

        ctk.CTkLabel(card, text="Exporter les données affichées",
                     font=ctk.CTkFont(size=17 if self._compact_mode else 18, weight="bold"),
                     text_color=C["accent"]).pack(pady=(24, 8))

        ctk.CTkLabel(card,
                     text=f"{len(self.table_data)} ligne(s) disponibles. Choisis le format d’export.",
                     font=ctk.CTkFont(size=11),
                     text_color=C["text_lo"]).pack(pady=(0, 18))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        if self._compact_mode:
            btn_row.pack(fill="x", pady=(0, 18))
        else:
            btn_row.pack(pady=(0, 18))

        if self._compact_mode:
            btn_row.columnconfigure((0, 1), weight=1, uniform="export")

        pdf_btn = ctk.CTkButton(
            btn_row,
            text="Exporter PDF",
            width=140 if not self._compact_mode else 120,
            height=38,
            fg_color=C["accent"],
            hover_color=C["accent_dim"],
            text_color="#000000",
            command=self.exporter_pdf,
        )

        csv_btn = ctk.CTkButton(
            btn_row,
            text="Exporter CSV",
            width=140 if not self._compact_mode else 120,
            height=38,
            fg_color=C["bg_section"],
            hover_color=C["border"],
            text_color=C["text_hi"],
            command=self.exporter_csv,
        )

        if self._compact_mode:
            pdf_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 8))
            csv_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=(0, 8))
        else:
            pdf_btn.pack(side="left", padx=(0, 10))
            csv_btn.pack(side="left")

        close_btn = ctk.CTkButton(
            card,
            text="Fermer",
            width=120,
            height=36,
            fg_color="transparent",
            border_width=1,
            border_color=C["border"],
            text_color=C["text_lo"],
            hover_color=C["bg_section"],
            command=self.destroy,
        )
        if self._compact_mode:
            close_btn.pack(fill="x", pady=(0, 20))
        else:
            close_btn.pack(pady=(0, 20))

    def _set_initial_geometry(self):
        screen_width = self._screen.width
        screen_height = self._screen.height

        if min(screen_width, screen_height) < 900:
            width_ratio, height_ratio = 0.92, 0.50
            min_width, min_height = 340, 240
        elif screen_width < 1366:
            width_ratio, height_ratio = 0.44, 0.36
            min_width, min_height = 400, 240
        else:
            width_ratio, height_ratio = 0.34, 0.32
            min_width, min_height = 420, 240

        width, height = clamp_window_geometry(
            screen_width,
            screen_height,
            width_ratio=width_ratio,
            height_ratio=height_ratio,
            min_width=min_width,
            min_height=min_height,
        )
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def exporter_pdf(self):
        if export_current_view_to_pdf(self, self.table_data, self.filter_summary):
            self.destroy()

    def exporter_csv(self):
        if export_current_view_to_csv(self, self.table_data, self.filter_summary):
            self.destroy()
