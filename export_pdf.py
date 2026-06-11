import csv
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Dict, Iterable, List, Sequence, Tuple

import customtkinter as ctk
from fpdf import FPDF


C = {
    "bg_deep": "#0B0F14",
    "bg_card": "#161E28",
    "bg_section": "#1A2332",
    "border": "#243042",
    "accent": "#C9A84C",
    "accent_dim": "#8A7035",
    "text_hi": "#EDF2F7",
    "text_lo": "#6B7C93",
    "green": "#3ECF8E",
    "orange": "#F59E0B",
    "blue": "#3B82F6",
    "red": "#EF4444",
}


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
        if len(values) < 6:
            continue
        normalized.append((values[0], values[1], values[2], values[3], values[4], values[5]))
    return normalized


def _build_summary(rows: List[Tuple]) -> Dict[str, object]:
    montants_souscrits = 0.0
    montants_verses = 0.0
    souscripteurs_en_regle = 0
    souscripteurs_litigieux = 0
    devises = Counter()

    for _, _, mois, montant, devise, statut in rows:
        montant_float = _parse_amount(montant)
        devise = str(devise).strip().upper() or "N/A"
        statut = str(statut).strip()

        montants_souscrits += montant_float
        devises[devise] += 1

        if statut == "Payé":
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

    for _, _, _, montant, devise, statut in rows:
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
        if statut == "Payé":
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
    @classmethod
    def generate_pdf_report(
        cls,
        rows: Iterable[Sequence],
        filepath: str,
        filter_summary: str = "",
        title: str = "TAP - Rapport des Souscriptions",
    ) -> bool:
        normalized_rows = _normalize_rows(rows)
        summary = _build_summary(normalized_rows)
        breakdown = _build_breakdown(normalized_rows)

        try:
            pdf = FPDF(orientation="P", unit="mm", format="A4")
            pdf.set_auto_page_break(auto=True, margin=16)
            pdf.alias_nb_pages()
            pdf.add_page()

            pdf.set_fill_color(11, 15, 20)
            pdf.rect(0, 0, 210, 297, "F")

            pdf.set_text_color(201, 168, 76)
            pdf.set_font("Arial", "B", 18)
            pdf.cell(0, 12, _safe_text(title), ln=True, align="C")

            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(107, 124, 147)
            pdf.cell(0, 6, _safe_text("Synthèse de l'export filtré"), ln=True, align="C")
            pdf.cell(0, 6, _safe_text(datetime.now().strftime("Généré le %d/%m/%Y à %H:%M")), ln=True, align="C")
            if filter_summary:
                pdf.multi_cell(0, 6, _safe_text(f"Filtres actifs : {filter_summary}"), align="C")
            pdf.ln(4)

            pdf.set_text_color(237, 242, 247)
            pdf.set_fill_color(22, 30, 40)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, _safe_text("Résumé"), ln=True)
            pdf.set_font("Arial", "", 10)

            devise_label = ""
            if len(summary["devises"]) == 1:
                devise_label = next(iter(summary["devises"].keys()))
            elif len(summary["devises"]) > 1:
                devise_label = "MULTI-DEVISES"

            devise_suffix = "" if not devise_label or devise_label == "MULTI-DEVISES" else devise_label
            if devise_label == "MULTI-DEVISES":
                pdf.set_font("Arial", "", 9)
                pdf.set_text_color(107, 124, 147)
                pdf.multi_cell(
                    0,
                    5,
                    _safe_text("Plusieurs devises sont présentes dans ce filtre. Les montants restent additionnés selon les valeurs saisies."),
                )
                pdf.ln(1)

            def summary_row(label: str, value: str) -> None:
                pdf.set_font("Arial", "", 10)
                pdf.set_text_color(237, 242, 247)
                pdf.set_fill_color(26, 35, 50)
                pdf.cell(118, 8, _safe_text(label), border=1, fill=True)
                pdf.cell(0, 8, _safe_text(value), border=1, ln=True, fill=True)

            summary_row("Total des montants souscrits", _format_amount(summary["montants_souscrits"], devise_suffix))
            summary_row("Total des montants versés", _format_amount(summary["montants_verses"], devise_suffix))
            summary_row("Souscripteurs en règle", str(summary["souscripteurs_en_regle"]))
            summary_row("Souscripteurs litigieux", str(summary["souscripteurs_litigieux"]))
            summary_row("Montant restant à recouvrer", _format_amount(summary["montant_restant"], devise_suffix))

            pdf.ln(5)

            if len(breakdown) > 1:
                pdf.set_text_color(237, 242, 247)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 8, _safe_text("Synthèse par devise"), ln=True)
                pdf.set_font("Arial", "B", 9)
                pdf.set_fill_color(26, 35, 50)
                pdf.set_text_color(255, 255, 255)
                widths = [24, 34, 34, 32, 32, 34]
                headers = ["Devise", "Souscrits", "Versés", "En règle", "Litigieux", "Restant"]
                for width, header in zip(widths, headers):
                    pdf.cell(width, 8, _safe_text(header), border=1, fill=True, align="C")
                pdf.ln()

                pdf.set_font("Arial", "", 9)
                pdf.set_text_color(237, 242, 247)
                for index, (devise, data) in enumerate(sorted(breakdown.items())):
                    r, g, b = (22, 30, 40) if index % 2 == 0 else (30, 40, 60)
                    pdf.set_fill_color(r, g, b)
                    row = [
                        devise,
                        _format_amount(data["montants_souscrits"]),
                        _format_amount(data["montants_verses"]),
                        str(int(data["en_regle"])),
                        str(int(data["litigieux"])),
                        _format_amount(data["restant"]),
                    ]
                    for width, value in zip(widths, row):
                        pdf.cell(width, 8, _safe_text(value), border=0, fill=True, align="C")
                    pdf.ln()
                pdf.ln(4)

            pdf.set_text_color(237, 242, 247)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, _safe_text("Détail des paiements"), ln=True)

            widths = [34, 32, 36, 28, 20, 28]
            headers = ["Nom", "Prénom", "Mois", "Montant", "Dev", "Statut"]
            pdf.set_font("Arial", "B", 9)
            pdf.set_fill_color(40, 40, 60)
            pdf.set_text_color(255, 255, 255)
            for width, header in zip(widths, headers):
                pdf.cell(width, 8, _safe_text(header), border=1, fill=True, align="C")
            pdf.ln()

            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(237, 242, 247)
            for index, row in enumerate(normalized_rows):
                if pdf.get_y() > 260:
                    pdf.add_page()
                    pdf.set_fill_color(11, 15, 20)
                    pdf.rect(0, 0, 210, 297, "F")
                    pdf.set_font("Arial", "B", 9)
                    pdf.set_fill_color(40, 40, 60)
                    pdf.set_text_color(255, 255, 255)
                    for width, header in zip(widths, headers):
                        pdf.cell(width, 8, _safe_text(header), border=1, fill=True, align="C")
                    pdf.ln()
                    pdf.set_font("Arial", "", 9)
                    pdf.set_text_color(237, 242, 247)

                fill = (22, 30, 40) if index % 2 == 0 else (30, 40, 60)
                pdf.set_fill_color(*fill)
                values = [
                    row[0],
                    row[1],
                    row[2],
                    _format_amount(_parse_amount(row[3])),
                    row[4],
                    row[5],
                ]
                for width, value in zip(widths, values):
                    pdf.cell(width, 8, _safe_text(value), border=0, fill=True, align="C")
                pdf.ln()

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
            writer.writerow(["Nom", "Prénom", "Mois", "Montant", "Devise", "Statut"])
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
        self.table_data = list(table_data or [])
        self.filter_summary = filter_summary
        self.title("TAP · Export")
        self.geometry("460x260")
        self.minsize(380, 220)
        self.resizable(True, True)
        self.configure(fg_color=C["bg_deep"])
        self.transient(parent)
        self.grab_set()

        card = ctk.CTkFrame(self, fg_color=C["bg_card"], corner_radius=16,
                            border_width=1, border_color=C["border"])
        card.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(card, text="Exporter les données affichées",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=C["accent"]).pack(pady=(24, 8))

        ctk.CTkLabel(card,
                     text=f"{len(self.table_data)} ligne(s) disponibles. Choisis le format d’export.",
                     font=ctk.CTkFont(size=11),
                     text_color=C["text_lo"]).pack(pady=(0, 18))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(pady=(0, 18))

        ctk.CTkButton(
            btn_row,
            text="Exporter PDF",
            width=140,
            height=38,
            fg_color=C["accent"],
            hover_color=C["accent_dim"],
            text_color="#000000",
            command=self.exporter_pdf,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="Exporter CSV",
            width=140,
            height=38,
            fg_color=C["bg_section"],
            hover_color=C["border"],
            text_color=C["text_hi"],
            command=self.exporter_csv,
        ).pack(side="left")

        ctk.CTkButton(
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
        ).pack(pady=(0, 20))

    def exporter_pdf(self):
        if export_current_view_to_pdf(self, self.table_data, self.filter_summary):
            self.destroy()

    def exporter_csv(self):
        if export_current_view_to_csv(self, self.table_data, self.filter_summary):
            self.destroy()
