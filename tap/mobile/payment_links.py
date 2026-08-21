from __future__ import annotations

import base64
import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterator

from mysql.connector import Error

from tap.core.local_signature import compute_document_hash, decode_signature_image
from tap.infrastructure.database.connection import (
    MESSAGE_BASE_INDISPONIBLE,
    connexion_prete,
    obtenir_connexion,
)
from tap.infrastructure.database.repository import (
    enregistrer_signature_et_mettre_a_jour_paiement,
)
from tap.mobile.security import generate_access_token, hash_access_token

MAX_PROOF_BYTES = 2 * 1024 * 1024
ALLOWED_PROOF_MIMES = {"image/png", "image/jpeg", "application/pdf"}
PROOF_SIGNATURES = {"image/png": (b"\x89PNG\r\n\x1a\n",), "image/jpeg": (b"\xff\xd8\xff",), "application/pdf": (b"%PDF-",)}

def _connexion_ou_erreur():
    conn = obtenir_connexion()
    if not connexion_prete(conn):
        raise ValueError(MESSAGE_BASE_INDISPONIBLE)
    return conn

def create_payment_link(payment_id: int, days: int = 7) -> tuple[str, datetime, Decimal, str]:
    token = generate_access_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, min(days, 30)))
    conn = _connexion_ou_erreur()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT montant_total, montant_paye, devise FROM paiements WHERE id = %s", (payment_id,))
        payment = cursor.fetchone()
        if not payment:
            raise ValueError("Paiement introuvable.")
        remaining = max(Decimal("0"), Decimal(str(payment.get("montant_total") or 0)) - Decimal(str(payment.get("montant_paye") or 0)))
        if remaining <= 0:
            raise ValueError("Ce paiement est déjà soldé.")
        cursor.execute("""INSERT INTO demandes_paiement (paiement_id, token_hash, montant_demande, devise, expires_at)
            VALUES (%s, %s, %s, %s, %s)""", (payment_id, hash_access_token(token), remaining, payment["devise"], expires_at.replace(tzinfo=None)))
        conn.commit()
        return token, expires_at, remaining, str(payment["devise"])
    finally:
        cursor.close(); conn.close()

def _resolve_link(token: str, cursor) -> dict[str, Any] | None:
    cursor.execute("""SELECT d.id, d.paiement_id AS payment_id, d.montant_demande, d.devise, d.expires_at,
        d.statut, d.note_locataire, p.mois, l.nom, l.prenom FROM demandes_paiement d
        JOIN paiements p ON p.id=d.paiement_id JOIN locataires l ON l.id=p.locataire_id
        WHERE d.token_hash=%s AND d.expires_at>NOW() AND d.statut IN ('pending','proof_submitted') LIMIT 1""", (hash_access_token(token),))
    return cursor.fetchone()

def get_payment_link(token: str) -> dict[str, Any] | None:
    conn = _connexion_ou_erreur(); cursor = conn.cursor(dictionary=True)
    try:
        row = _resolve_link(token, cursor)
        return dict(row) if row else None
    finally:
        cursor.close(); conn.close()

def _decode_proof(data_url: str) -> tuple[bytes, str]:
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        raise ValueError("La preuve doit être une image PNG/JPEG ou un PDF.")
    header, separator, encoded = data_url.partition(",")
    if not separator or ";base64" not in header:
        raise ValueError("Format de preuve invalide.")
    mime = header[5:].split(";", 1)[0].lower()
    if mime not in ALLOWED_PROOF_MIMES:
        raise ValueError("Format accepté : PNG, JPEG ou PDF.")
    try: data = base64.b64decode(encoded, validate=True)
    except Exception as exc: raise ValueError("La preuve est illisible.") from exc
    if not data or len(data) > MAX_PROOF_BYTES or not any(data.startswith(s) for s in PROOF_SIGNATURES[mime]):
        raise ValueError("Le contenu du fichier ne correspond pas à son format déclaré.")
    return data, mime

def inspect_proof(data: bytes, mime: str) -> dict[str, str | int]:
    if mime not in ALLOWED_PROOF_MIMES or not data or len(data) > MAX_PROOF_BYTES or not any(data.startswith(s) for s in PROOF_SIGNATURES[mime]):
        raise ValueError("Signature binaire incohérente avec le type MIME.")
    return {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data), "mime": mime}

