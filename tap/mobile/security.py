"""Génération et vérification des tokens d'accès au portail locataire.

Le token brut n'est jamais stocké : seule sa signature HMAC-SHA256, calculée
avec un secret applicatif (le "pepper"), l'est. Un pepper — contrairement à
un sel — est un secret unique partagé par tous les tokens, gardé hors de la
base de données ; il fait qu'un dump de la base seule ne suffit pas à
retrouver un token valide, même si l'attaquant connaît l'algorithme.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

# Un pepper plus court que le token qu'il protège (256 bits, cf.
# generate_access_token) en deviendrait le maillon faible.
_MIN_PEPPER_LENGTH = 32

# Un token legitime issu de generate_access_token() fait ~43 caracteres.
# 512 laisse une marge tres large tout en rejetant une chaine invraisemblable
# (ex. entree malveillante envoyee sur une route publique du portail) avant
# de depenser du CPU a la hacher.
_MAX_TOKEN_LENGTH = 512

__all__ = ["generate_access_token", "hash_access_token", "tokens_match"]


def _token_pepper() -> bytes:
    """Charge le pepper HMAC depuis l'environnement.

    Relu à chaque appel (pas de cache) : le coût d'un getenv() est
    négligeable, et ça évite un pepper resté en mémoire après une rotation
    du secret ou lors de tests qui le repositionnent.
    """
    value = os.getenv("TAP_PORTAL_TOKEN_PEPPER", "").strip()
    if not value:
        raise RuntimeError(
            "TAP_PORTAL_TOKEN_PEPPER doit être configuré avant d'utiliser les tokens du portail."
        )
    if len(value) < _MIN_PEPPER_LENGTH:
        raise RuntimeError(
            f"TAP_PORTAL_TOKEN_PEPPER est trop court ({len(value)} caractère(s), "
            f"{_MIN_PEPPER_LENGTH} minimum) : un pepper faible affaiblit tous les tokens du portail."
        )
    return value.encode("utf-8")


def generate_access_token() -> str:
    """Génère un token d'accès aléatoire cryptographiquement sûr (256 bits d'entropie)."""
    return secrets.token_urlsafe(32)


def hash_access_token(token: str) -> str:
    """Calcule le HMAC-SHA256 (hex) d'un token, avec le pepper applicatif comme clé.

    Lève ValueError sur une entrée de forme invalide : un appelant qui passe
    un type incorrect ou une chaîne vide/absurdement longue a un bug, pas un
    cas métier à absorber silencieusement.
    """
    if not isinstance(token, str) or not token or len(token) > _MAX_TOKEN_LENGTH:
        raise ValueError("token doit être une chaîne non vide et de longueur raisonnable.")
    return hmac.new(_token_pepper(), token.encode("utf-8"), hashlib.sha256).hexdigest()


def tokens_match(raw_token: str, stored_hash: str) -> bool:
    """Compare un token brut à un hash stocké, en temps constant.

    raw_token invalide (mauvais type, vide, trop long) fait lever ValueError,
    comme dans hash_access_token : c'est un bug appelant.
    stored_hash invalide (None, vide, mauvais type) renvoie False plutôt que
    de lever : cette valeur vient typiquement d'un enregistrement en base
    (token révoqué, ligne absente, colonne NULL), et le comportement sûr par
    défaut pour du contrôle d'accès est de refuser plutôt que de planter.
    """
    if not isinstance(stored_hash, str) or not stored_hash:
        return False
    return hmac.compare_digest(hash_access_token(raw_token), stored_hash)