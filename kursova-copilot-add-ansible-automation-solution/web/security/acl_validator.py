"""ACL (iptables) validator security module."""

import re
import shlex
import subprocess


class ACLValidator:
    """Validates iptables firewall rules for dangerous configurations."""

    DANGEROUS_PATTERNS = [
        (re.compile(r"-j ACCEPT\s*$", re.IGNORECASE), "Blanket ACCEPT rule without conditions"),
        (re.compile(r"-s 0\.0\.0\.0/0.*-j ACCEPT", re.IGNORECASE), "Accept all from any source"),
        (re.compile(r"--dport 23\s.*-j ACCEPT", re.IGNORECASE), "Telnet (port 23) allowed inbound"),
        (re.compile(r"--dport 21\s.*-j ACCEPT", re.IGNORECASE), "FTP (port 21) allowed inbound"),
    ]

    def run(self) -> dict:
        rules = self._get_iptables_rules()
        policy = self._get_iptables_policy()
        issues = self._analyze_rules(rules, policy)

        if not issues:
            status = "pass"
            severity = "low"
            message = "No dangerous ACL rules found"
        elif any(i["severity"] == "critical" for i in issues):
            status = "fail"
            severity = "critical"
            message = f"Critical ACL issues: {len(issues)} problems found"
        elif any(i["severity"] == "high" for i in issues):
            status = "fail"
            severity = "high"
            message = f"High-severity ACL issues: {len(issues)} problems found"
        else:
            status = "warning"
            severity = "medium"
            message = f"ACL warnings: {len(issues)} issues found"

        return {
            "status": status,
            "severity": severity,
            "message": message,
            "rules": rules,
            "policy": policy,
            "issues": issues,
        }

    def _get_iptables_rules(self) -> list:
        rules = []
        try:
            result = subprocess.run(
                shlex.split("iptables -L -n --line-numbers"),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line and not line.startswith("Chain") and not line.startswith("target"):
                        rules.append(line)
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
            rules.append("iptables not accessible (run as root for full check)")
        return rules

    def _get_iptables_policy(self) -> dict:
        policy = {"INPUT": "UNKNOWN", "OUTPUT": "UNKNOWN", "FORWARD": "UNKNOWN"}
        try:
            result = subprocess.run(
                shlex.split("iptables -L -n"),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    match = re.match(r"Chain (\w+) \(policy (\w+)\)", line)
                    if match:
                        policy[match.group(1)] = match.group(2)
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
            pass
        return policy

    def _analyze_rules(self, rules: list, policy: dict) -> list:
        issues = []

        # Check default INPUT policy
        if policy.get("INPUT") == "ACCEPT":
            issues.append({
                "severity": "high",
                "description": "Default INPUT policy is ACCEPT (should be DROP or REJECT)",
                "remediation": "Run: iptables -P INPUT DROP",
                "rule": "Default policy",
            })

        # Check individual rules
        rules_text = "\n".join(rules)
        for pattern, description in self.DANGEROUS_PATTERNS:
            for rule in rules:
                if pattern.search(rule):
                    issues.append({
                        "severity": "medium",
                        "description": description,
                        "remediation": f"Review and tighten rule: {rule[:80]}",
                        "rule": rule[:80],
                    })
                    break

        return issues
