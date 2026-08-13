from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from mysql.connector import Error

from tap.core.local_signature import decode_signature_image
from tap.infrastructure.database.connection import obtenir_connexion
from tap.infrastructure.database.repository import (
    enregistrer_signature_et_mettre_a_jour_paiement,
)
from tap.mobile.security import generate_access_token, hash_access_token


def create_portal_token(locataire_id: int, days: int = 30) -> tuple[str, datetime]:
    """Crée un lien locataire dont la base ne conserve jamais le secret brut."""
    token = generate_access_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, min(days, 365)))
    conn = obtenir_connexion()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO portail_locataire_tokens
                (locataire_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (locataire_id, hash_access_token(token), expires_at.replace(tzinfo=None)),
        )
        conn.commit()
        return token, expires_at
    finally:
        cursor.close()
        conn.close()


def _resolve_token(token: str, cursor) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT t.id AS token_id, t.locataire_id, t.expires_at,
               l.nom, l.prenom, l.telephone
        FROM portail_locataire_tokens t
        JOIN locataires l ON l.id = t.locataire_id
        WHERE t.token_hash = %s
          AND t.revoked_at IS NULL
          AND t.expires_at > NOW()
        LIMIT 1
        """,
        (hash_access_token(token),),
    )
    row = cursor.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        return row
    keys = ("token_id", "locataire_id", "expires_at", "nom", "prenom", "telephone")
    return dict(zip(keys, row))


def get_portal_data(token: str) -> dict[str, Any] | None:
    conn = obtenir_connexion()
    cursor = conn.cursor(dictionary=True)
    try:
        tenant = _resolve_token(token, cursor)
        if not tenant:
            return None
        cursor.execute(
            """
            SELECT p.id, DATE_FORMAT(p.mois, '%%m/%%Y') AS mois,
                   p.montant_total, p.montant_paye, p.reste_a_payer,
                   p.devise, p.statut, p.statut_paiement,
                   EXISTS(SELECT 1 FROM signatures_paiements s
                          WHERE s.paiement_id = p.id) AS est_signe
            FROM paiements p
            WHERE p.locataire_id = %s
            ORDER BY p.mois DESC
            """,
            (tenant["locataire_id"],),
        )
        payments = cursor.fetchall()
        cursor.execute(
            "UPDATE portail_locataire_tokens SET last_used_at = NOW() WHERE id = %s",
            (tenant["token_id"],),
        )
        conn.commit()
        return {
            "tenant": {
                "id": tenant["locataire_id"],
                "nom": tenant["nom"],
                "prenom": tenant["prenom"],
                "telephone": tenant["telephone"],
            },
            "payments": payments,
        }
    finally:
        cursor.close()
        conn.close()


def sign_portal_payment(
    token: str,
    payment_id: int,
    signature_data_url: str,
    consent: bool,
    signer_ip: str,
    user_agent: str,
) -> tuple[bool, str]:
    if not consent:
        return False, "Consentement requis."
    signature_png = decode_signature_image(signature_data_url)
    conn = obtenir_connexion()
    cursor = conn.cursor(dictionary=True)
    try:
        tenant = _resolve_token(token, cursor)
        if not tenant:
            return False, "Lien locataire invalide ou expiré."
        cursor.execute(
            """
            SELECT p.id, p.locataire_id, p.mois, p.montant_total,
                   p.montant_paye, p.reste_a_payer, p.devise, p.statut,
                   p.statut_paiement, l.nom, l.prenom
            FROM paiements p JOIN locataires l ON l.id = p.locataire_id
            WHERE p.id = %s AND p.locataire_id = %s
            """,
            (payment_id, tenant["locataire_id"]),
        )
        payment = cursor.fetchone()
        if not payment:
            return False, "Paiement introuvable pour ce locataire."
        payload = {
            "paiement_id": payment["id"],
            "locataire_id": payment["locataire_id"],
            "nom": payment["nom"],
            "prenom": payment["prenom"],
            "signataire_nom": f"{payment['nom']} {payment['prenom']}",
            "mois": str(payment["mois"]),
            "montant_total": str(payment["montant_total"]),
            "montant_paye_signature": str(payment["montant_paye"]),
            "reste_a_payer": str(payment["reste_a_payer"]),
            "devise": payment["devise"],
        }
        from tap.core.local_signature import compute_document_hash

        ok, message = enregistrer_signature_et_mettre_a_jour_paiement(
            payload,
            compute_document_hash(payload),
            signature_png,
            signer_ip,
            user_agent,
        )
        return ok, message
    except (Error, ValueError) as exc:
        return False, str(exc)
    finally:
        cursor.close()
        conn.close()
