from __future__ import annotations

import hashlib
import hmac
import os
import secrets


def generate_access_token() -> str:
    return secrets.token_urlsafe(32)


def hash_access_token(token: str) -> str:
    secret = os.getenv("TAP_PORTAL_TOKEN_PEPPER", "tap-change-this-pepper").encode()
    return hmac.new(secret, token.encode(), hashlib.sha256).hexdigest()


def tokens_match(raw_token: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_access_token(raw_token), stored_hash)

