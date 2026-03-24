"""Port scanner security module."""

import shlex
import subprocess
import re


DANGEROUS_PORTS = {
    21: "FTP - unencrypted file transfer",
    23: "Telnet - unencrypted remote access",
    445: "SMB - Windows file sharing (lateral movement risk)",
    3389: "RDP - Remote Desktop Protocol",
    6379: "Redis - no-auth cache exposure",
}


class PortScanner:
    """Scans for open ports and identifies dangerous services."""

    def run(self) -> dict:
        open_ports = self._get_open_ports()
        dangerous_found = []
        details = []

        for port, pid, service in open_ports:
            details.append({
                "port": port,
                "pid": pid,
                "service": service,
                "dangerous": port in DANGEROUS_PORTS,
                "reason": DANGEROUS_PORTS.get(port, ""),
            })
            if port in DANGEROUS_PORTS:
                dangerous_found.append(port)

        if not dangerous_found:
            status = "pass"
            severity = "low"
            message = f"No dangerous ports found. {len(open_ports)} ports scanned."
        elif len(dangerous_found) >= 3:
            status = "fail"
            severity = "critical"
            message = f"Critical: {len(dangerous_found)} dangerous ports open: {dangerous_found}"
        else:
            status = "fail"
            severity = "high"
            message = f"Dangerous ports open: {dangerous_found}"

        return {
            "status": status,
            "severity": severity,
            "message": message,
            "open_ports": open_ports,
            "dangerous_ports": dangerous_found,
            "details": details,
        }

    def _get_open_ports(self) -> list:
        """Return list of (port, pid, service) tuples for listening TCP ports."""
        ports = []
        # Try ss first, fallback to netstat
        for cmd_str in ("ss -tlnp", "netstat -tlnp"):
            cmd = shlex.split(cmd_str)
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if result.returncode == 0:
                    ports = self._parse_output(result.stdout, cmd_str.startswith("ss"))
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        return ports

    def _parse_output(self, output: str, is_ss: bool) -> list:
        ports = []
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("State") or line.startswith("Active") or line.startswith("Proto"):
                continue
            # Extract port number from address like 0.0.0.0:22 or :::22 or *:22
            port_match = re.search(r'[:\*](\d+)\s', line)
            if not port_match:
                port_match = re.search(r'[:\*](\d+)$', line)
            if not port_match:
                continue
            try:
                port = int(port_match.group(1))
            except ValueError:
                continue

            # Try to extract PID/process name
            pid_match = re.search(r'pid=(\d+)', line)
            pid = pid_match.group(1) if pid_match else "unknown"

            proc_match = re.search(r'"([^"]+)"', line)
            service = proc_match.group(1) if proc_match else "unknown"

            ports.append((port, pid, service))

        # Deduplicate
        seen = set()
        unique = []
        for item in ports:
            if item[0] not in seen:
                seen.add(item[0])
                unique.append(item)
        return unique
