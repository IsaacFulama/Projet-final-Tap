from collections.abc import Callable
from typing import Protocol, runtime_checkable

import mysql.connector

from tap.config.settings import load_db_config


def _sanitize_identifier(identifier: str) -> str:
    return identifier.replace("`", "``")


@runtime_checkable
class ConnectionProtocol(Protocol):
    def cursor(self): ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...

    def is_connected(self) -> bool: ...


ConnectionProvider = Callable[[], ConnectionProtocol]


class MySQLConnectionProvider:
    """Fournisseur concret de connexions MySQL."""

    def __call__(self) -> ConnectionProtocol:
        config = load_db_config()
        host = config["host"]
        database = config["database"]
        user = config["user"]
        password = config["password"]
        port = config.get("port", 3306)

        try:
            return mysql.connector.connect(
                host=host,
                database=database,
                user=user,
                password=password,
                port=port,
            )
        except mysql.connector.Error as exc:
            error_text = str(exc).lower()
            if "unknown database" in error_text or "1049" in error_text:
                fallback_conn = mysql.connector.connect(
                    host=host,
                    user=user,
                    password=password,
                    port=port,
                )
                try:
                    cursor = fallback_conn.cursor()
                    cursor.execute(
                        f"CREATE DATABASE IF NOT EXISTS `{_sanitize_identifier(database)}`"
                    )
                    fallback_conn.commit()
                    cursor.close()
                finally:
                    fallback_conn.close()

                return mysql.connector.connect(
                    host=host,
                    database=database,
                    user=user,
                    password=password,
                    port=port,
                )
            raise


class ResilientProviderWrapper:
    def __call__(self) -> ConnectionProtocol:
        from tap.infrastructure.database.resilient_connection import obtenir_connexion_resiliente
        return obtenir_connexion_resiliente()


_default_provider = ResilientProviderWrapper()


def obtenir_connexion(provider: ConnectionProvider | None = None) -> ConnectionProtocol:
    """Obtient une connexion via un fournisseur injectable.

    Le provider par défaut reste MySQL, mais les couches amont peuvent injecter
    un faux provider pour les tests ou un autre backend conforme au contrat.
    """
    active_provider = provider or _default_provider
    return active_provider()


def get_default_connection_provider() -> ConnectionProvider:
    """Expose le provider concret par défaut pour les usages avancés."""
    return _default_provider
