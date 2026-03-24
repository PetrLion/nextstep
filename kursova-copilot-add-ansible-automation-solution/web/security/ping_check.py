"""ICMP reachability check using the system ping utility."""

import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from validators.network_validator import validate_host
from validators.command_validator import run_safe


def check(host: str = "127.0.0.1", count: int = 4) -> dict:
    """
    Ping *host* and return reachability information.

    Parameters
    ----------
    host : str
        Target IP or hostname (must be private/loopback).
    count : int
        Number of ICMP echo requests (1–10).

    Returns
    -------
    dict
        ``{host, reachable, packet_loss_pct, avg_rtt_ms, raw_output}``
    """
    try:
        host = validate_host(host)
    except ValueError as exc:
        return {"error": str(exc)}

    count = max(1, min(int(count), 10))

    result = run_safe(["ping", "-c", str(count), "-W", "2", host], timeout=30)

    reachable = result["success"]
    output = result["stdout"] + result["stderr"]

    # Extract packet-loss percentage
    loss_pct = 100.0
    m = re.search(r"(\d+(?:\.\d+)?)%\s+packet loss", output)
    if m:
        loss_pct = float(m.group(1))

    # Extract average RTT (Linux format: rtt min/avg/max/mdev)
    avg_rtt = None
    m = re.search(r"rtt[^=]*=\s*[\d.]+/([\d.]+)/", output)
    if m:
        avg_rtt = float(m.group(1))

    return {
        "host": host,
        "reachable": reachable,
        "packet_loss_pct": loss_pct,
        "avg_rtt_ms": avg_rtt,
        "raw_output": output,
    }
