"""Auto-Fix operations: close ports, enable firewall, update system, reset ACL."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from validators.command_validator import run_safe

# Ports to block when running "close_open_ports"
DANGEROUS_PORTS = [21, 23, 135, 139, 445, 3389, 4444, 5900]


def close_open_ports() -> dict:
    """
    Block well-known dangerous TCP ports using iptables.

    Returns
    -------
    dict
        ``{status, changes, errors}``
    """
    changes = []
    errors = []

    for port in DANGEROUS_PORTS:
        result = run_safe(
            ["iptables", "-A", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "DROP"],
            timeout=10,
        )
        if result["success"]:
            changes.append(f"Blocked TCP port {port}")
        else:
            errors.append(f"Failed to block port {port}: {result['stderr'].strip()}")

    return {
        "status": "applied" if not errors else "partial",
        "changes": changes,
        "errors": errors,
    }


def enable_firewall() -> dict:
    """
    Enable UFW (Uncomplicated Firewall) if available, otherwise set default
    iptables DROP policy for INPUT.

    Returns
    -------
    dict
        ``{status, changes, errors}``
    """
    changes = []
    errors = []

    # Try ufw first
    ufw_result = run_safe(["ufw", "--force", "enable"], timeout=15)
    if ufw_result["success"]:
        changes.append("UFW firewall enabled")
        return {"status": "applied", "changes": changes, "errors": errors}

    if "not found" in ufw_result["stderr"]:
        # Fall back to iptables default DROP
        for cmd in [
            ["iptables", "-P", "INPUT", "DROP"],
            ["iptables", "-P", "FORWARD", "DROP"],
            ["iptables", "-A", "INPUT", "-m", "state", "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
            ["iptables", "-A", "INPUT", "-i", "lo", "-j", "ACCEPT"],
        ]:
            r = run_safe(cmd, timeout=10)
            if r["success"]:
                changes.append("iptables: " + " ".join(cmd[1:]))
            else:
                errors.append(r["stderr"].strip())
    else:
        errors.append(ufw_result["stderr"].strip())

    return {
        "status": "applied" if not errors else "partial",
        "changes": changes,
        "errors": errors,
    }


def update_patches() -> dict:
    """
    Update system packages via apt-get.

    Returns
    -------
    dict
        ``{status, changes, errors}``
    """
    changes = []
    errors = []

    update_result = run_safe(["apt-get", "update", "-y"], timeout=120)
    if update_result["success"]:
        changes.append("Package lists updated")
    else:
        errors.append("apt-get update: " + update_result["stderr"].strip())

    upgrade_result = run_safe(["apt-get", "upgrade", "-y"], timeout=300)
    if upgrade_result["success"]:
        changes.append("Packages upgraded")
    else:
        errors.append("apt-get upgrade: " + upgrade_result["stderr"].strip())

    return {
        "status": "applied" if not errors else "partial",
        "changes": changes,
        "errors": errors,
    }


def reset_acl_rules() -> dict:
    """
    Flush all iptables rules and restore safe defaults.

    Returns
    -------
    dict
        ``{status, changes, errors}``
    """
    changes = []
    errors = []

    flush_cmds = [
        ["iptables", "-F"],
        ["iptables", "-X"],
        ["iptables", "-t", "nat", "-F"],
        ["iptables", "-t", "mangle", "-F"],
        ["iptables", "-P", "INPUT", "ACCEPT"],
        ["iptables", "-P", "FORWARD", "ACCEPT"],
        ["iptables", "-P", "OUTPUT", "ACCEPT"],
    ]

    for cmd in flush_cmds:
        r = run_safe(cmd, timeout=10)
        if r["success"]:
            changes.append("iptables: " + " ".join(cmd[1:]))
        else:
            errors.append(r["stderr"].strip())

    return {
        "status": "applied" if not errors else "partial",
        "changes": changes,
        "errors": errors,
    }
