"""Modèles de données utilisés entre la base de données et l'interface.

Les requêtes historiques retournaient des tuples dont le sens dépendait de la
position des colonnes. Ces modèles rendent le contrat explicite et permettent
à l'interface d'évoluer sans casser la couche de persistance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class SubscriptionRecord:
    """Une souscription affichée dans le tableau principal."""

    payment_id: int
    tenant_id: int
    last_name: str
    first_name: str
    month: Any
    amount: Any
    currency: str
    subscription_status: str
    status: str
    created_at: Any = None
    total_amount: Any = None
    paid_amount: Any = None
    remaining_amount: Any = None
    payment_status: str = "En attente"
    is_signed: bool = False

    @classmethod
    def from_row(cls, row: Sequence[Any]) -> "SubscriptionRecord":
        """Construit un modèle depuis une ligne SQL actuelle ou historique."""
        amount = row[5] if len(row) > 5 else 0
        return cls(
            payment_id=row[0],
            tenant_id=row[1],
            last_name=str(row[2] or ""),
            first_name=str(row[3] or ""),
            month=row[4] if len(row) > 4 else "",
            amount=amount,
            currency=str(row[6] or ""),
            subscription_status=str(row[7] or "Simple"),
            status=str(row[8] or "En attente"),
            created_at=row[9] if len(row) > 9 else None,
            total_amount=row[10] if len(row) > 10 else amount,
            paid_amount=row[11] if len(row) > 11 else 0,
            remaining_amount=row[12] if len(row) > 12 else 0,
            payment_status=str(row[13] or "En attente") if len(row) > 13 else "En attente",
            is_signed=bool(row[14]) if len(row) > 14 else False,
        )

    @property
    def visible_values(self) -> tuple[Any, ...]:
        """Valeurs destinées aux colonnes visibles du tableau."""
        return (
            self.month,
            self.total_amount if self.total_amount is not None else self.amount,
            self.paid_amount if self.paid_amount is not None else 0,
            self.remaining_amount if self.remaining_amount is not None else 0,
            self.currency,
            self.subscription_status,
            self.status,
            self.payment_status,
            "Signé" if self.is_signed else "Non signé",
        )

    def to_metadata(self) -> dict[str, Any]:
        """Retourne les données nécessaires aux actions de l'interface."""
        return {
            "paiement_id": self.payment_id,
            "locataire_id": self.tenant_id,
            "nom": self.last_name,
            "prenom": self.first_name,
            "mois": self.month,
            "montant": self.amount,
            "devise": self.currency,
            "statut_souscription": self.subscription_status,
            "statut": self.status,
            "montant_total": self.total_amount if self.total_amount is not None else self.amount,
            "montant_paye": self.paid_amount if self.paid_amount is not None else 0,
            "reste_a_payer": self.remaining_amount if self.remaining_amount is not None else 0,
            "statut_paiement": self.payment_status,
            "est_signe": self.is_signed,
        }

    def to_edit_tuple(self) -> tuple[Any, ...]:
        """Format temporaire conservé pour les formulaires existants."""
        return (
            self.payment_id,
            self.tenant_id,
            self.last_name,
            self.first_name,
            self.month,
            self.amount,
            self.currency,
            self.subscription_status,
            self.status,
            self.total_amount if self.total_amount is not None else self.amount,
            self.paid_amount if self.paid_amount is not None else 0,
            self.remaining_amount if self.remaining_amount is not None else 0,
            self.payment_status,
        )


@dataclass(frozen=True)
class HistoryPayment:
    """Ligne d'historique d'un locataire."""

    month: Any
    amount: Any
    currency: str
    subscription_status: str
    status: str
    total_amount: Any = 0
    paid_amount: Any = 0
    remaining_amount: Any = 0
    payment_status: str = "En attente"

    @classmethod
    def from_row(cls, row: Sequence[Any]) -> "HistoryPayment":
        amount = row[1] if len(row) > 1 else 0
        return cls(
            month=row[0] if len(row) > 0 else "",
            amount=amount,
            currency=str(row[2] or "") if len(row) > 2 else "",
            subscription_status=str(row[3] or "Simple") if len(row) > 3 else "Simple",
            status=str(row[4] or "En attente") if len(row) > 4 else "En attente",
            total_amount=row[5] if len(row) > 5 else amount,
            paid_amount=row[6] if len(row) > 6 else amount,
            remaining_amount=row[7] if len(row) > 7 else 0,
            payment_status=str(row[8] or "Complet") if len(row) > 8 else "Complet",
        )
