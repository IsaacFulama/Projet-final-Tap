"""
Module de mise à jour automatique des statuts de paiement.
Change automatiquement le statut à "Litigieux" le 5 du mois suivant pour les paiements en attente.
"""

import logging
from datetime import date
from typing import Tuple, List

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


def verifier_et_mettre_a_jour_statuts() -> Tuple[int, int]:
    """
    Vérifie et met à jour automatiquement les statuts des paiements.
    
    Change le statut à "Litigieux" le 5 du mois suivant pour les paiements:
    - En attente (sans paiement)
    - Avec acompte (paiement partiel)
    
    Returns:
        Tuple[int, int]: (nombre de paiements mis à jour, nombre d'erreurs)
    """
    conn = None
    cursor = None
    mis_a_jour = 0
    erreurs = 0
    
    try:
        conn = obtenir_connexion()
        if conn.is_connected():
            cursor = conn.cursor()
            
            # Date actuelle
            aujourdhui = date.today()
            jour_actuel = aujourdhui.day
            
            logger.info(f"Vérification automatique des statuts - Date: {aujourdhui}")
            
            # Ne faire la mise à jour que le 5 du mois
            if jour_actuel != 5:
                logger.info(f"Aucune mise à jour nécessaire (jour {jour_actuel}, pas le 5)")
                return 0, 0
            
            # Trouver les paiements qui doivent être mis à jour
            # Critères:
            # - Statut = "En attente" ou "Litigieux"
            # - Mois de paiement < mois actuel
            query = """
                SELECT id, locataire_id, mois, statut, montant_total, montant_paye, reste_a_payer
                FROM paiements
                WHERE statut IN ('En attente', 'Litigieux')
                AND mois < %s
                ORDER BY mois ASC
            """
            
            cursor.execute(query, (aujourdhui.strftime('%Y-%m-%d'),))
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


def obtenir_paiements_a_suivi() -> List[dict]:
    """
    Obtient la liste des paiements qui nécessitent un suivi.
    
    Returns:
        List[dict]: Liste des paiements avec informations de suivi
    """
    conn = None
    cursor = None
    paiements = []
    
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
                ORDER BY p.mois ASC
            """
            
            cursor.execute(query)
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


def executer_mise_a_jour_automatique() -> dict:
    """
    Exécute la mise à jour automatique et retourne un rapport.
    
    Returns:
        dict: Rapport de la mise à jour
    """
    logger.info("=" * 60)
    logger.info("Démarrage de la mise à jour automatique des statuts")
    logger.info("=" * 60)
    
    mis_a_jour, erreurs = verifier_et_mettre_a_jour_statuts()
    
    paiements_suivi = obtenir_paiements_a_suivi()
    
    rapport = {
        'date': date.today().isoformat(),
        'mis_a_jour': mis_a_jour,
        'erreurs': erreurs,
        'paiements_a_suivi': len(paiements_suivi),
        'details_paiements': paiements_suivi
    }
    
    logger.info(f"Rapport: {rapport}")
    logger.info("=" * 60)
    
    return rapport


if __name__ == "__main__":
    # Pour tester manuellement
    rapport = executer_mise_a_jour_automatique()
    print(f"Mise à jour terminée: {rapport['mis_a_jour']} paiements mis à jour")
    print(f"Paiements à suivre: {rapport['paiements_a_suivi']}")
