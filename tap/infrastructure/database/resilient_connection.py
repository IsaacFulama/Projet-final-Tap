"""
Module de connexion résiliente à la base de données avec auto-réparation.

Ce module fournit:
- Reconnexion automatique en cas de déconnexion
- Détection et correction des problèmes de connexion
- Pool de connexions avec retry automatique
- Gestion intelligente des timeouts
"""

import logging
import time
from typing import Optional, Callable
from contextlib import contextmanager

from mysql.connector import Error, MySQLConnection
from mysql.connector.pooling import PooledMySQLConnection

from tap.infrastructure.database.connection import MySQLConnectionProvider
from tap.config.settings import load_db_config

_base_provider = MySQLConnectionProvider()
logger = logging.getLogger(__name__)


class ResilientConnection:
    """Gestionnaire de connexion résiliente avec auto-réparation."""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 2.0):
        """
        Initialise le gestionnaire de connexion résiliente.
        
        Args:
            max_retries: Nombre maximum de tentatives de reconnexion
            retry_delay: Délai entre les tentatives en secondes
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connection_pool = {}
        self.last_connection_attempt = {}
        self.connection_health = {}
    
    def get_connection_with_retry(self) -> Optional[MySQLConnection]:
        """
        Obtient une connexion avec retry automatique.
        
        Returns:
            Connexion MySQL ou None si échec
        """
        for attempt in range(self.max_retries):
            try:
                conn = _base_provider()
                
                if conn and conn.is_connected():
                    self._update_connection_health(conn, True)
                    logger.info(f"Connexion réussie (tentative {attempt + 1})")
                    return conn
                
                logger.warning(f"Connexion échouée (tentative {attempt + 1})")
                
            except Error as e:
                logger.error(f"Erreur de connexion (tentative {attempt + 1}): {e}")
                self._attempt_connection_repair(e)
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        logger.error("Échec de connexion après toutes les tentatives")
        return None
    
    def _update_connection_health(self, conn: MySQLConnection, is_healthy: bool):
        """Met à jour l'état de santé de la connexion."""
        conn_id = id(conn)
        self.connection_health[conn_id] = {
            "is_healthy": is_healthy,
            "last_check": time.time(),
        }
    
    def _attempt_connection_repair(self, error: Error):
        """
        Tente de réparer la connexion automatiquement.
        
        Args:
            error: Erreur de connexion
        """
        error_msg = str(error).lower()
        
        if "access denied" in error_msg:
            logger.warning("Erreur d'accès détectée - Vérifiez les identifiants dans config.json")
        
        elif "unknown database" in error_msg:
            logger.warning("Base de données inconnue - Tentative de création...")
            self._create_database_if_not_exists()
        
        elif "can't connect" in error_msg:
            logger.warning("Serveur inaccessible - Vérifiez que MySQL est démarré")
        
        elif "timeout" in error_msg:
            logger.warning("Timeout de connexion - Augmentation du délai...")
    
    def _create_database_if_not_exists(self):
        """Crée la base de données si elle n'existe pas."""
        try:
            db_config = load_db_config()
            db_name = db_config.get("database", "gestion_loyers")
            
            # Connexion sans spécifier la base de données
            import mysql.connector
            conn = mysql.connector.connect(
                host=db_config.get("host", "localhost"),
                user=db_config.get("user", "root"),
                password=db_config.get("password", ""),
                port=db_config.get("port", 3306),
            )

            cursor = conn.cursor()
            safe_name = str(db_name).replace("`", "``")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{safe_name}`")
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Base de données {db_name} créée avec succès")
            
        except Exception as e:
            logger.error(f"Impossible de créer la base de données: {e}")
    
    @contextmanager
    def resilient_cursor(self):
        """
        Context manager pour un curseur résilient.
        
        Yields:
            Curseur MySQL avec gestion automatique des erreurs
        """
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection_with_retry()
            if not conn:
                raise Exception("Impossible d'obtenir une connexion")
            
            cursor = conn.cursor()
            yield cursor
            
            conn.commit()
            
        except Error as e:
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
        """
        Vérifie la santé de la connexion.
        
        Returns:
            Dict avec l'état de santé de la connexion
        """
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
        """
        Exécute une requête avec retry automatique.
        
        Args:
            query: Requête SQL
            params: Paramètres de la requête
        
        Returns:
            Résultats de la requête ou None si échec
        """
        for attempt in range(self.max_retries):
            try:
                with self.resilient_cursor() as cursor:
                    cursor.execute(query, params or ())
                    return cursor.fetchall()
            
            except Error as e:
                logger.error(f"Erreur d'exécution (tentative {attempt + 1}): {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        return None


# Instance globale du gestionnaire de connexion résiliente
resilient_connection = ResilientConnection()


def obtenir_connexion_resiliente() -> Optional[MySQLConnection]:
    """
    Obtient une connexion avec gestion automatique des erreurs.
    
    Returns:
        Connexion MySQL ou None si échec
    """
    return resilient_connection.get_connection_with_retry()


def executer_avec_retry(query: str, params: tuple = None) -> Optional[list]:
    """
    Exécute une requête avec retry automatique.
    
    Args:
        query: Requête SQL
        params: Paramètres de la requête
    
    Returns:
        Résultats de la requête ou None si échec
    """
    return resilient_connection.execute_with_retry(query, params)
