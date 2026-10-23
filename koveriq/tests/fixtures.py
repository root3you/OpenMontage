"""Shared example data for the KoverIQ tests: one valid scene per kind."""

from __future__ import annotations

import copy
from pathlib import Path

from PIL import Image

KIND_EXAMPLES: dict[str, dict] = {
    "photo_pan": {
        "assetId": "a-1",
        "overline": "Plantation shutters",
        "headline": "Made for your windows",
        "subline": "Every window. Every shape.",
        "direction": "in",
        "focus": {"x": 0.5, "y": 0.4},
    },
    "photo_reveal": {
        "assetId": "a-2",
        "overline": "Plantation shutters",
        "headline": "Light, your way.",
        "subline": "Beautiful light and privacy for every room.",
    },
    "option_chips": {
        "title": "Louvre sizes",
        "chips": ["47mm", "63mm", "76mm", "89mm"],
        "assetId": "a-1",
    },
    "swatches": {
        "title": "Colours and finishes",
        "swatches": [
            {"label": "Pure White", "color": "#FAF9F5"},
            {"label": "Silk White", "color": "#EFEADC"},
            {"label": "Stone", "color": "#CFC5B1"},
            {"label": "Natural Oak", "color": "#C39A68"},
            {"label": "Walnut", "color": "#6E4A32"},
        ],
        "highlight": 0,
    },
    "text_card": {
        "overline": "Child safe",
        "headline": "No cords. No chains.",
        "subline": "Safe for children and pets by design.",
        "tone": "dark",
    },
    "offer_card": {
        "overline": "This month",
        "offer": "15% off all shutters",
        "terms": "Ends 30 November",
        "badge": "Limited time",
    },
    "steps": {
        "title": "How it works",
        "steps": ["We measure", "We advise", "We fit"],
    },
    "before_after": {
        "beforeAssetId": "a-1",
        "afterAssetId": "a-2",
        "headline": "A bay window, transformed",
    },
    "town_card": {
        "overline": "Recently fitted in",
        "town": "Harrogate",
        "subline": "Full-height shutters for a bay window",
        "assetId": "a-2",
    },
    "cta_endcard": {
        "overline": "Free home survey",
        "cta": "Book your free home survey",
        "steps": ["Measure", "Advise", "Fit"],
        "assetId": "a-2",
    },
}

KINDS = list(KIND_EXAMPLES)

ROLE_FOR_KIND = {
    "photo_reveal": "hook",
    "photo_pan": "product",
    "option_chips": "options",
    "swatches": "options",
    "text_card": "benefit",
    "steps": "benefit",
}


def example(kind: str) -> dict:
    return {"kind": kind, "slots": copy.deepcopy(KIND_EXAMPLES[kind])}


def make_photo(path: Path, size=(1600, 1200), color=(200, 180, 150)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "JPEG", quality=80)
    return path


def make_assets(tmp_path: Path) -> dict[str, Path]:
    return {
        "a-1": make_photo(tmp_path / "in" / "one.jpg"),
        "a-2": make_photo(tmp_path / "in" / "two.jpg", size=(1200, 1600), color=(120, 130, 140)),
    }


def brand(tmp_path: Path | None = None, *, logo: bool = False) -> dict:
    out = {"companyName": "Shutters Factory", "website": "shuttersfactory.co.uk"}
    if logo and tmp_path is not None:
        out["logoPath"] = make_photo(tmp_path / "in" / "logo.jpg", size=(400, 120), color=(30, 30, 30))
    return out


def plan_for(kinds: list[str], seconds: list[float] | None = None) -> tuple[dict, dict, dict]:
    """Build a scene plan, script and timings for the given kind sequence."""
    seconds = seconds or [5.0] * len(kinds)
    scenes, sections, timings = [], [], {}
    start = 0
    for i, (kind, dur) in enumerate(zip(kinds, seconds), start=1):
        sid, sec = f"sc{i}", f"s{i}"
        end = start + int(round(dur * 1000))
        scene = {
            "id": sid,
            "type": "broll",
            "description": f"{kind} scene",
            "start_seconds": start / 1000,
            "end_seconds": end / 1000,
            "script_section_id": sec,
            **example(kind),
        }
        if kind in ROLE_FOR_KIND:
            scene["role"] = ROLE_FOR_KIND[kind]
        scenes.append(scene)
        text = f"Scene {i} narration about {kind.replace('_', ' ')}."
        sections.append({"id": sec, "text": text, "start_seconds": start / 1000, "end_seconds": end / 1000})
        words, t = [], start + 300
        for w in text.split():
            words.append({"w": w, "startMs": t, "endMs": t + 280})
            t += 320
        timings[sid] = {"startMs": start, "endMs": end, "words": words}
        start = end
    scene_plan = {"version": "1.0", "scenes": scenes}
    script = {"version": "1.0", "title": "Plantation shutters", "total_duration_seconds": start / 1000, "sections": sections}
    return scene_plan, script, timings
