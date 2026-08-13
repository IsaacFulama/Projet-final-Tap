from __future__ import annotations

from dataclasses import dataclass

import customtkinter as ctk


@dataclass(frozen=True)
class ScreenProfile:
    width: int
    height: int
    dpi_scale: float


@dataclass(frozen=True)
class LayoutProfile:
    name: str
    sidebar_width: int
    main_padding: int
    table_card_columns: int
    kpi_columns: int
    chart_mode: str
    filter_mode: str
    table_row_height: int
    table_body_font_size: int
    table_head_font_size: int
    sidebar_brand_size: int
    sidebar_subtitle_size: int
    sidebar_button_size: int
    header_title_size: int
    header_subtitle_size: int
    card_value_size: int
    card_label_size: int
    table_widths: dict[str, int]


def detect_screen_profile() -> ScreenProfile:
    """Détecte la taille d'écran et le facteur DPI courant."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        try:
            dpi_scale = float(root.winfo_fpixels("1i")) / 96.0
        except Exception:
            dpi_scale = 1.0
    finally:
        root.destroy()

    return ScreenProfile(width=width, height=height, dpi_scale=dpi_scale)


def apply_responsive_scaling(profile: ScreenProfile | None = None) -> ScreenProfile:
    """
    Applique une échelle d'interface adaptée à la taille et à la densité de l'écran.
    """
    profile = profile or detect_screen_profile()
    short_side = min(profile.width, profile.height)

    if short_side < 900:
        size_scale = 0.88
    elif short_side < 1100:
        size_scale = 0.95
    elif short_side < 1400:
        size_scale = 1.00
    elif short_side < 1800:
        size_scale = 1.06
    else:
        size_scale = 1.12

    widget_scale = max(0.85, min(profile.dpi_scale * size_scale, 1.30))
    window_scale = max(0.85, min(size_scale, 1.25))

    try:
        ctk.set_widget_scaling(widget_scale)
    except Exception:
        pass

    try:
        ctk.set_window_scaling(window_scale)
    except Exception:
        pass

    # Configurer la police des Treeview ttk pour améliorer la lisibilité sur toutes
    # tailles d'écran (permet de réduire légèrement la taille afin que les enregistrements
    # restent visibles dans des interfaces compactes).
    try:
        layout = build_layout_profile(profile.width)
        import tkinter as tk
        from tkinter import ttk
        style = ttk.Style()
        style.configure("TAP.Treeview", font=("Helvetica", layout.table_body_font_size))
        style.configure("TAP.Treeview.Heading", font=("Helvetica", layout.table_head_font_size, "bold"))
    except Exception:
        pass

    return profile


def build_layout_profile(window_width: int) -> LayoutProfile:
    """Retourne un profil de layout adapté à la largeur de la fenêtre."""
    if window_width < 1000:
        widths = {
            "Nom": 165,
            "Prénom": 150,
            "Mois": 120,
            "Montant": 120,
            "Devise": 85,
            "Statut Souscription": 150,
            "Statut des versements": 120,
        }
        return LayoutProfile(
            name="compact",
            sidebar_width=160,
            main_padding=12,
            table_card_columns=1,
            kpi_columns=2,
            chart_mode="stacked",
            filter_mode="stacked",
            table_row_height=38,
            table_body_font_size=10,
            table_head_font_size=9,
            sidebar_brand_size=30,
            sidebar_subtitle_size=9,
            sidebar_button_size=12,
            header_title_size=18,
            header_subtitle_size=11,
            card_value_size=22,
            card_label_size=10,
            table_widths=widths,
        )

    if window_width < 1400:
        widths = {
            "Nom": 205,
            "Prénom": 185,
            "Mois": 140,
            "Montant": 130,
            "Devise": 95,
            "Statut Souscription": 165,
            "Statut des versements": 135,
        }
        return LayoutProfile(
            name="medium",
            sidebar_width=185,
            main_padding=16,
            table_card_columns=2,
            kpi_columns=3,
            chart_mode="stacked",
            filter_mode="stacked",
            table_row_height=42,
            table_body_font_size=11,
            table_head_font_size=10,
            sidebar_brand_size=36,
            sidebar_subtitle_size=10,
            sidebar_button_size=12,
            header_title_size=21,
            header_subtitle_size=12,
            card_value_size=25,
            card_label_size=10,
            table_widths=widths,
        )

    widths = {
        "Nom": 230,
        "Prénom": 205,
        "Mois": 150,
        "Montant": 140,
        "Devise": 100,
        "Statut Souscription": 180,
        "Statut des versements": 145,
    }
    return LayoutProfile(
        name="wide",
        sidebar_width=210,
        main_padding=20,
        table_card_columns=4,
        kpi_columns=5,
        chart_mode="side",
        filter_mode="inline",
        table_row_height=46,
        table_body_font_size=11,
        table_head_font_size=10,
        sidebar_brand_size=42,
        sidebar_subtitle_size=10,
        sidebar_button_size=13,
        header_title_size=24,
        header_subtitle_size=13,
        card_value_size=28,
        card_label_size=11,
        table_widths=widths,
    )


def clamp_window_geometry(
    screen_width: int,
    screen_height: int,
    width_ratio: float,
    height_ratio: float,
    min_width: int,
    min_height: int,
    max_width_margin: int = 24,
    max_height_margin: int = 24,
) -> tuple[int, int]:
    """Calcule une géométrie qui reste dans l'écran, même sur les petites résolutions."""
    max_width = max(320, screen_width - max_width_margin)
    max_height = max(260, screen_height - max_height_margin)

    width = int(screen_width * width_ratio)
    height = int(screen_height * height_ratio)

    width = min(max(width, min(min_width, max_width)), max_width)
    height = min(max(height, min(min_height, max_height)), max_height)

    return width, height
