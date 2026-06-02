from __future__ import annotations

import os
from pathlib import Path
import subprocess


DEEPSEEK_KEYCHAIN_SERVICE = "xingzuo.deepseek"
DEEPSEEK_KEY_FILE_ENV = "DEEPSEEK_API_KEY_FILE"


def get_secret(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    if name == "DEEPSEEK_API_KEY":
        key_file = os.getenv(DEEPSEEK_KEY_FILE_ENV)
        if key_file:
            value = _read_secret_file(Path(key_file))
            if value:
                return value
        return _read_macos_keychain(DEEPSEEK_KEYCHAIN_SERVICE)

    return None


def _read_secret_file(path: Path) -> str | None:
    try:
        secret = path.read_text().strip()
    except OSError:
        return None
    return secret or None


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
