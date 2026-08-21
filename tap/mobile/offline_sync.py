from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from mysql.connector import Error

from tap.infrastructure.database.connection import (
    MESSAGE_BASE_INDISPONIBLE,
    connexion_prete,
    obtenir_connexion,
)
from tap.infrastructure.database.repository import _statuts_montant


def apply_sync_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for event in events:
        event_id = str(event.get("event_id", ""))
        if not event_id or not event.get("event_type"):
            results.append({"event_id": event_id, "status": "failed", "message": "Événement invalide."})
            continue
        results.append(_apply_one(event))
    return results


def _apply_one(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event["event_id"])
    payload = event.get("payload") or {}
    conn = None
    cursor = None
    try:
        conn = obtenir_connexion()
        if not connexion_prete(conn):
            return {"event_id": event_id, "status": "failed", "message": MESSAGE_BASE_INDISPONIBLE}
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT status FROM offline_sync_events WHERE event_id = %s", (event_id,))
        existing = cursor.fetchone()
        if existing and existing["status"] == "synced":
            return {"event_id": event_id, "status": "synced", "idempotent": True}
        if event["event_type"] != "record_payment":
            return _record_result(conn, cursor, event, "failed", "Type d'événement non supporté.")
        payment_id = int(payload["payment_id"])
        amount = Decimal(str(payload["amount"]))
        cursor.execute(
            "SELECT statut_souscription, montant_total, montant_paye FROM paiements WHERE id = %s FOR UPDATE",
            (payment_id,),
        )
        row = cursor.fetchone()
        if not row:
            return _record_result(conn, cursor, event, "conflict", "Paiement introuvable.")
        if row["statut_souscription"] == "Spécial":
            return _record_result(conn, cursor, event, "conflict", "Les paiements spéciaux doivent être synchronisés depuis le desktop.")
        base_paid = Decimal(str(payload.get("base_paid", row["montant_paye"])))
        current_paid = Decimal(str(row["montant_paye"]))
        if abs(current_paid - base_paid) > Decimal("0.01"):
            return _record_result(conn, cursor, event, "conflict", "Le paiement a changé sur le serveur.")
        total = Decimal(str(row["montant_total"]))
        new_paid = current_paid + amount
        status, payment_status, remaining = _statuts_montant(total, new_paid)
        cursor.execute(
            "UPDATE paiements SET montant_paye=%s, reste_a_payer=%s, statut=%s, statut_paiement=%s WHERE id=%s",
            (float(new_paid), float(remaining), status, payment_status, payment_id),
        )
        return _record_result(conn, cursor, event, "synced", "Paiement synchronisé.")
    except (Error, ValueError, KeyError) as exc:
        return {"event_id": event_id, "status": "failed", "message": str(exc)}
    finally:
        if cursor is not None:
            cursor.close()
        if connexion_prete(conn):
            conn.close()


def _record_result(conn, cursor, event, status: str, message: str) -> dict[str, Any]:
    cursor.execute(
        """
        INSERT INTO offline_sync_events
            (event_id, device_id, event_type, payload_json, status, conflict_json)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE status = VALUES(status), conflict_json = VALUES(conflict_json), synced_at = NOW()
        """,
        (str(event["event_id"]), str(event.get("device_id", "")), str(event["event_type"]),
         json.dumps(event.get("payload", {}), ensure_ascii=False), status,
         message if status == "conflict" else None),
    )
    conn.commit()
    return {"event_id": str(event["event_id"]), "status": status, "message": message}
