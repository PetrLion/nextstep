"""Validates IP addresses and port numbers to prevent injection."""

import ipaddress
import re

# Ports allowed for scanning (avoids scanning privileged ranges arbitrarily)
MIN_PORT = 1
MAX_PORT = 65535

# Hosts that are explicitly permitted targets (can be extended via config)
ALLOWED_HOST_PATTERN = re.compile(
    r"^(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3})$"
)


def validate_ip(address: str) -> str:
    """Return the validated IP string or raise ValueError."""
    try:
        parsed = ipaddress.ip_address(address.strip())
    except ValueError:
        raise ValueError(f"Invalid IP address: {address!r}")
    if parsed.is_loopback or parsed.is_private:
        return str(parsed)
    raise ValueError(f"Host {address!r} is not a private/loopback address")


def validate_host(host: str) -> str:
    """Return the validated hostname/IP string or raise ValueError."""
    host = host.strip()
    if not host:
        raise ValueError("Host must not be empty")
    # If the input looks like an IP address, validate it strictly as one
    try:
        ipaddress.ip_address(host)
        # It parsed as an IP – must be private or loopback
        return validate_ip(host)
    except ValueError as exc:
        # If it parsed as IP but failed the private check, re-raise
        if "not a private" in str(exc) or "Invalid IP" in str(exc):
            raise
    # Allow simple hostnames (letters, digits, hyphens, dots)
    if re.fullmatch(r"[A-Za-z0-9]([A-Za-z0-9\-\.]{0,253}[A-Za-z0-9])?", host):
        return host
    raise ValueError(f"Invalid host: {host!r}")


def validate_port(port) -> int:
    """Return the validated port integer or raise ValueError."""
    try:
        p = int(port)
    except (TypeError, ValueError):
        raise ValueError(f"Port must be an integer, got {port!r}")
    if not (MIN_PORT <= p <= MAX_PORT):
        raise ValueError(f"Port {p} out of range [{MIN_PORT}, {MAX_PORT}]")
    return p


def validate_port_list(ports) -> list:
    """Validate and return a list of port integers."""
    if isinstance(ports, str):
        ports = [p.strip() for p in ports.split(",") if p.strip()]
    return [validate_port(p) for p in ports]
