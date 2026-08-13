"""Services applicatifs de paiement consommables par l'interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tap.infrastructure.database import (
    ajouter_paiement_complementaire,
    get_historique_locataire,
    get_souscriptions,
    mettre_a_jour_statut,
    modifier_souscription,
    supprimer_souscription,
)


@dataclass(frozen=True)
class SubscriptionFilters:
    name: str = ""
    status: str = "Tous"
    currency: str = ""
    month: str = ""
    subscription_status: str = "Tous"


class PaymentService:
    """Façade métier : la vue ne dépend plus directement du repository."""

    def list_subscriptions(self, filters: SubscriptionFilters):
        return get_souscriptions(
            filters.name,
            filters.status,
            filters.currency,
            filters.month,
            filters.subscription_status,
        )

    @staticmethod
    def update_status(payment_id: int, status: str):
        return mettre_a_jour_statut(payment_id, status)

    @staticmethod
    def delete(payment_id: int):
        return supprimer_souscription(payment_id)

    @staticmethod
    def add_payment(payment_id: int, amount: Any):
        return ajouter_paiement_complementaire(payment_id, amount)

    @staticmethod
    def history(tenant_id: int):
        return get_historique_locataire(tenant_id)

    @staticmethod
    def update(
        payment_id: int,
        name: str,
        first_name: str,
        phone: str,
        month: str,
        amount: Any,
        currency: str,
        status: str,
        subscription_status: str,
        paid_amount: Any = None,
        advance: Any = None,
    ):
        return modifier_souscription(
            payment_id,
            name,
            first_name,
            phone,
            month,
            amount,
            currency,
            status,
            subscription_status,
            paid_amount,
            advance,
        )
