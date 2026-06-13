from tap.infrastructure.database.connection import obtenir_connexion
from tap.infrastructure.database.migrations import run_migrations
from tap.infrastructure.database.repository import (
    get_historique_locataire,
    get_souscriptions,
    get_souscriptions_avec_filtres,
    inserer_souscription,
    mettre_a_jour_statut,
    modifier_souscription,
    recuperer_inventaire,
    supprimer_souscription,
)

run_migrations()

__all__ = [
    "obtenir_connexion",
    "inserer_souscription",
    "recuperer_inventaire",
    "get_souscriptions",
    "mettre_a_jour_statut",
    "get_souscriptions_avec_filtres",
    "get_historique_locataire",
    "modifier_souscription",
    "supprimer_souscription",
]
