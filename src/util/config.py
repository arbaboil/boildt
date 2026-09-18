"""Environment + config loader."""
from __future__ import annotations

import os
from pathlib import Path

from src.util.paths import ROOT


def load_env() -> dict[str, str]:
    """Load .env if present. Simple parser to avoid a dotenv dependency."""
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k, v in env.items():
        os.environ.setdefault(k, v)
    return env


def get_key(name: str, default: str | None = None) -> str | None:
    load_env()
    return os.environ.get(name, default)
