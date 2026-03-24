"""Network input validator for IPs, hostnames, and ports."""

import ipaddress
import re

_HOSTNAME_PATTERN = re.compile(
    r"^(?!-)[A-Za-z0-9\-]{1,63}(?<!-)(\.[A-Za-z0-9\-]{1,63}(?<!-))*$"
)


class NetworkValidator:
    """Validates network addresses, hostnames, and port numbers."""

    def validate_ip(self, ip: str) -> bool:
        """Return True if ip is a valid IPv4 or IPv6 address."""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def validate_hostname(self, hostname: str) -> bool:
        """Return True if hostname is a syntactically valid hostname/FQDN."""
        if not hostname or len(hostname) > 253:
            return False
        return bool(_HOSTNAME_PATTERN.match(hostname))

    def validate_port(self, port: int | str) -> bool:
        """Return True if port is an integer in the valid range 1-65535."""
        try:
            p = int(port)
            return 1 <= p <= 65535
        except (ValueError, TypeError):
            return False
