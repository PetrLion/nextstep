"""Ping checker security module."""

import re
import shlex
import subprocess


DEFAULT_TARGETS = [
    "127.0.0.1",
    "192.168.1.1",
    "192.168.1.2",
    "192.168.1.10",
    "192.168.1.20",
]


class PingChecker:
    """Checks reachability of network hosts using ICMP ping."""

    def run(self, targets: list | None = None) -> dict:
        if targets is None:
            targets = DEFAULT_TARGETS

        results = []
        for host in targets:
            reachable, latency_ms = self._ping_host(host)
            results.append({
                "host": host,
                "reachable": reachable,
                "latency_ms": latency_ms,
            })

        reachable_count = sum(1 for r in results if r["reachable"])
        total = len(results)

        if reachable_count == 0:
            status = "fail"
            severity = "high"
            message = "No hosts reachable"
        elif reachable_count < total:
            status = "warning"
            severity = "medium"
            message = f"{reachable_count}/{total} hosts reachable"
        else:
            status = "pass"
            severity = "low"
            message = f"All {total} hosts reachable"

        return {
            "status": status,
            "severity": severity,
            "message": message,
            "results": results,
            "reachable_count": reachable_count,
            "total_hosts": total,
        }

    def _ping_host(self, host: str) -> tuple[bool, float | None]:
        """Ping a single host. Returns (reachable, latency_ms)."""
        cmd = shlex.split(f"ping -c 1 -W 2 {host}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                latency = self._extract_latency(result.stdout)
                return True, latency
            return False, None
        except (subprocess.TimeoutExpired, OSError):
            return False, None

    def _extract_latency(self, output: str) -> float | None:
        match = re.search(r'time[=<]([\d.]+)\s*ms', output)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None
