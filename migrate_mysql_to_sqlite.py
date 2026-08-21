"""Exporte la base TAP MySQL/MariaDB vers une base SQLite locale.

Exemple:
    python migrate_mysql_to_sqlite.py --output app_data.db
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import mysql.connector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("app_data.db"))
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--database", default=os.getenv("MYSQL_DATABASE", "gestion_loyers"))
    parser.add_argument("--user", default=os.getenv("MYSQL_USER", "root"))
    parser.add_argument("--password", default=os.getenv("MYSQL_PASSWORD", ""))
    return parser.parse_args()


def sqlite_type(mysql_type: str) -> str:
    kind = mysql_type.lower().split("(", 1)[0]
    if kind in {"tinyint", "smallint", "mediumint", "int", "integer", "bigint", "bit"}:
        return "INTEGER"
    if kind in {"decimal", "numeric", "float", "double", "real"}:
        return "NUMERIC"
    if kind in {"blob", "tinyblob", "mediumblob", "longblob", "binary", "varbinary"}:
        return "BLOB"
    return "TEXT"


def sqlite_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def mysql_tables(source) -> list[str]:
    cursor = source.cursor()
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return tables


def create_table(source, target: sqlite3.Connection, table: str) -> list[str]:
    cursor = source.cursor(dictionary=True)
    cursor.execute(f"SHOW COLUMNS FROM `{table.replace('`', '``')}`")
    columns = cursor.fetchall()
    cursor.close()
    primary = [column["Field"] for column in columns if column["Key"] == "PRI"]
    definitions = []
    for column in columns:
        name = column["Field"].replace('"', '""')
        definition = f'"{name}" {sqlite_type(column["Type"])}'
        if column["Extra"] and "auto_increment" in column["Extra"] and primary == [column["Field"]]:
            definition = f'"{name}" INTEGER PRIMARY KEY AUTOINCREMENT'
        elif column["Field"] in primary:
            definition += " PRIMARY KEY"
        if column["Null"] == "NO" and column["Field"] not in primary:
            definition += " NOT NULL"
        if column["Default"] is not None and "auto_increment" not in column["Extra"]:
            default = column["Default"]
            if isinstance(default, str) and default.upper() in {"CURRENT_TIMESTAMP", "CURRENT_DATE"}:
                definition += f" DEFAULT {default.upper()}"
            else:
                escaped = str(default).replace("'", "''")
                definition += f" DEFAULT '{escaped}'"
        definitions.append(definition)

    cursor = source.cursor(dictionary=True)
    cursor.execute(
        "SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
        "FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL",
        (table,),
    )
    foreign_keys = cursor.fetchall()
    cursor.close()
    for key in foreign_keys:
        definitions.append(
            f'FOREIGN KEY ("{key["COLUMN_NAME"]}") REFERENCES '
            f'"{key["REFERENCED_TABLE_NAME"]}" ("{key["REFERENCED_COLUMN_NAME"]}") ON DELETE CASCADE'
        )
    target.execute(f'DROP TABLE IF EXISTS "{table.replace(chr(34), chr(34) * 2)}"')
    target.execute(f'CREATE TABLE "{table.replace(chr(34), chr(34) * 2)}" ({", ".join(definitions)})')
    return [column["Field"] for column in columns]


def copy_table(source, target: sqlite3.Connection, table: str, columns: list[str]) -> int:
    cursor = source.cursor()
    cursor.execute(f"SELECT * FROM `{table.replace('`', '``')}`")
    rows = cursor.fetchall()
    cursor.close()
    quoted_table = table.replace('"', '""')
    quoted_columns = ", ".join(f'"{column.replace(chr(34), chr(34) * 2)}"' for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    target.executemany(
        f'INSERT INTO "{quoted_table}" ({quoted_columns}) VALUES ({placeholders})',
        [tuple(sqlite_value(value) for value in row) for row in rows],
    )
    return len(rows)


def create_indexes(source, target: sqlite3.Connection, table: str) -> None:
    cursor = source.cursor(dictionary=True)
    cursor.execute(f"SHOW INDEX FROM `{table.replace('`', '``')}`")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in cursor.fetchall():
        if item["Key_name"] != "PRIMARY":
            grouped.setdefault(item["Key_name"], []).append(item)
    cursor.close()
    for index_name, items in grouped.items():
        items.sort(key=lambda item: item["Seq_in_index"])
        quoted_name = index_name.replace('"', '""')
        quoted_table = table.replace('"', '""')
        quoted_columns = ", ".join(
            f'"{item["Column_name"].replace(chr(34), chr(34) * 2)}"' for item in items
        )
        unique = "UNIQUE " if items[0]["Non_unique"] == 0 else ""
        target.execute(
            f'CREATE {unique}INDEX IF NOT EXISTS "{quoted_name}" '
            f'ON "{quoted_table}" ({quoted_columns})'
        )


def ensure_sync_queue(target: sqlite3.Connection) -> None:
    target.execute(
        """CREATE TABLE IF NOT EXISTS sync_queue (
            event_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            conflict_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            synced_at TEXT
        )"""
    )
    target.execute("CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(status)")


def main() -> int:
    args = parse_args()
    source = mysql.connector.connect(
        host=args.host, port=args.port, database=args.database,
        user=args.user, password=args.password,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    target = sqlite3.connect(args.output)
    target.execute("PRAGMA foreign_keys = OFF")
    try:
        tables = mysql_tables(source)
        ordered = sorted(tables, key=lambda name: name == "paiements")
        definitions = {table: create_table(source, target, table) for table in ordered}
        total = sum(copy_table(source, target, table, columns) for table, columns in definitions.items())
        for table in ordered:
            create_indexes(source, target, table)
        ensure_sync_queue(target)
        target.commit()
        print(f"Migration terminee: {total} lignes vers {args.output}")
    finally:
        target.close()
        source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())