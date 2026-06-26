"""
security.py — Phase 3 security layer.

Provides:
- SecurityHeadersMiddleware  : adds hardened HTTP headers to every response
- get_allowed_origins()     : builds CORS origin list from ALLOWED_ORIGINS env var
- RateLimits                : named limit strings for use with slowapi decorators
- sanitize_gp_name()        : strips characters that could cause path traversal or injection
- validate_session_type()   : enforces strict session type enum
- load_env()                : loads .env file if present (dev convenience)
"""

import os
import re
from typing import List

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Load .env file (no-op in production where env vars are injected directly)
# ---------------------------------------------------------------------------

def load_env() -> None:
    """Load .env file if python-dotenv is available and file exists."""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            print("[security] Loaded .env file")
    except ImportError:
        pass  # python-dotenv not installed — fine in production


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

_DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]


def get_allowed_origins() -> List[str]:
    """
    Build the CORS allowed-origins list.

    In production set: ALLOWED_ORIGINS=https://yourapp.netlify.app,https://custom.domain.com
    In development the env var is usually absent — falls back to localhost.
    Set ALLOWED_ORIGINS=* to allow all (not recommended in production).
    """
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    if not raw:
        # No env var — development mode, allow localhost
        return _DEFAULT_DEV_ORIGINS
    if raw == "*":
        return ["*"]
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return origins if origins else _DEFAULT_DEV_ORIGINS


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security-hardening HTTP headers to every response.
    Does NOT add HSTS on localhost to avoid breaking local dev.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        host = request.headers.get("host", "")
        is_local = host.startswith("localhost") or host.startswith("127.")

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Block clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Legacy XSS filter (belt-and-braces)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Strict referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissions policy — deny all unused browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        # Remove server fingerprint header if uvicorn set it
        response.headers.pop("server", None)

        # HSTS — only on real HTTPS, not localhost
        if not is_local:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


# ---------------------------------------------------------------------------
# Rate limit strings (used as @limiter.limit("...") arguments)
# ---------------------------------------------------------------------------

class RateLimits:
    # Fast, no-cost endpoints
    HEALTH   = "120/minute"
    METADATA = "60/minute"    # /years, /schedule, /practice-status

    # Moderate cost — model inference
    PREDICT  = "20/minute"    # /winner-probabilities, /predict-winner

    # Expensive — FastF1 session load (cached after first call)
    TIMING   = "6/minute"     # /timing, /race-control, /timing-drivers

    # Very expensive — background task that may download many MB
    PRECOMPUTE = "2/minute"   # /precompute-practice


# ---------------------------------------------------------------------------
# Input sanitization
# ---------------------------------------------------------------------------

# GP names should only contain letters, digits, spaces and a few punctuation chars
_GP_ALLOWED = re.compile(r"^[A-Za-z0-9 \-'\.éàü]{1,80}$")

# Session types that FastF1 actually supports
_VALID_SESSION_TYPES = {"R", "Q", "SQ", "FP1", "FP2", "FP3", "SS"}


def sanitize_gp_name(gp: str) -> str:
    """
    Strip leading/trailing whitespace and validate the GP name against an allowlist pattern.
    Raises ValueError on invalid input (caller should convert to 422).
    """
    gp = gp.strip()
    if not gp:
        raise ValueError("Grand Prix name must not be empty.")
    if len(gp) > 80:
        raise ValueError("Grand Prix name is too long (max 80 characters).")
    if not _GP_ALLOWED.match(gp):
        raise ValueError(
            f"Grand Prix name contains invalid characters: '{gp}'. "
            "Only letters, digits, spaces, hyphens, apostrophes, and dots are allowed."
        )
    return gp


def validate_session_type(session_type: str) -> str:
    """
    Normalise and validate a session type string.
    Returns the canonical uppercase form, raises ValueError on unknown types.
    """
    st = session_type.strip().upper()
    if st not in _VALID_SESSION_TYPES:
        raise ValueError(
            f"Unknown session type '{session_type}'. "
            f"Must be one of: {', '.join(sorted(_VALID_SESSION_TYPES))}."
        )
    return st


def validate_year(year: int) -> int:
    """Year must be within the FastF1 data range."""
    if year < 2018 or year > 2027:
        raise ValueError(f"Year {year} is out of the supported range (2018-2027).")
    return year
