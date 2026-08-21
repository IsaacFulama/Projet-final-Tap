C = {
    "bg_deep":    "#FFFFFF",
    "bg_panel":   "#FFFFFF",
    "bg_card":    "#FFFFFF",
    "bg_section": "#F7F9FC",
    "border":     "#D7E0EA",
    "accent":     "#C9A84C",
    "accent_dim": "#A88537",
    "text_hi":    "#0F172A",
    "text_lo":    "#475569",
    "green":      "#1F9D67",
    "orange":     "#D97706",
    "blue":       "#2563EB",
    "red":        "#DC2626",
    "red_hover":  "#B91C1C",
    "tbl_even":   "#FFFFFF",
    "tbl_odd":    "#F9FBFD",
    "tbl_select": "#D8E8FF",
    "tbl_head":   "#EEF3F8",
}

BRANDING = {
    "name": "TAP",
    "subtitle": "GESTION LOYERS",
    "tagline": "ERP immobilier",
    "logo_path": "",
}


def apply_branding(branding: dict | None) -> None:
    """Surcharge l'identité visuelle depuis config.json, sans obligation."""
    if not isinstance(branding, dict):
        return
    for key in ("name", "subtitle", "tagline", "logo_path"):
        value = branding.get(key)
        if isinstance(value, str) and value.strip():
            BRANDING[key] = value.strip()[:80]
    for source, target in (("accent", "accent"), ("accent_dim", "accent_dim"),
                           ("primary", "accent"), ("primary_hover", "accent_dim")):
        value = branding.get(source)
        if isinstance(value, str) and len(value) in (4, 7) and value.startswith("#"):
            C[target] = value
            MPL["accent"] = value

MPL = {
    "bg":     "#FFFFFF",
    "axes":   "#FCFDFE",
    "grid":   "#D7E0EA",
    "text":   "#475569",
    "accent": "#C9A84C",
    "green":  "#1F9D67",
    "orange": "#D97706",
    "blue":   "#2563EB",
    "red":    "#DC2626",
}

STATUS_COLORS = {
    "En règle":   MPL["green"],
    "Litigieux":  MPL["orange"],
    "En attente": MPL["blue"],
}

MONTH_ALIASES = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
