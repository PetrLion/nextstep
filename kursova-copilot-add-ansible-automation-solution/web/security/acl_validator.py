"""Validates ACL / routing rules in GNS3 project configs."""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

GNS3_PROJECT_FILE = os.environ.get(
    "GNS3_PROJECT_FILE",
    "/tmp/gns3_project/Network_Topology.gns3",
)

# Rules that every router config should satisfy
_REQUIRED_RULES = [
    {
        "id": "ACL-001",
        "description": "Loopback interface should be configured",
        "pattern": re.compile(r"interface\s+lo", re.IGNORECASE),
        "severity": "warning",
    },
    {
        "id": "ACL-002",
        "description": "Default route should be present",
        "pattern": re.compile(r"ip\s+route\s+0\.0\.0\.0", re.IGNORECASE),
        "severity": "warning",
    },
    {
        "id": "ACL-003",
        "description": "No telnet (insecure) should be the only remote access",
        "pattern": re.compile(r"no\s+service\s+telnet|transport\s+input\s+ssh", re.IGNORECASE),
        "severity": "high",
    },
]

# Rules that must NOT appear
_FORBIDDEN_RULES = [
    {
        "id": "ACL-F01",
        "description": "Permit-all ACL (any any) is dangerous",
        "pattern": re.compile(r"permit\s+ip\s+any\s+any", re.IGNORECASE),
        "severity": "high",
    },
]

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "security_validator", "configs")


def _load_configs() -> dict:
    """Return a dict of {router_name: config_text} from the latest config files."""
    configs = {}
    config_dir = os.path.abspath(CONFIG_DIR)
    if not os.path.isdir(config_dir):
        return configs
    for fname in os.listdir(config_dir):
        if fname.endswith("_latest.cfg"):
            router = fname.replace("_latest.cfg", "")
            with open(os.path.join(config_dir, fname), "r", encoding="utf-8") as fh:
                configs[router] = fh.read()
    return configs


def validate() -> dict:
    """
    Validate routing / ACL rules for all known routers.

    Returns
    -------
    dict
        ``{routers: [{router, rules, violations}], overall_severity}``
    """
    configs = _load_configs()
    if not configs:
        # Return a placeholder result when no configs are present
        return {
            "routers": [],
            "overall_severity": "unknown",
            "raw_output": "No router configurations found in " + os.path.abspath(CONFIG_DIR),
        }

    results = []
    all_violations = []
    log_lines = []

    for router, config_text in sorted(configs.items()):
        violations = []
        satisfied = []

        for rule in _REQUIRED_RULES:
            if rule["pattern"].search(config_text):
                satisfied.append({"id": rule["id"], "description": rule["description"], "status": "ok"})
            else:
                violations.append(
                    {
                        "id": rule["id"],
                        "description": rule["description"],
                        "severity": rule["severity"],
                        "status": "missing",
                    }
                )

        for rule in _FORBIDDEN_RULES:
            if rule["pattern"].search(config_text):
                violations.append(
                    {
                        "id": rule["id"],
                        "description": rule["description"],
                        "severity": rule["severity"],
                        "status": "violated",
                    }
                )

        log_lines.append(f"{router}: {len(violations)} violation(s)")
        all_violations.extend(violations)
        results.append({"router": router, "rules": satisfied, "violations": violations})

    sev_order = {"high": 2, "warning": 1, "low": 0}
    if all_violations:
        worst = max(all_violations, key=lambda v: sev_order.get(v.get("severity", "low"), 0))
        overall = worst.get("severity", "low")
    else:
        overall = "ok"

    return {
        "routers": results,
        "overall_severity": overall,
        "raw_output": "\n".join(log_lines),
    }
