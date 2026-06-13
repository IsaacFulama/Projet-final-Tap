import mysql.connector

from tap.config.settings import load_db_config


def obtenir_connexion():
    config = load_db_config()
    return mysql.connector.connect(
        host=config["host"],
        database=config["database"],
        user=config["user"],
        password=config["password"],
    )