def submit_payment_proof(token: str, proof_data_url: str, note: str = "") -> tuple[bool, str]:
    proof_data, mime = _decode_proof(proof_data_url); audit = inspect_proof(proof_data, mime)
    conn = _connexion_ou_erreur(); cursor = conn.cursor(dictionary=True)
    try:
        link = _resolve_link(token, cursor)
        if not link: return False, "Lien invalide, expiré ou déjà traité."
        cursor.execute("""UPDATE demandes_paiement SET statut='proof_submitted', preuve_data=%s, preuve_mime=%s,
            preuve_sha256=%s, verification_status='pending_review', note_locataire=%s, soumis_at=NOW()
            WHERE id=%s AND statut='pending'""", (proof_data, mime, audit["sha256"], str(note or "")[:500], link["id"]))
        if cursor.rowcount != 1:
            conn.rollback(); return False, "Cette demande a déjà été envoyée."
        conn.commit(); return True, "Preuve envoyée. Elle sera vérifiée par le gestionnaire."
    finally: cursor.close(); conn.close()


def list_pending_payment_proofs() -> list[dict[str, Any]]:
    conn = _connexion_ou_erreur(); cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""SELECT d.id, d.paiement_id AS payment_id, d.montant_demande, d.devise,
            d.note_locataire, d.soumis_at, d.preuve_mime, d.preuve_sha256,
            d.verification_status, p.mois, l.nom, l.prenom
            FROM demandes_paiement d JOIN paiements p ON p.id=d.paiement_id
            JOIN locataires l ON l.id=p.locataire_id WHERE d.statut='proof_submitted'
            ORDER BY d.soumis_at ASC, d.id ASC""")
        return cursor.fetchall()
    finally: cursor.close(); conn.close()


def read_payment_proof(proof_id: int) -> tuple[bytes, str] | None:
    conn = _connexion_ou_erreur(); cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT preuve_data, preuve_mime FROM demandes_paiement WHERE id=%s", (proof_id,))
        row = cursor.fetchone()
        return (bytes(row["preuve_data"]), str(row["preuve_mime"] or "application/octet-stream")) if row and row["preuve_data"] else None
    finally: cursor.close(); conn.close()


def review_payment_proof(proof_id: int, approve: bool, note: str = "") -> tuple[bool, str]:
    conn = _connexion_ou_erreur(); cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT paiement_id AS payment_id, montant_demande, statut FROM demandes_paiement WHERE id=%s FOR UPDATE", (proof_id,))
        row = cursor.fetchone()
        if not row or row["statut"] != "proof_submitted": return False, "Cette preuve n'est plus en attente."
        if not approve:
            cursor.execute("UPDATE demandes_paiement SET statut='rejected', verification_status='rejected', traite_at=NOW(), note_traitement=%s WHERE id=%s", (str(note or "")[:500], proof_id))
            conn.commit(); return True, "Preuve refusée."
        cursor.execute("UPDATE demandes_paiement SET statut='processing' WHERE id=%s AND statut='proof_submitted'", (proof_id,))
        conn.commit()
    finally: cursor.close(); conn.close()
    from tap.infrastructure.database.repository import ajouter_paiement_complementaire
    ok, message = ajouter_paiement_complementaire(int(row["payment_id"]), Decimal(str(row["montant_demande"])))
    conn = _connexion_ou_erreur(); cursor = conn.cursor()
    try:
        cursor.execute("UPDATE demandes_paiement SET statut=%s, verification_status=%s, traite_at=NOW(), note_traitement=%s WHERE id=%s", ("approved" if ok else "proof_submitted", "approved" if ok else "pending_review", str(note or message)[:500], proof_id))
        conn.commit()
    finally: cursor.close(); conn.close()
    return ok, message if ok else f"Paiement non validé : {message}"


@contextmanager
def _portal_cursor(dictionary: bool = True) -> Iterator[tuple[Any, Any]]:
    """Ouvre une connexion + curseur et garantit leur fermeture, meme si
    l'ouverture du curseur elle-meme echoue.

    Leve ValueError(MESSAGE_BASE_INDISPONIBLE) si la base est indisponible ;
    charge aux appelants de decider s'ils traduisent ca en None, en tuple
    (False, message), etc.
    """
    conn = obtenir_connexion()
    if not connexion_prete(conn):
        raise ValueError(MESSAGE_BASE_INDISPONIBLE)
    try:
        cursor = conn.cursor(dictionary=dictionary)
        try:
            yield cursor, conn
        finally:
            cursor.close()
    finally:
        conn.close()


def create_portal_token(locataire_id: int, days: int = 30) -> tuple[str, datetime]:
    """Cree un lien locataire dont la base ne conserve jamais le secret brut."""
    token = generate_access_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, min(days, 365)))
    with _portal_cursor(dictionary=False) as (cursor, conn):
        cursor.execute(
            """
            INSERT INTO portail_locataire_tokens
                (locataire_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            # Stocke en naif : la colonne DATETIME n'a pas de fuseau, on
            # convient donc que toute valeur stockee ici est en UTC.
            (locataire_id, hash_access_token(token), expires_at.replace(tzinfo=None)),
        )
        conn.commit()
    return token, expires_at


