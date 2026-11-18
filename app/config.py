from __future__ import annotations

import json
import os
from pathlib import Path


APP_NAME = "SoundPanel"


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


DEFAULTS = {
    "sounds": [],
    "out_device": None,
    "mic_device": None,
    "sfx_volume": 85,
    "mic_volume": 100,
    "mic_enabled": True,
    "exclusive_play": False,
    "window": {"width": 1080, "height": 700},
}


def load_config() -> dict:
    data = dict(DEFAULTS)
    try:
        with open(config_path(), "r", encoding="utf-8") as handle:
            stored = json.load(handle)
        if isinstance(stored, dict):
            data.update(stored)
    except (OSError, ValueError):
        pass
    return data


def save_config(data: dict) -> None:
    try:
        with open(config_path(), "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except OSError as exc:
        print("config save failed:", exc)


def sounds_dir() -> Path:
    path = config_dir() / "sounds"
    path.mkdir(parents=True, exist_ok=True)
    return path
