"""CIS Benchmark security module."""

import os
import re
import shlex
import subprocess


class CISBenchmark:
    """Runs CIS-inspired hardening checks against the local system."""

    def run(self) -> dict:
        checks = []
        checks.extend(self._check_firewall())
        checks.extend(self._check_account_security())
        checks.extend(self._check_ssh_config())
        checks.extend(self._check_apparmor_selinux())

        passed = sum(1 for c in checks if c["status"] == "pass")
        total = len(checks) if checks else 1
        score = int((passed / total) * 100)

        failed_checks = [c for c in checks if c["status"] == "fail"]

        if score >= 80:
            status = "pass"
            severity = "low"
        elif score >= 50:
            status = "warning"
            severity = "medium"
        else:
            status = "fail"
            severity = "high" if score >= 30 else "critical"

        return {
            "status": status,
            "severity": severity,
            "score": score,
            "passed": passed,
            "total": total,
            "message": f"CIS Benchmark score: {score}/100 ({passed}/{total} checks passed)",
            "checks": checks,
            "failed_checks": [c["name"] for c in failed_checks],
        }

    def _check_firewall(self) -> list:
        checks = []

        # Check ufw
        ufw_active = False
        try:
            result = subprocess.run(
                shlex.split("ufw status"),
                capture_output=True, text=True, timeout=5, check=False,
            )
            ufw_active = "active" in result.stdout.lower()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check iptables
        iptables_active = False
        try:
            result = subprocess.run(
                shlex.split("iptables -L -n"),
                capture_output=True, text=True, timeout=5, check=False,
            )
            iptables_active = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        checks.append({
            "name": "Firewall Active",
            "status": "pass" if (ufw_active or iptables_active) else "fail",
            "description": "At least one firewall (ufw or iptables) should be active",
            "remediation": "Run: ufw enable  OR  systemctl start iptables",
            "details": f"ufw={'active' if ufw_active else 'inactive'}, iptables={'available' if iptables_active else 'unavailable'}",
        })

        return checks

    def _check_account_security(self) -> list:
        checks = []

        # Check /etc/passwd for accounts with empty passwords (field 2 empty)
        no_password_users = []
        try:
            with open("/etc/passwd", "r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.strip().split(":")
                    if len(parts) >= 2 and parts[1] == "":
                        no_password_users.append(parts[0])
        except (OSError, PermissionError):
            pass

        checks.append({
            "name": "No Empty Passwords",
            "status": "pass" if not no_password_users else "fail",
            "description": "No system accounts should have empty passwords in /etc/passwd",
            "remediation": "Lock or set passwords for: " + ", ".join(no_password_users) if no_password_users else "N/A",
            "details": f"Accounts with empty passwords: {no_password_users or 'none'}",
        })

        # Check for passwordless sudo (NOPASSWD in sudoers)
        nopasswd_found = False
        sudoers_paths = ["/etc/sudoers"]
        try:
            sudoers_d = os.listdir("/etc/sudoers.d")
            sudoers_paths.extend([os.path.join("/etc/sudoers.d", f) for f in sudoers_d])
        except (OSError, PermissionError):
            pass

        for path in sudoers_paths:
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                    if "NOPASSWD" in content:
                        nopasswd_found = True
                        break
            except (OSError, PermissionError):
                continue

        checks.append({
            "name": "No NOPASSWD Sudo",
            "status": "fail" if nopasswd_found else "pass",
            "description": "Sudo rules should require password authentication",
            "remediation": "Remove NOPASSWD directives from /etc/sudoers and /etc/sudoers.d/*",
            "details": f"NOPASSWD found in sudoers: {nopasswd_found}",
        })

        return checks

    def _check_ssh_config(self) -> list:
        checks = []
        sshd_config_path = "/etc/ssh/sshd_config"
        config = {}

        try:
            with open(sshd_config_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split(None, 1)
                        if len(parts) == 2:
                            config[parts[0].lower()] = parts[1].lower()
        except (OSError, PermissionError):
            # SSH config not accessible - treat as unknown/pass to avoid false positives
            checks.append({
                "name": "SSH PermitRootLogin Disabled",
                "status": "pass",
                "description": "SSH should not permit direct root login",
                "remediation": "Set PermitRootLogin no in /etc/ssh/sshd_config",
                "details": "sshd_config not readable (may not be installed)",
            })
            checks.append({
                "name": "SSH PasswordAuthentication",
                "status": "pass",
                "description": "SSH should prefer key-based authentication",
                "remediation": "Set PasswordAuthentication no in /etc/ssh/sshd_config",
                "details": "sshd_config not readable (may not be installed)",
            })
            return checks

        permit_root = config.get("permitrootlogin", "no")
        checks.append({
            "name": "SSH PermitRootLogin Disabled",
            "status": "pass" if permit_root in ("no", "prohibit-password") else "fail",
            "description": "SSH should not permit direct root login",
            "remediation": "Set PermitRootLogin no in /etc/ssh/sshd_config",
            "details": f"PermitRootLogin = {permit_root}",
        })

        password_auth = config.get("passwordauthentication", "yes")
        checks.append({
            "name": "SSH PasswordAuthentication",
            "status": "pass" if password_auth == "no" else "fail",
            "description": "SSH should prefer key-based authentication",
            "remediation": "Set PasswordAuthentication no in /etc/ssh/sshd_config",
            "details": f"PasswordAuthentication = {password_auth}",
        })

        return checks

    def _check_apparmor_selinux(self) -> list:
        checks = []

        # Check AppArmor
        apparmor_active = False
        try:
            result = subprocess.run(
                shlex.split("aa-status"),
                capture_output=True, text=True, timeout=5, check=False,
            )
            apparmor_active = result.returncode == 0 and "profiles are loaded" in result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check SELinux
        selinux_active = False
        try:
            result = subprocess.run(
                shlex.split("getenforce"),
                capture_output=True, text=True, timeout=5, check=False,
            )
            selinux_active = result.stdout.strip().lower() in ("enforcing", "permissive")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        checks.append({
            "name": "MAC Security (AppArmor/SELinux)",
            "status": "pass" if (apparmor_active or selinux_active) else "fail",
            "description": "Mandatory Access Control should be active",
            "remediation": "Enable AppArmor: systemctl enable --now apparmor OR enable SELinux",
            "details": f"AppArmor={'active' if apparmor_active else 'inactive'}, SELinux={'active' if selinux_active else 'inactive'}",
        })

        return checks
