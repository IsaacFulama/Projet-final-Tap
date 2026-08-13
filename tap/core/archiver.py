import logging
import threading
from datetime import datetime, timedelta

from tap.infrastructure.database.connection import obtenir_connexion

logger = logging.getLogger(__name__)

# On considère comme vieux les enregistrements de plus de 5 mois
MOIS_ARCHIVE_LIMITE = 5

def executer_archivage():
    """Déplace les paiements vieux de plus de MOIS_ARCHIVE_LIMITE mois vers la table d'archives."""
    try:
        conn = obtenir_connexion()
        if not conn.is_connected():
            return

        cursor = conn.cursor()
        
        # Date limite : aujourd'hui - 24 mois (environ 730 jours)
        date_limite = datetime.now() - timedelta(days=MOIS_ARCHIVE_LIMITE * 30)
        date_limite_str = date_limite.strftime('%Y-%m-%d')
        
        # 1. Copier vers archives_paiements (avec IGNORE pour éviter les doublons si déjà archivé)
        query_insert = f"""
            INSERT IGNORE INTO archives_paiements 
            SELECT * FROM paiements 
            WHERE mois < '{date_limite_str}'
        """
        cursor.execute(query_insert)
        lignes_archivees = cursor.rowcount
        
        # 2. Supprimer de paiements les enregistrements qu'on vient de copier
        if lignes_archivees > 0:
            query_delete = f"""
                DELETE FROM paiements 
                WHERE mois < '{date_limite_str}'
            """
            cursor.execute(query_delete)
            conn.commit()
            logger.info(f"Auto-Archivage: {lignes_archivees} enregistrements anciens archivés avec succès.")
        else:
            conn.commit()
            logger.info("Auto-Archivage: Aucun enregistrement ancien à archiver aujourd'hui.")
            
        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"Erreur lors de l'archivage automatique: {e}")


def lancer_archivage_en_arriere_plan():
    """Démarre le nettoyage/archivage dans un thread séparé."""
    thread = threading.Thread(target=executer_archivage, daemon=True, name="AutoArchiverThread")
    thread.start()
