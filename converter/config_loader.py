from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "homestay_layers.json"


def load_homestay_config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def get_preset(name: str) -> dict[str, Any]:
    cfg = load_homestay_config()
    presets = cfg.get("presets", {})
    if name not in presets:
        known = ", ".join(sorted(presets))
        raise ValueError(f"未知预设 '{name}'，可选: {known}")
    return presets[name]
