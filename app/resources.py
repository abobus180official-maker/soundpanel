from __future__ import annotations

import sys
from pathlib import Path


def asset_dir() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / "app" / "assets"
    return Path(__file__).resolve().parent / "assets"


def asset(name: str) -> str:
    return str(asset_dir() / name)
