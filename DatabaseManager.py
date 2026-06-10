import mysql.connector
from mysql.connector import pooling
import logging

class DatabaseManager:
    _pool = None

    @classmethod
    def _init_pool(cls):
        if cls._pool is None:
            try:
                # Configuration du pool : conserve 5 connexions ouvertes
                cls._pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name="tap_pool",
                    pool_size=5,
                    host='localhost',
                    database='gestion_loyers',
                    user='root',
                    password=''
                )
            except mysql.connector.Error as e:
                logging.error(f"Erreur de création du pool BDD : {e}")
                raise

    @classmethod
    def execute(cls, query, params=(), fetch=False):
        cls._init_pool()
        conn = cls._pool.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()
            conn.commit()
            return cursor.lastrowid
        except mysql.connector.Error as e:
            logging.error(f"Erreur SQL : {e}")
            raise
        finally:
            cursor.close()
            conn.close()