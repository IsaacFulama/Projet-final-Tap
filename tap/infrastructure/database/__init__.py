"""
Module d'infrastructure de base de données.

Ce module fournit l'accès à la base de données et les opérations CRUD
de base pour l'application TAP Gestion des Loyers.
"""

import logging

from tap.infrastructure.database.connection import obtenir_connexion
from tap.infrastructure.database.migrations import run_migrations
from tap.infrastructure.database.repository import (
    ajouter_paiement_complementaire,
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

# Exécuter les migrations au démarrage avec gestion d'erreurs
try:
    run_migrations()
    logger.info("Migrations de base de données exécutées avec succès")
except Exception as e:
    logger.warning(f"Impossible d'exécuter les migrations: {e}")
    logger.warning("L'application continuera mais certaines fonctionnalités pourraient ne pas fonctionner correctement")

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
]
