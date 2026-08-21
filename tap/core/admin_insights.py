"""Indicateurs et recommandations explicables du Centre d'administration."""

from __future__ import annotations

from decimal import Decimal


def _decimal(value) -> Decimal:
    try:
        return Decimal(str(value or 0).replace(",", "."))
    except Exception:
        return Decimal("0")


def build_admin_insights(records: list) -> dict:
    records = list(records or [])
    total = sum((_decimal(getattr(r, "total_amount", 0)) for r in records), Decimal("0"))
    paid = sum((_decimal(getattr(r, "paid_amount", 0)) for r in records), Decimal("0"))
    remaining = max(Decimal("0"), total - paid)
    overdue = sum(str(getattr(r, "payment_status", "")).lower() in {"litigieux", "en attente"} for r in records)
    unsigned = sum(not getattr(r, "is_signed", False) for r in records)
    rate = float((paid / total * 100) if total else 0)
    recommendations = []
    if not records:
        recommendations.append("Ajoutez un premier enregistrement pour activer les recommandations.")
    elif overdue:
        recommendations.append(f"Priorité : examiner {overdue} dossier(s) en attente ou litigieux.")
    if unsigned:
        recommendations.append(f"{unsigned} reçu(s) ne sont pas encore signés.")
    if not recommendations:
        recommendations.append("Aucune urgence détectée : votre portefeuille est à jour.")
    if not records:
        health, alert = "inconnu", "Aucune donnée exploitable pour le moment."
    elif overdue >= 3 or rate < 60:
        health, alert = "critique", "Action recommandée aujourd’hui : traiter les impayés prioritaires."
    elif overdue or rate < 90 or unsigned:
        health, alert = "surveillance", "Votre portefeuille nécessite une vérification ciblée."
    else:
        health, alert = "sain", "Les opérations sont sous contrôle."
    return {"total": total, "paid": paid, "remaining": remaining, "overdue": overdue, "unsigned": unsigned, "collection_rate": rate, "health": health, "alert": alert, "recommendations": recommendations}