def _resolve_token(token: str, cursor: Any) -> dict[str, Any] | None:
    """Retrouve le locataire associe a un token, si valide et non expire.

    Suppose un curseur dictionary=True (seul mode utilise par les appelants
    de ce module) : chaque ligne revient donc deja sous forme de dict.
    """
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
    return cursor.fetchone()


def get_portal_data(token: str) -> dict[str, Any] | None:
    try:
        with _portal_cursor(dictionary=True) as (cursor, conn):
            tenant = _resolve_token(token, cursor)
            if not tenant:
                return None
            cursor.execute(
                """
                SELECT p.id, DATE_FORMAT(p.mois, '%m/%Y') AS mois,
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
    except ValueError:
        # Base indisponible : traite comme "token invalide" du point de vue
        # de l'appelant, qui n'a de toute facon rien de plus a faire ici.
        return None


def _parse_decimal_filter(raw: str) -> float | None:
    """Convertit un filtre de montant saisi par l'utilisateur.

    Renvoie None si le champ est vide OU si la valeur n'est pas un nombre
    valide, pour que le filtre soit simplement ignore plutot que de faire
    planter la requete sur une entree malformee.
    """
    raw = raw.strip()
    if not raw:
        return None
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def get_portal_payments(
    token: str,
    *,
    search: str = "",
    status: str = "",
    date_from: str = "",
    date_to: str = "",
    amount_min: str = "",
    amount_max: str = "",
    payment_id: int | None = None,
) -> dict[str, Any] | None:
    """Retourne l'historique ou le detail, toujours limite au locataire du token."""
    try:
        with _portal_cursor(dictionary=True) as (cursor, _conn):
            tenant = _resolve_token(token, cursor)
            if not tenant:
                return None

            clauses: list[str] = ["p.locataire_id = %s"]
            params: list[Any] = [tenant["locataire_id"]]

            if payment_id is not None:
                clauses.append("p.id = %s")
                params.append(payment_id)

            if search.strip():
                clauses.append(
                    "(CAST(p.id AS CHAR) LIKE %s OR CONCAT('PAI-', p.id) LIKE %s "
                    "OR CONCAT('Loyer ', DATE_FORMAT(p.mois, '%m/%Y')) LIKE %s "
                    "OR p.devise LIKE %s OR p.statut LIKE %s)"
                )
                term = f"%{search.strip()}%"
                params.extend([term] * 5)

            if status.strip():
                clauses.append("p.statut_paiement = %s")
                params.append(status.strip())

            if date_from.strip():
                clauses.append("p.mois >= %s")
                params.append(date_from.strip())

            if date_to.strip():
                clauses.append("p.mois <= %s")
                params.append(date_to.strip())

            amount_min_value = _parse_decimal_filter(amount_min)
            if amount_min_value is not None:
                clauses.append("p.montant_total >= %s")
                params.append(amount_min_value)

            amount_max_value = _parse_decimal_filter(amount_max)
            if amount_max_value is not None:
                clauses.append("p.montant_total <= %s")
                params.append(amount_max_value)

            where_sql = " AND ".join(clauses)
            cursor.execute(
                f"""
                SELECT p.id, p.mois, p.montant_total, p.montant_paye, p.reste_a_payer,
                       p.devise, p.statut, p.statut_paiement,
                       COALESCE(p.statut_paiement, p.statut, 'En attente') AS statut_affiche,
                       CONCAT('PAI-', p.id) AS reference,
                       CONCAT('Loyer ', DATE_FORMAT(p.mois, '%m/%Y')) AS prestation,
                       'Non renseignée' AS methode_paiement,
                       EXISTS(SELECT 1 FROM signatures_paiements s WHERE s.paiement_id = p.id) AS est_signe
                FROM paiements p
                WHERE {where_sql}
                ORDER BY p.mois DESC, p.id DESC
                """,
                tuple(params),
            )
            return {"tenant": tenant, "payments": cursor.fetchall()}
    except ValueError:
        return None


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
    try:
        signature_png = decode_signature_image(signature_data_url)
        with _portal_cursor(dictionary=True) as (cursor, _conn):
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
            return enregistrer_signature_et_mettre_a_jour_paiement(
                payload,
                compute_document_hash(payload),
                signature_png,
                signer_ip,
                user_agent,
            )
    except (Error, ValueError) as exc:
        return False, str(exc)
