"""Reproducibility helpers: git commit, config hashing, environment capture."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess  # nosec B404
import sys
from importlib import metadata as importlib_metadata

from pydantic import BaseModel

from sentinel.schemas.experiments import EnvironmentInfo

_TRACKED_PACKAGES = [
    "pydantic",
    "numpy",
    "fastapi",
    "typer",
]


def get_git_commit(short: bool = True) -> str | None:
    try:
        args = ["git", "rev-parse", "--short" if short else "HEAD", "HEAD"]
        # Fixed argv, no shell, no user input reaches this command.
        out = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)  # nosec
        if out.returncode != 0:
            return None
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def get_git_dirty() -> bool | None:
    try:
        # Fixed argv, no shell, no user input reaches this command.
        out = subprocess.run(  # nosec
            ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5, check=False
        )
        if out.returncode != 0:
            return None
        return bool(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None


def config_hash(config: BaseModel) -> str:
    payload = json.dumps(config.model_dump(mode="json"), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def dataset_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def capture_environment() -> EnvironmentInfo:
    from sentinel import __version__

    packages = {}
    for pkg in _TRACKED_PACKAGES:
        try:
            packages[pkg] = importlib_metadata.version(pkg)
        except importlib_metadata.PackageNotFoundError:
            packages[pkg] = "not-installed"
    return EnvironmentInfo(
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        sentinel_version=__version__,
        packages=packages,
    )
