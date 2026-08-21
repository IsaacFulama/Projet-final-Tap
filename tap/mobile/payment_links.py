"""Liens de paiement sans frais : demande, preuve et validation manuelle."""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from tap.infrastructure.database.connection import (
    MESSAGE_BASE_INDISPONIBLE,
    connexion_prete,
    obtenir_connexion,
)
from tap.infrastructure.database.repository import ajouter_paiement_complementaire
from tap.mobile.security import generate_access_token, hash_access_token

MAX_PROOF_BYTES = 2 * 1024 * 1024
ALLOWED_PROOF_MIMES = {"image/png", "image/jpeg", "application/pdf"}
PROOF_SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "application/pdf": (b"%PDF-",),
}


def _connexion_ou_erreur():
    conn = obtenir_connexion()
    if not connexion_prete(conn):
        raise ValueError(MESSAGE_BASE_INDISPONIBLE)
    return conn


def create_payment_link(payment_id: int, days: int = 7) -> tuple[str, datetime, Decimal, str]:
    """Crée un lien temporaire pour le reste à payer d'une ligne."""
    token = generate_access_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, min(days, 30)))
    conn = _connexion_ou_erreur()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT montant_total, montant_paye, reste_a_payer, devise
            FROM paiements WHERE id = %s
            """,
            (payment_id,),
        )
        payment = cursor.fetchone()
        if not payment:
            raise ValueError("Paiement introuvable.")
        total = Decimal(str(payment.get("montant_total") or 0))
        paid = Decimal(str(payment.get("montant_paye") or 0))
        remaining = max(Decimal("0"), total - paid)
        if remaining <= 0:
            raise ValueError("Ce paiement est déjà soldé.")
        cursor.execute(
            """
            INSERT INTO demandes_paiement
                (paiement_id, token_hash, montant_demande, devise, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                payment_id,
                hash_access_token(token),
                remaining,
                payment["devise"],
                expires_at.replace(tzinfo=None),
            ),
        )
        conn.commit()
        return token, expires_at, remaining, str(payment["devise"])
    finally:
        cursor.close()
        conn.close()


def _resolve_link(token: str, cursor) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT d.id, d.paiement_id AS payment_id, d.montant_demande, d.devise,
               d.expires_at, d.statut, d.note_locataire,
               p.mois, l.nom, l.prenom
        FROM demandes_paiement d
        JOIN paiements p ON p.id = d.paiement_id
        JOIN locataires l ON l.id = p.locataire_id
        WHERE d.token_hash = %s AND d.expires_at > NOW()
          AND d.statut IN ('pending', 'proof_submitted')
        LIMIT 1
        """,
        (hash_access_token(token),),
    )
    return cursor.fetchone()


def get_payment_link(token: str) -> dict[str, Any] | None:
    conn = _connexion_ou_erreur()
    cursor = conn.cursor(dictionary=True)
    try:
        row = _resolve_link(token, cursor)
        if not row:
            return None
        return dict(row)
    finally:
        cursor.close()
        conn.close()


def _decode_proof(data_url: str) -> tuple[bytes, str]:
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        raise ValueError("La preuve doit être une image PNG/JPEG ou un PDF.")
    header, separator, encoded = data_url.partition(",")
    if not separator or ";base64" not in header:
        raise ValueError("Format de preuve invalide.")
    mime = header[5:].split(";", 1)[0].lower()
    if mime not in ALLOWED_PROOF_MIMES:
        raise ValueError("Format accepté : PNG, JPEG ou PDF.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("La preuve est illisible.") from exc
    if not data or len(data) > MAX_PROOF_BYTES:
        raise ValueError("La preuve doit peser au maximum 2 Mo.")
    if not any(data.startswith(signature) for signature in PROOF_SIGNATURES[mime]):
        raise ValueError("Le contenu du fichier ne correspond pas à son format déclaré.")
    return data, mime


def inspect_proof(data: bytes, mime: str) -> dict[str, str | int]:
    """Retourne les éléments d'audit avant validation humaine."""
    if mime not in ALLOWED_PROOF_MIMES or not data:
        raise ValueError("Preuve vide ou format non autorisé.")
    if len(data) > MAX_PROOF_BYTES:
        raise ValueError("La preuve dépasse 2 Mo.")
    if not any(data.startswith(signature) for signature in PROOF_SIGNATURES[mime]):
        raise ValueError("Signature binaire incohérente avec le type MIME.")
    return {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data), "mime": mime}


