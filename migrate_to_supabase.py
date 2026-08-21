"""Charge le stock initial SQLite dans Supabase PostgreSQL.

Pour une source XAMPP, executer d'abord migrate_mysql_to_sqlite.py.

Strategie de chargement :
- chaque table SQLite est copiee (COPY, streaming, sans tout charger en
  memoire) dans une table temporaire "staging" de meme structure ;
- un seul INSERT ... SELECT ... ON CONFLICT DO NOTHING transfere ensuite
  staging vers la table finale, ce qui conserve l'idempotence du script
  (relancer le script ne duplique rien) tout en etant nettement plus rapide
  qu'un executemany() ligne par ligne.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

import psycopg
from psycopg import sql
from dotenv import load_dotenv

load_dotenv(override=True)

TABLES = [
    "locataires", "paiements", "maintenance_journal", "schema_migrations",
    "portail_locataire_tokens", "offline_sync_events", "archives_paiements",
    "demandes_paiement", "loyer_tarifs", "signatures_paiements", "sync_queue",
]
# L'ordre ci-dessus respecte les dependances de cles etrangeres (une table
# referencee doit etre chargee avant celle qui la reference).

SEQUENCE_TABLES = [
    "locataires", "paiements", "maintenance_journal", "portail_locataire_tokens",
    "demandes_paiement", "loyer_tarifs", "signatures_paiements", "archives_paiements",
]

# Colonnes json/jsonb par table : une chaine vide en SQLite n'est pas un JSON
# valide pour Postgres, on la convertit donc en NULL. Le texte JSON valide est
# transmis tel quel : Postgres le caste automatiquement vers json/jsonb.
JSON_COLUMNS: dict[str, tuple[str, ...]] = {
    "sync_queue": ("payload_json", "conflict_json"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, default=Path("app_data.db"))
    parser.add_argument("--dsn", default=os.getenv("SUPABASE_DB_URL"), required=not os.getenv("SUPABASE_DB_URL"))
    parser.add_argument("--schema", type=Path, default=Path(__file__).with_name("supabase_schema.sql"))
    return parser.parse_args()


def normalise_row(json_indexes: tuple[int, ...], row: tuple) -> tuple:
    if not json_indexes:
        return row
    values = list(row)
    for index in json_indexes:
        if values[index] == "":
            values[index] = None
    return tuple(values)


def load_table(source: sqlite3.Connection, target: psycopg.Connection, table: str) -> tuple[int, float]:
    """Copie une table SQLite vers Postgres via COPY + staging. Renvoie (nb lignes, secondes)."""
    started = time.perf_counter()
    cursor = source.execute(f'SELECT * FROM "{table}"')
    columns = [description[0] for description in cursor.description]
    json_indexes = tuple(columns.index(c) for c in JSON_COLUMNS.get(table, ()) if c in columns)

    staging = f"_staging_{table}"
    column_list = sql.SQL(", ").join(map(sql.Identifier, columns))
    count = 0

    with target.cursor() as target_cursor:
        target_cursor.execute(
            sql.SQL("CREATE TEMP TABLE {staging} (LIKE {table})").format(
                staging=sql.Identifier(staging), table=sql.Identifier(table),
            )
        )
        copy_stmt = sql.SQL("COPY {staging} ({columns}) FROM STDIN").format(
            staging=sql.Identifier(staging), columns=column_list,
        )
        with target_cursor.copy(copy_stmt) as copy:
            for row in cursor:  # streaming depuis SQLite, pas de fetchall()
                copy.write_row(normalise_row(json_indexes, row))
                count += 1

        if count:
            target_cursor.execute(
                sql.SQL(
                    "INSERT INTO {table} ({columns}) SELECT {columns} FROM {staging} ON CONFLICT DO NOTHING"
                ).format(table=sql.Identifier(table), columns=column_list, staging=sql.Identifier(staging))
            )
        target_cursor.execute(sql.SQL("DROP TABLE {staging}").format(staging=sql.Identifier(staging)))

    return count, time.perf_counter() - started


def reset_sequence(target: psycopg.Connection, table: str) -> None:
    target.execute(
        sql.SQL(
            "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) "
            "FROM {table}"
        ).format(table=sql.Identifier(table)),
        (table,),
    )


def main() -> int:
    args = parse_args()
    if not args.sqlite.exists():
        raise SystemExit(f"Fichier SQLite introuvable: {args.sqlite}")
    if not args.schema.exists():
        raise SystemExit(f"Fichier de schema introuvable: {args.schema}")

    total_started = time.perf_counter()
    with sqlite3.connect(args.sqlite) as source, psycopg.connect(args.dsn) as target:
        try:
            target.execute(args.schema.read_text(encoding="utf-8"))

            total_rows = 0
            for table in TABLES:
                count, elapsed = load_table(source, target, table)
                total_rows += count
                rate = f" ({count / elapsed:,.0f} lignes/s)" if elapsed > 0.05 and count else ""
                print(f"{table}: {count} ligne(s) en {elapsed:.2f}s{rate}")

            for table in SEQUENCE_TABLES:
                reset_sequence(target, table)
        except Exception:
            target.rollback()
            raise

        target.commit()

    print(f"Termine : {total_rows} ligne(s) au total en {time.perf_counter() - total_started:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())