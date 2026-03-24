"""Port scanning via nmap (preferred) or netstat/ss fallback."""

import re
import socket
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from validators.network_validator import validate_host
from validators.command_validator import run_safe

# Common ports that should raise a warning when open
HIGH_RISK_PORTS = {21, 23, 25, 110, 135, 139, 445, 3389, 4444, 5900}


def _parse_nmap_output(stdout: str) -> list:
    """Extract open port numbers from nmap -oG output."""
    ports = []
    for line in stdout.splitlines():
        # Match lines like: "80/tcp  open  http"
        for m in re.finditer(r"(\d+)/tcp\s+open", line):
            ports.append(int(m.group(1)))
    return sorted(set(ports))


def _fallback_tcp_scan(host: str, port_list: list, timeout: float = 1.0) -> list:
    """Pure-Python TCP connect scan used when nmap is unavailable."""
    open_ports = []
    for port in port_list:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                open_ports.append(port)
        except OSError:
            pass
    return open_ports


def scan(host: str = "127.0.0.1", ports: str = "1-1024") -> dict:
    """
    Scan *host* for open TCP ports.

    Parameters
    ----------
    host : str
        Target IP or hostname (must be private/loopback).
    ports : str
        nmap-style port specification, e.g. ``"22,80,443"`` or ``"1-1024"``.

    Returns
    -------
    dict
        ``{host, open_ports, high_risk_ports, severity, raw_output}``
    """
    try:
        host = validate_host(host)
    except ValueError as exc:
        return {"error": str(exc)}

    # Validate ports string (allow digits, commas, hyphens only)
    if not re.fullmatch(r"[\d,\-]+", ports):
        return {"error": "Invalid port specification"}

    result = run_safe(["nmap", "-p", ports, "--open", "-T4", host], timeout=60)

    if not result["success"] and "not found" in result["stderr"]:
        # nmap not available – fall back to a limited TCP probe
        try:
            port_list = _expand_ports(ports)
        except ValueError as exc:
            return {"error": str(exc)}
        open_ports = _fallback_tcp_scan(host, port_list)
        raw = f"(nmap unavailable – TCP connect scan of {len(port_list)} ports)"
    else:
        open_ports = _parse_nmap_output(result["stdout"])
        raw = result["stdout"] or result["stderr"]

    risky = sorted(set(open_ports) & HIGH_RISK_PORTS)
    if risky:
        severity = "high"
    elif open_ports:
        severity = "medium"
    else:
        severity = "low"

    return {
        "host": host,
        "open_ports": open_ports,
        "high_risk_ports": risky,
        "severity": severity,
        "raw_output": raw,
    }


def _expand_ports(spec: str) -> list:
    """Expand a port specification like ``"22,80,443"`` or ``"1-100"``."""
    ports = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            ports.extend(range(int(lo), int(hi) + 1))
        else:
            ports.append(int(part))
    if any(p < 1 or p > 65535 for p in ports):
        raise ValueError("Port out of range")
    return ports
