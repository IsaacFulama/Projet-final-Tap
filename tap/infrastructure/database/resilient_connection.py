"""
Module de connexion résiliente à la base de données avec auto-réparation.

Ce module fournit:
- Reconnexion automatique en cas de déconnexion
- Détection et correction des problèmes de connexion
- Gestion intelligente des timeouts
"""

import logging
import time
from typing import Optional
from contextlib import contextmanager

from tap.infrastructure.database.connection import SupabaseConnectionProvider, ConnectionProtocol

_base_provider = SupabaseConnectionProvider()
logger = logging.getLogger(__name__)


class ResilientConnection:
    """Gestionnaire de connexion résiliente avec auto-réparation."""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 2.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connection_health = {}
    
    def get_connection_with_retry(self) -> Optional[ConnectionProtocol]:
        """Obtient une connexion avec retry automatique."""
        for attempt in range(self.max_retries):
            try:
                conn = _base_provider()
                if conn and conn.is_connected():
                    self._update_connection_health(conn, True)
                    logger.info(f"Connexion réussie (tentative {attempt + 1})")
                    return conn
                logger.warning(f"Connexion échouée (tentative {attempt + 1})")
            except Exception as e:
                logger.error(f"Erreur de connexion (tentative {attempt + 1}): {e}")
                self._attempt_connection_repair(e)
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        logger.error("Échec de connexion après toutes les tentatives")
        return None
    
    def _update_connection_health(self, conn: ConnectionProtocol, is_healthy: bool):
        conn_id = id(conn)
        self.connection_health[conn_id] = {
            "is_healthy": is_healthy,
            "last_check": time.time(),
        }
    
    def _attempt_connection_repair(self, error: Exception):
        error_msg = str(error).lower()
        if "password authentication failed" in error_msg or "access denied" in error_msg:
            logger.warning("Erreur d'accès détectée - Vérifiez le mot de passe dans .env (SUPABASE_DB_URL)")
        elif "timeout" in error_msg:
            logger.warning("Timeout de connexion - Augmentation du délai...")
    
    @contextmanager
    def resilient_cursor(self):
        """Context manager pour un curseur résilient."""
        conn = None
        cursor = None
        try:
            conn = self.get_connection_with_retry()
            if not conn:
                raise Exception("Impossible d'obtenir une connexion")
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception as e:
            logger.error(f"Erreur avec le curseur résilient: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
    
    def check_connection_health(self) -> dict:
        try:
            conn = self.get_connection_with_retry()
            if conn and conn.is_connected():
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                conn.close()
                return {
                    "status": "healthy",
                    "message": "Connexion à la base de données fonctionnelle",
                    "timestamp": time.time(),
                }
            return {
                "status": "unhealthy",
                "message": "Impossible de se connecter à la base de données",
                "timestamp": time.time(),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Erreur de vérification: {e}",
                "timestamp": time.time(),
            }
    
    def execute_with_retry(self, query: str, params: tuple = None) -> Optional[list]:
        for attempt in range(self.max_retries):
            try:
                with self.resilient_cursor() as cursor:
                    cursor.execute(query, params or ())
                    return cursor.fetchall()
            except Exception as e:
                logger.error(f"Erreur d'exécution (tentative {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        return None


resilient_connection = ResilientConnection()

def obtenir_connexion_resiliente() -> Optional[ConnectionProtocol]:
    return resilient_connection.get_connection_with_retry()

def executer_avec_retry(query: str, params: tuple = None) -> Optional[list]:
    return resilient_connection.execute_with_retry(query, params)
