from __future__ import annotations

import os
import subprocess


DEEPSEEK_KEYCHAIN_SERVICE = "xingzuo.deepseek"


def get_secret(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    if name == "DEEPSEEK_API_KEY":
        return _read_macos_keychain(DEEPSEEK_KEYCHAIN_SERVICE)

    return None


def _read_macos_keychain(service: str) -> str | None:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", os.getenv("USER", ""), "-s", service, "-w"],
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None
    secret = result.stdout.strip()
    return secret or None
