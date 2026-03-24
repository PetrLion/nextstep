"""Input sanitisation: prevents XSS, SQL injection, and validates CSRF tokens."""

import hashlib
import hmac
import html
import os
import re
import time

# ── CSRF ─────────────────────────────────────────────────────────────────────

_SECRET = os.environ.get("CSRF_SECRET", os.urandom(32).hex())
_TOKEN_TTL = 3600  # seconds


def generate_csrf_token() -> str:
    """Return a time-stamped HMAC token for CSRF protection."""
    ts = str(int(time.time()))
    sig = hmac.new(_SECRET.encode(), ts.encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"


def validate_csrf_token(token: str) -> bool:
    """Return True if the token is valid and not expired."""
    if not token or "." not in token:
        return False
    parts = token.split(".", 1)
    if len(parts) != 2:
        return False
    ts_str, sig = parts
    try:
        ts = int(ts_str)
    except ValueError:
        return False
    if time.time() - ts > _TOKEN_TTL:
        return False
    expected_sig = hmac.new(_SECRET.encode(), ts_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, sig)


# ── XSS / HTML injection ─────────────────────────────────────────────────────

def sanitize_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS."""
    return html.escape(str(text), quote=True)


# ── SQL injection (basic pattern detection) ──────────────────────────────────

_SQL_PATTERN = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC|UNION|CAST)\b"
    r"|--|;|/\*|\*/|xp_)",
    re.IGNORECASE,
)


def check_sql_injection(value: str) -> bool:
    """Return True if the value appears to contain a SQL injection attempt."""
    return bool(_SQL_PATTERN.search(value))


def validate_text_input(value: str, max_length: int = 256) -> str:
    """
    Sanitise a free-text input field.

    - Strips leading/trailing whitespace.
    - Truncates to *max_length* characters.
    - Raises ValueError on detected SQL injection.
    """
    value = str(value).strip()[:max_length]
    if check_sql_injection(value):
        raise ValueError("Potentially unsafe input detected")
    return value
