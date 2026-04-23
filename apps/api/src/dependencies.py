import logging
import os

import jwt
from fastapi import Header
from jwt import PyJWKClient

from .errors import UnauthorizedError

logger = logging.getLogger(__name__)

# Supabase issues either:
# - HS256 tokens signed with the legacy JWT secret, or
# - Asymmetric tokens (ES256, RS256, …) from JWT signing keys; public keys live at
#   {SUPABASE_URL}/auth/v1/.well-known/jwks.json
# See: https://supabase.com/docs/guides/auth/jwts

_jwks_client: PyJWKClient | None = None
_jwks_base_url: str | None = None


def _get_supabase_url() -> str:
    return (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")


def _get_jwt_secret() -> str:
    return (os.getenv("SUPABASE_JWT_SECRET") or "").strip()


def _jwks_client_for(url: str) -> PyJWKClient:
    global _jwks_client, _jwks_base_url
    if _jwks_client is None or _jwks_base_url != url:
        jwks_url = f"{url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(
            jwks_url, cache_jwk_set=True, max_cached_keys=16, lifespan=600.0
        )
        _jwks_base_url = url
        logger.debug("JWKS client bound to %s", jwks_url)
    return _jwks_client


def _decode_symmetric(token: str) -> dict:
    secret = _get_jwt_secret()
    if not secret:
        raise jwt.InvalidTokenError(
            "HS256 token but SUPABASE_JWT_SECRET is empty — add the JWT secret from "
            "Supabase (Project Settings > API) to the API .env"
        )
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )


def _decode_jwks(token: str) -> dict:
    base = _get_supabase_url()
    if not base:
        raise jwt.InvalidTokenError(
            "Asymmetric Supabase token but SUPABASE_URL is empty — set SUPABASE_URL in the API .env "
            "(same project as VITE_SUPABASE_URL) for JWKS verification"
        )
    try:
        header = jwt.get_unverified_header(token)
    except (jwt.exceptions.DecodeError, TypeError, ValueError, KeyError) as e:
        raise jwt.InvalidTokenError(f"Could not read JWT header: {e}") from e
    token_alg = (header or {}).get("alg")
    if not token_alg:
        raise jwt.InvalidTokenError("JWT header missing alg")
    client = _jwks_client_for(base)
    signing_key = client.get_signing_key_from_jwt(token)
    issuer = f"{base}/auth/v1"
    # Use the token's declared alg (must match algs PyJWT will accept). PyJWK's inferred
    # algorithm_name can disagree with the header and trigger "The specified alg value is not allowed".
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=[token_alg],
        issuer=issuer,
        options={"verify_aud": False, "verify_iss": True},
    )


def _decode_bearer_jwt(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.exceptions.DecodeError as e:
        raise jwt.InvalidTokenError(f"Malformed JWT: {e}") from e
    except (TypeError, ValueError, KeyError) as e:
        raise jwt.InvalidTokenError(f"Could not read JWT header: {e}") from e

    alg = (header or {}).get("alg") or ""

    # Symmetric (legacy shared secret)
    if alg == "HS256":
        return _decode_symmetric(token)

    # Asymmetric (ES256, RS256, …) must use JWKS — needs project URL, not the legacy secret alone
    if alg and alg != "HS256":
        if not _get_supabase_url():
            raise jwt.InvalidTokenError(
                f"Token uses {alg} — set SUPABASE_URL in the API .env to the same project as "
                "VITE_SUPABASE_URL (JWKS at …/auth/v1/.well-known/jwks.json). "
                "SUPABASE_JWT_SECRET alone is not used for asymmetric tokens."
            )
        return _decode_jwks(token)

    if _get_supabase_url():
        return _decode_jwks(token)

    if _get_jwt_secret():
        return _decode_symmetric(token)

    raise jwt.InvalidTokenError(
        "Set SUPABASE_URL (for JWKS) and/or SUPABASE_JWT_SECRET (for HS256) in the API .env — "
        "they must match the Supabase project used by the web app (VITE_SUPABASE_URL)."
    )


def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return _decode_bearer_jwt(token)
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedError("Token has expired") from e
    except jwt.InvalidTokenError as e:
        logger.warning("JWT validation failed: %s", e)
        raise UnauthorizedError(f"Invalid token: {e}") from e
