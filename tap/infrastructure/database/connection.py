import os
from collections.abc import Callable
from typing import Protocol, runtime_checkable

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv(override=True)

MESSAGE_BASE_INDISPONIBLE = (
    "La base de données n'est pas accessible. "
    "Vérifiez votre connexion internet ou votre lien Supabase."
)


def _sanitize_identifier(identifier: str) -> str:
    return identifier.replace("`", "``")


@runtime_checkable
class ConnectionProtocol(Protocol):
    def cursor(self, dictionary: bool = False, buffered: bool = False): ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...

    def is_connected(self) -> bool: ...


ConnectionProvider = Callable[[], ConnectionProtocol]

class PsycopgCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor
        
    def execute(self, query, params=None):
        # Psycopg3 uses %s just like MySQL connector
        # But we need to replace some MySQL specific queries maybe?
        # Let's just pass it to psycopg.
        return self._cursor.execute(query, params)
        
    def fetchone(self):
        return self._cursor.fetchone()
        
    def fetchall(self):
        return self._cursor.fetchall()
        
    def close(self):
        self._cursor.close()
        
    @property
    def rowcount(self):
        return self._cursor.rowcount
        
    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)
        
    def __iter__(self):
        return iter(self._cursor)
        
    @property
    def description(self):
        return self._cursor.description


class PsycopgConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn
        
    def cursor(self, dictionary: bool = False, buffered: bool = False):
        if dictionary:
            c = self._conn.cursor(row_factory=dict_row)
        else:
            c = self._conn.cursor()
        return PsycopgCursorWrapper(c)
        
    def commit(self):
        self._conn.commit()
        
    def rollback(self):
        self._conn.rollback()
        
    def close(self):
        self._conn.close()
        
    def is_connected(self):
        return not self._conn.closed


class SupabaseConnectionProvider:
    """Fournisseur de connexions PostgreSQL (Supabase)."""

    def __call__(self) -> ConnectionProtocol:
        dsn = os.getenv("SUPABASE_DB_URL")
        if not dsn:
            raise ValueError("SUPABASE_DB_URL n'est pas defini dans .env")
        return PsycopgConnectionWrapper(psycopg.connect(dsn))


class ResilientProviderWrapper:
    def __call__(self) -> ConnectionProtocol | None:
        from tap.infrastructure.database.resilient_connection import obtenir_connexion_resiliente
        return obtenir_connexion_resiliente()


_default_provider = ResilientProviderWrapper()


def connexion_prete(conn: ConnectionProtocol | None) -> bool:
    """True seulement si la connexion existe et répond comme ouverte."""
    if conn is None:
        return False
    checker = getattr(conn, "is_connected", None)
    if not callable(checker):
        return True
    try:
        return bool(checker())
    except Exception:
        return False


def rollback_si_possible(conn: ConnectionProtocol | None) -> None:
    if not connexion_prete(conn):
        return
    rollback = getattr(conn, "rollback", None)
    if callable(rollback):
        try:
            rollback()
        except Exception:
            pass


def fermer_connexion(conn: ConnectionProtocol | None, cursor=None) -> None:
    if cursor is not None:
        try:
            cursor.close()
        except Exception:
            pass
    if not connexion_prete(conn):
        return
    try:
        conn.close()
    except Exception:
        pass


def obtenir_connexion(provider: ConnectionProvider | None = None) -> ConnectionProtocol | None:
    active_provider = provider or _default_provider
    return active_provider()


def get_default_connection_provider() -> ConnectionProvider:
    return _default_provider
