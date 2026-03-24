"""Command validator – blocks dangerous shell invocations."""

import re

ALLOWED_BASE_COMMANDS = {
    "ping",
    "netstat",
    "ss",
    "iptables",
    "ufw",
    "aa-status",
    "getenforce",
    "ssh",
    "sudo",
    "uname",
    "pkexec",
    "apt-get",
    "apt",
    "dpkg",
}

_DANGEROUS_PATTERNS = [
    re.compile(r"\brm\b.*-[rRfF]"),
    re.compile(r"\bsudo\s+su\b"),
    re.compile(r"\bbash\s+-c\b"),
    re.compile(r"\bsh\s+-c\b"),
    re.compile(r"[|;&`$]"),
    re.compile(r">\s*/"),
    re.compile(r"\beval\b"),
    re.compile(r"\bexec\b"),
    re.compile(r"/etc/shadow"),
    re.compile(r"/etc/sudoers"),
]


class CommandValidator:
    """Validates command lists before subprocess execution."""

    def validate_command(self, cmd_list: list) -> None:
        """Raise ValueError if the command list contains dangerous patterns.

        cmd_list must be a list of strings (no shell=True invocations).
        """
        if not cmd_list or not isinstance(cmd_list, list):
            raise ValueError("Command must be a non-empty list of strings")

        base = cmd_list[0].split("/")[-1]
        if base not in ALLOWED_BASE_COMMANDS:
            raise ValueError(
                f"Command '{base}' is not in the allowed commands whitelist"
            )

        full_cmd = " ".join(str(a) for a in cmd_list)
        for pattern in _DANGEROUS_PATTERNS:
            if pattern.search(full_cmd):
                raise ValueError(
                    f"Command contains a forbidden pattern: {pattern.pattern!r}"
                )