def submit_payment_proof(token: str, proof_data_url: str, note: str = "") -> tuple[bool, str]:
    proof_data, mime = _decode_proof(proof_data_url)
    audit = inspect_proof(proof_data, mime)
    conn = _connexion_ou_erreur()
    cursor = conn.cursor(dictionary=True)
    try:
        link = _resolve_link(token, cursor)
        if not link:
            return False, "Lien invalide, expiré ou déjà traité."
        cursor.execute(
            """
            UPDATE demandes_paiement
            SET statut = 'proof_submitted', preuve_data = %s, preuve_mime = %s,
                preuve_sha256 = %s, verification_status = 'pending_review',
                note_locataire = %s, soumis_at = NOW()
            WHERE id = %s AND statut = 'pending'
            """,
            (proof_data, mime, audit["sha256"], str(note or "")[:500], link["id"]),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return False, "Cette demande a déjà été envoyée."
        conn.commit()
        return True, "Preuve envoyée. Elle sera vérifiée par le gestionnaire."
    finally:
        cursor.close()
        conn.close()


def list_pending_payment_proofs() -> list[dict[str, Any]]:
    conn = _connexion_ou_erreur()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT d.id, d.paiement_id AS payment_id, d.montant_demande, d.devise,
                   d.note_locataire, d.soumis_at, d.preuve_mime,
                   d.preuve_sha256, d.verification_status,
                   p.mois, l.nom, l.prenom
            FROM demandes_paiement d
            JOIN paiements p ON p.id = d.paiement_id
            JOIN locataires l ON l.id = p.locataire_id
            WHERE d.statut = 'proof_submitted'
            ORDER BY d.soumis_at ASC, d.id ASC
            """
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def read_payment_proof(proof_id: int) -> tuple[bytes, str] | None:
    conn = _connexion_ou_erreur()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT preuve_data, preuve_mime FROM demandes_paiement WHERE id = %s",
            (proof_id,),
        )
        row = cursor.fetchone()
        if not row or not row["preuve_data"]:
            return None
        return bytes(row["preuve_data"]), str(row["preuve_mime"] or "application/octet-stream")
    finally:
        cursor.close()
        conn.close()


def review_payment_proof(proof_id: int, approve: bool, note: str = "") -> tuple[bool, str]:
    conn = _connexion_ou_erreur()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT paiement_id AS payment_id, montant_demande, statut FROM demandes_paiement WHERE id = %s FOR UPDATE",
            (proof_id,),
        )
        row = cursor.fetchone()
        if not row or row["statut"] != "proof_submitted":
            return False, "Cette preuve n'est plus en attente."
        if not approve:
            cursor.execute(
                "UPDATE demandes_paiement SET statut='rejected', verification_status='rejected', traite_at=NOW(), note_traitement=%s WHERE id=%s",
                (str(note or "")[:500], proof_id),
            )
            conn.commit()
            return True, "Preuve refusée."
        # Verrou logique avant l'appel métier : un double clic ne peut pas
        # créditer deux fois la même preuve.
        cursor.execute(
            "UPDATE demandes_paiement SET statut='processing' WHERE id=%s AND statut='proof_submitted'",
            (proof_id,),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    ok, message = ajouter_paiement_complementaire(
        int(row["payment_id"]), Decimal(str(row["montant_demande"]))
    )
    conn = _connexion_ou_erreur()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE demandes_paiement SET statut=%s, verification_status=%s, traite_at=NOW(), note_traitement=%s WHERE id=%s",
            ("approved" if ok else "proof_submitted", "approved" if ok else "pending_review", str(note or message)[:500], proof_id),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return ok, message if ok else f"Paiement non validé : {message}"
