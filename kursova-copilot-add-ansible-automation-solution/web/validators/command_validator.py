"""Safe subprocess execution – whitelists commands and blocks shell injection."""

import shlex
import subprocess

# ── Whitelist of permitted executable names ───────────────────────────────────
ALLOWED_COMMANDS = {
    "ping",
    "nmap",
    "netstat",
    "ss",
    "iptables",
    "ip6tables",
    "ufw",
    "apt-get",
    "apt",
}

# Characters that are dangerous in shell contexts
_SHELL_META = set('|&;`$><!()\'"\\{}')


def _is_safe_arg(arg: str) -> bool:
    """Return True when *arg* contains no shell meta-characters."""
    return not any(c in _SHELL_META for c in arg)


def validate_command(args: list) -> list:
    """
    Validate a command argument list and return it unchanged.

    Raises:
        ValueError – if the command is not whitelisted or an argument contains
                     shell meta-characters.
    """
    if not args:
        raise ValueError("Empty command")
    executable = args[0]
    if executable not in ALLOWED_COMMANDS:
        raise ValueError(f"Command {executable!r} is not permitted")
    for arg in args[1:]:
        if not _is_safe_arg(str(arg)):
            raise ValueError(f"Argument {arg!r} contains unsafe characters")
    return args


def run_safe(args: list, timeout: int = 30) -> dict:
    """
    Run a whitelisted command with *shell=False* and return a result dict::

        {
            "success": bool,
            "stdout":  str,
            "stderr":  str,
            "returncode": int,
        }

    Raises ValueError for disallowed commands (caller should handle it).
    """
    validate_command(args)
    try:
        result = subprocess.run(
            [str(a) for a in args],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Command timed out", "returncode": -1}
    except FileNotFoundError:
        return {"success": False, "stdout": "", "stderr": f"{args[0]!r} not found", "returncode": -1}
