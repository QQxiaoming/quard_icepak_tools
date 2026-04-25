from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path


APP_NAME = "Quard Icepak 工具箱"
DEFAULT_VERSION = "dev"
_ROOT_DIR = Path(__file__).resolve().parent


def _run_git_command(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=_ROOT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    output = result.stdout.strip()
    return output or None


def _embedded_build_version() -> str | None:
    try:
        from build_version import BUILD_VERSION
    except ImportError:
        return None

    version = str(BUILD_VERSION).strip()
    return version or None


def _git_version() -> str | None:
    short_hash = _run_git_command("rev-parse", "--short", "HEAD")
    if short_hash is None:
        return None

    tag = _run_git_command("describe", "--tags", "--exact-match")
    version = f"{tag}-{short_hash}" if tag else short_hash
    dirty = _run_git_command("status", "--porcelain")
    if dirty:
        version = f"{version}-dirty"
    return version


@lru_cache(maxsize=1)
def get_app_version() -> str:
    env_version = os.environ.get("QUARD_ICEPAK_TOOLS_VERSION", "").strip()
    if env_version:
        return env_version

    embedded_version = _embedded_build_version()
    if embedded_version:
        return embedded_version

    git_version = _git_version()
    if git_version:
        return git_version

    return DEFAULT_VERSION


def get_window_title() -> str:
    return f"{APP_NAME} 版本：{get_app_version()}"