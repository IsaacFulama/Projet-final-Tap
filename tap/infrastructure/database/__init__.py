"""
Module d'infrastructure de base de données.

Ce module fournit l'accès à la base de données et les opérations CRUD
de base pour l'application TAP Gestion des Loyers.
"""

import logging

from tap.infrastructure.database.connection import obtenir_connexion
from tap.infrastructure.database.repository import (
    ajouter_paiement_complementaire,
    enregistrer_signature_et_mettre_a_jour_paiement,
    get_historique_locataire,
    get_souscriptions,
    get_souscriptions_avec_filtres,
    inserer_souscription,
    mettre_a_jour_statut,
    modifier_souscription,
    recuperer_inventaire,
    supprimer_souscription,
)

logger = logging.getLogger(__name__)

# Les migrations sont lancées par ensure_startup_ready() au démarrage de l'UI.
# Les exécuter ici à l'import provoquait des retries MySQL et des crashs None.

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
    "ajouter_paiement_complementaire",
    "enregistrer_signature_et_mettre_a_jour_paiement",
]
