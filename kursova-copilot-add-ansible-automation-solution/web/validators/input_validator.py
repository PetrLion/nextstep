"""Input validator for security test and fix names."""

import re
from markupsafe import escape

VALID_TEST_NAMES = [
    "port_scan",
    "cis_benchmark",
    "vulnerability_check",
    "ping_check",
    "acl_validation",
]

VALID_FIX_NAMES = [
    "close_ports",
    "enable_firewall",
    "update_system",
    "reset_acl",
]

_MAX_STRING_LEN = 512
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


class InputValidator:
    """Validates and sanitizes user-supplied input values."""

    def validate_test_name(self, name: str) -> str:
        """Raise ValueError if name is not a known test name; return the name."""
        if name not in VALID_TEST_NAMES:
            raise ValueError(
                f"Invalid test name '{name}'. Allowed: {VALID_TEST_NAMES}"
            )
        return name

    def validate_fix_name(self, name: str) -> str:
        """Raise ValueError if name is not a known fix name; return the name."""
        if name not in VALID_FIX_NAMES:
            raise ValueError(
                f"Invalid fix name '{name}'. Allowed: {VALID_FIX_NAMES}"
            )
        return name

    def sanitize_string(self, s: str) -> str:
        """Strip HTML tags and limit length."""
        if not isinstance(s, str):
            s = str(s)
        s = _HTML_TAG_PATTERN.sub("", s)
        s = s[:_MAX_STRING_LEN]
        return str(escape(s))
