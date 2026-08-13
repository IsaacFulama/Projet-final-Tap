from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class OfflineQueue:
    """File locale durable pour les actions créées sans MariaDB."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._ensure_schema()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS offline_queue (
                    event_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    conflict_json TEXT,
                    created_at TEXT NOT NULL,
                    synced_at TEXT
                )
                """
            )

    def enqueue(self, event_type: str, payload: dict[str, Any], device_id: str) -> str:
        event_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO offline_queue VALUES (?, ?, ?, ?, 'pending', NULL, ?, NULL)",
                (event_id, device_id, event_type, json.dumps(payload, ensure_ascii=False),
                 datetime.now(timezone.utc).isoformat()),
            )
        return event_id

    def pending(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM offline_queue WHERE status = 'pending' ORDER BY created_at"
            ).fetchall()
        return [self._decode(row) for row in rows]

    def mark_result(self, event_id: str, status: str, conflict: dict | None = None):
        if status not in {"synced", "conflict", "failed"}:
            raise ValueError("Statut de synchronisation invalide")
        with self._connect() as conn:
            conn.execute(
                "UPDATE offline_queue SET status = ?, conflict_json = ?, synced_at = ? WHERE event_id = ?",
                (status, json.dumps(conflict, ensure_ascii=False) if conflict else None,
                 datetime.now(timezone.utc).isoformat(), event_id),
            )

    @staticmethod
    def _decode(row) -> dict[str, Any]:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        if item.get("conflict_json"):
            item["conflict"] = json.loads(item["conflict_json"])
        item.pop("conflict_json", None)
        return item

