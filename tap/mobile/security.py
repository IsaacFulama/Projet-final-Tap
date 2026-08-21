from __future__ import annotations

import hashlib
import hmac
import os
import secrets


def _token_pepper() -> bytes:
    value = os.getenv("TAP_PORTAL_TOKEN_PEPPER", "").strip()
    if not value:
        raise RuntimeError(
            "TAP_PORTAL_TOKEN_PEPPER doit être configuré avant d'utiliser les tokens du portail."
        )
    return value.encode("utf-8")


def generate_access_token() -> str:
    return secrets.token_urlsafe(32)


def hash_access_token(token: str) -> str:
    return hmac.new(_token_pepper(), token.encode(), hashlib.sha256).hexdigest()


def tokens_match(raw_token: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_access_token(raw_token), stored_hash)

