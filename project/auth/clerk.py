"""
Clerk JWT verification and signed session cookie helpers.

Environment variables required:
  CLERK_JWKS_URL       — e.g. https://<frontend-api>.clerk.accounts.dev/.well-known/jwks.json
  SESSION_SECRET_KEY   — random secret used to sign the rag_uid cookie
"""

import json
import os
import time

import httpx
import jwt
from itsdangerous import URLSafeSerializer, BadSignature

# ── JWKS caching ─────────────────────────────────────────────────────────────

_jwks_cache: dict = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600  # refresh keys every hour


def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache
    url = os.environ.get("CLERK_JWKS_URL", "")
    if not url:
        raise RuntimeError("CLERK_JWKS_URL is not set")
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    _jwks_cache = resp.json()
    _jwks_fetched_at = now
    return _jwks_cache


def verify_clerk_token(token: str) -> dict:
    """Verify a Clerk-issued JWT. Returns the decoded payload on success."""
    from jwt.algorithms import RSAAlgorithm

    jwks = _get_jwks()
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")

    key_data = next(
        (k for k in jwks.get("keys", []) if k.get("kid") == kid), None
    )
    if not key_data:
        raise ValueError(f"No JWKS key matching kid={kid!r}")

    public_key = RSAAlgorithm.from_jwk(json.dumps(key_data))
    payload = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )
    return payload


# ── Signed cookie helpers ─────────────────────────────────────────────────────

def _signer() -> URLSafeSerializer:
    secret = os.environ.get("SESSION_SECRET_KEY", "change-me-in-production")
    return URLSafeSerializer(secret, salt="rag-uid")


def make_session_cookie(user_id: str, email: str = "") -> str:
    """Return a signed value to store in the rag_uid cookie."""
    return _signer().dumps({"uid": user_id, "email": email})


def read_session_cookie(raw: str) -> dict | None:
    """
    Verify and decode the rag_uid cookie value.
    Returns {"uid": ..., "email": ...} or None if invalid/missing.
    """
    if not raw:
        return None
    try:
        return _signer().loads(raw)
    except BadSignature:
        return None


def get_user_id(cookies: dict) -> str | None:
    """Convenience: extract user_id from a cookies dict."""
    data = read_session_cookie(cookies.get("rag_uid", ""))
    return data.get("uid") if data else None


def get_user_info(cookies: dict) -> dict:
    """Return {"uid": ..., "email": ...} or {} if no valid session."""
    data = read_session_cookie(cookies.get("rag_uid", ""))
    if not data:
        return {}
    return {"uid": data.get("uid", ""), "email": data.get("email", "")}
