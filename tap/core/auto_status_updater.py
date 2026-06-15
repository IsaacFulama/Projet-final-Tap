"""
Module de maintenance automatique des paiements.

Chaque démarrage:
- crée les enregistrements du mois courant pour les souscripteurs spéciaux
- laisse ces nouveaux enregistrements en "En attente"
- passe ces enregistrements en "Litigieux" à partir du 7 du mois
"""

import logging
from datetime import date
from typing import Tuple, List, Optional

from tap.infrastructure.database import obtenir_connexion

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_status_updater.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def verifier_et_mettre_a_jour_statuts(reference_date: Optional[date] = None) -> Tuple[int, int]:
    """
    Vérifie et met à jour automatiquement les statuts des paiements.
    
    Change le statut à "Litigieux" à partir du 7 de chaque mois pour les paiements:
    - En attente (sans paiement)
    - Avec acompte (paiement partiel)
    
    Utilise la date du système de l'ordinateur pour déterminer le jour actuel.
    
    Returns:
        Tuple[int, int]: (nombre de paiements mis à jour, nombre d'erreurs)
    """
    conn = None
    cursor = None
    mis_a_jour = 0
    erreurs = 0
    date_reference = reference_date or date.today()
    mois_courant = date_reference.replace(day=1)
    
    try:
        conn = obtenir_connexion()
        if conn.is_connected():
            cursor = conn.cursor()
            
            # Date de référence
            jour_actuel = date_reference.day
            
            logger.info(f"Vérification automatique des statuts - Date référence: {date_reference}")
            
            # Ne faire la mise à jour qu'à partir du 7 du mois
            if jour_actuel < 7:
                logger.info(f"Aucune mise à jour nécessaire (jour {jour_actuel}, avant le 7)")
                return 0, 0
            
            # Trouver les paiements qui doivent être mis à jour
            # Critères:
            # - Statut = "En attente" ou "Litigieux"
            # - Mois de paiement = mois courant
            query = """
                SELECT id, locataire_id, mois, statut, montant_total, montant_paye, reste_a_payer
                FROM paiements
                WHERE statut IN ('En attente', 'Litigieux')
                AND mois = %s
                ORDER BY mois ASC
            """
            
            cursor.execute(query, (mois_courant,))
            paiements = cursor.fetchall()
            
            logger.info(f"{len(paiements)} paiements éligibles pour mise à jour")
            
            for paiement in paiements:
                paiement_id, locataire_id, mois_paiement, statut_actuel, montant_total, montant_paye, reste_a_payer = paiement
                
                try:
                    # Déterminer le nouveau statut
                    if statut_actuel == "En attente":
                        nouveau_statut = "Litigieux"
                        message = f"Passage de En attente à Litigieux (paiement du {mois_paiement})"
                    elif statut_actuel == "Litigieux":
                        # Rester litigieux mais on peut logger
                        nouveau_statut = "Litigieux"
                        message = f"Rester Litigieux (paiement du {mois_paiement}, reste: {reste_a_payer})"
                    else:
                        continue
                    
                    # Mettre à jour le statut
                    update_query = """
                        UPDATE paiements
                        SET statut = %s
                        WHERE id = %s
                    """
                    
                    cursor.execute(update_query, (nouveau_statut, paiement_id))
                    mis_a_jour += 1
                    
                    logger.info(f"Paiement ID {paiement_id}: {message}")
                    
                except Exception as e:
                    erreurs += 1
                    logger.error(f"Erreur lors de la mise à jour du paiement {paiement_id}: {e}")
            
            conn.commit()
            logger.info(f"Mise à jour terminée: {mis_a_jour} paiements mis à jour, {erreurs} erreurs")
            
    except Exception as e:
        erreurs += 1
        logger.error(f"Erreur générale lors de la mise à jour des statuts: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
    
    return mis_a_jour, erreurs


def creer_souscriptions_speciales_mensuelles(reference_date: Optional[date] = None) -> Tuple[int, int]:
    """
    Crée automatiquement les enregistrements du mois courant pour les souscripteurs spéciaux.

    Pour chaque locataire ayant un dernier enregistrement avec le statut de souscription
    "Spécial", la fonction crée une ligne pour le mois courant si elle n'existe pas encore.
    Les nouveaux enregistrements sont créés en "En attente" avec montant payé à 0.

    Returns:
        Tuple[int, int]: (nombre de créations, nombre d'erreurs)
    """
    conn = None
    cursor = None
    creations = 0
    erreurs = 0
    date_reference = reference_date or date.today()

    try:
        conn = obtenir_connexion()
        if conn.is_connected():
            cursor = conn.cursor()

            mois_courant = date_reference.replace(day=1)
            logger.info(f"Vérification des souscriptions spéciales pour {mois_courant}")

            query = """
                SELECT p.id, p.locataire_id, p.montant_total, p.montant_paye, p.devise,
                       p.statut_souscription, l.nom, l.prenom, l.telephone
                FROM paiements p
                JOIN (
                    SELECT locataire_id, MAX(id) AS dernier_id
                    FROM paiements
                    WHERE statut_souscription = 'Spécial'
                    GROUP BY locataire_id
                ) derniers ON derniers.dernier_id = p.id
                JOIN locataires l ON l.id = p.locataire_id
                WHERE p.statut_souscription = 'Spécial'
                ORDER BY l.nom ASC, l.prenom ASC
            """

            cursor.execute(query)
            souscripteurs = cursor.fetchall()
            logger.info(f"{len(souscripteurs)} souscripteurs spéciaux trouvés pour duplication mensuelle")

            for (
                paiement_id,
                locataire_id,
                montant_total,
                montant_paye,
                devise,
                statut_souscription,
                nom,
                prenom,
                telephone,
            ) in souscripteurs:
                try:
                    cursor.execute(
                        """
                            SELECT id
                            FROM paiements
                            WHERE locataire_id = %s
                              AND mois = %s
                              AND statut_souscription = 'Spécial'
                            LIMIT 1
                        """,
                        (locataire_id, mois_courant),
                    )
                    existe_deja = cursor.fetchone()
                    if existe_deja:
                        logger.info(
                            f"Enregistrement déjà présent pour {nom} {prenom} au mois {mois_courant}"
                        )
                        continue

                    montant_total_val = float(montant_total or montant_paye or 0)
                    if montant_total_val <= 0:
                        logger.warning(
                            f"Montant invalide pour {nom} {prenom} (paiement ID {paiement_id}), duplication ignorée"
                        )
                        continue

                    cursor.execute(
                        """
                            INSERT INTO paiements (
                                locataire_id, mois, montant, montant_total, montant_paye,
                                reste_a_payer, devise, statut, statut_souscription, statut_paiement
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            locataire_id,
                            mois_courant,
                            montant_total_val,
                            montant_total_val,
                            0,
                            montant_total_val,
                            devise,
                            "En attente",
                            "Spécial",
                            "En attente",
                        ),
                    )
                    creations += 1
                    logger.info(
                        f"Duplication mensuelle créée pour {nom} {prenom} ({telephone or 'sans téléphone'})"
                    )

                except Exception as e:
                    erreurs += 1
                    logger.error(
                        f"Erreur lors de la duplication mensuelle du souscripteur {nom} {prenom}: {e}"
                    )

            conn.commit()
            logger.info(f"Duplication mensuelle terminée: {creations} créations, {erreurs} erreurs")

    except Exception as e:
        erreurs += 1
        logger.error(f"Erreur générale lors de la duplication mensuelle: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    return creations, erreurs


def obtenir_paiements_a_suivi(reference_date: Optional[date] = None) -> List[dict]:
    """
    Obtient la liste des paiements qui nécessitent un suivi.
    
    Returns:
        List[dict]: Liste des paiements avec informations de suivi
    """
    conn = None
    cursor = None
    paiements = []
    date_reference = reference_date or date.today()
    mois_courant = date_reference.replace(day=1)
    
    try:
        conn = obtenir_connexion()
        if conn.is_connected():
            cursor = conn.cursor()
            
            query = """
                SELECT p.id, p.mois, p.statut, p.montant_total, p.montant_paye, p.reste_a_payer,
                       l.nom, l.prenom, l.telephone
                FROM paiements p
                JOIN locataires l ON p.locataire_id = l.id
                WHERE p.statut IN ('En attente', 'Litigieux')
                AND p.mois = %s
                ORDER BY p.mois ASC
            """
            
            cursor.execute(query, (mois_courant,))
            resultats = cursor.fetchall()
            
            for row in resultats:
                paiements.append({
                    'id': row[0],
                    'mois': row[1],
                    'statut': row[2],
                    'montant_total': row[3],
                    'montant_paye': row[4],
                    'reste_a_payer': row[5],
                    'nom': row[6],
                    'prenom': row[7],
                    'telephone': row[8]
                })
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des paiements à suivre: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
    
    return paiements


def executer_mise_a_jour_automatique(reference_date: Optional[date] = None) -> dict:
    """
    Exécute la mise à jour automatique et retourne un rapport.
    
    Returns:
        dict: Rapport de la mise à jour
    """
    logger.info("=" * 60)
    logger.info("Démarrage de la mise à jour automatique des statuts")
    logger.info("=" * 60)

    date_reference = reference_date or date.today()
    
    creations, erreurs_creations = creer_souscriptions_speciales_mensuelles(date_reference)
    mis_a_jour, erreurs_mises_a_jour = verifier_et_mettre_a_jour_statuts(date_reference)
    
    paiements_suivi = obtenir_paiements_a_suivi(date_reference)
    
    rapport = {
        'date': date_reference.isoformat(),
        'creations_speciales': creations,
        'mis_a_jour': mis_a_jour,
        'erreurs': erreurs_creations + erreurs_mises_a_jour,
        'paiements_a_suivi': len(paiements_suivi),
        'details_paiements': paiements_suivi
    }
    
    logger.info(f"Rapport: {rapport}")
    logger.info("=" * 60)
    
    return rapport


def executer_demo_cycle_mensuel(reference_date: Optional[date] = None) -> dict:
    """
    Simule le passage du 1er et du 7 du mois sur une date donnée.
    """
    date_reference = reference_date or date.today().replace(day=1)
    date_premier = date_reference.replace(day=1)
    date_sept = date_reference.replace(day=7)

    logger.info("Démarrage de la démo du cycle mensuel")
    creations, erreurs_creations = creer_souscriptions_speciales_mensuelles(date_premier)
    mis_a_jour, erreurs_mises_a_jour = verifier_et_mettre_a_jour_statuts(date_sept)
    paiements_suivi = obtenir_paiements_a_suivi(date_sept)

    rapport = {
        "date_demo": date_reference.isoformat(),
        "date_premier": date_premier.isoformat(),
        "date_sept": date_sept.isoformat(),
        "creations_speciales": creations,
        "mis_a_jour": mis_a_jour,
        "erreurs": erreurs_creations + erreurs_mises_a_jour,
        "paiements_a_suivi": len(paiements_suivi),
        "details_paiements": paiements_suivi,
    }

    logger.info(f"Démo cycle mensuel terminée: {rapport}")
    return rapport


if __name__ == "__main__":
    # Pour tester manuellement
    rapport = executer_mise_a_jour_automatique()
    print(f"Créations mensuelles: {rapport['creations_speciales']}")
    print(f"Mise à jour terminée: {rapport['mis_a_jour']} paiements mis à jour")
    print(f"Paiements à suivre: {rapport['paiements_a_suivi']}")
