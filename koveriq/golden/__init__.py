"""Deterministic golden: fixed script, scene plan, timings and assets.

`python -m koveriq.golden` (or `make golden`) builds the clean 16:9
composition, lints it, snapshots it at three times, renders it and checks the
MP4's duration and resolution with ffprobe. See README.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GOLDEN_DIR = Path(__file__).resolve().parent
ASSET_IDS = ("a-bay", "a-arches", "a-living")


def _load(name: str) -> Any:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def inputs() -> dict[str, Any]:
    """Keyword arguments for build_composition, minus style/fmt/out_dir."""
    assets = {asset_id: GOLDEN_DIR / "assets" / f"{asset_id}.jpg" for asset_id in ASSET_IDS}
    assets["@narration"] = GOLDEN_DIR / "assets" / "narration.m4a"
    return {
        "scene_plan": _load("scene_plan.json"),
        "script": _load("script.json"),
        "timings": _load("timings.json"),
        "assets": assets,
        "brand": _load("brand.json"),
    }


def expected() -> dict[str, Any]:
    return _load("expected.json")
