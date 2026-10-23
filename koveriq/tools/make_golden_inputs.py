"""Regenerate koveriq/golden/ inputs from the 2026-10-22 OpenMontage spike.

Dev-only provenance script; the outputs are committed, so the golden does not
need the spike. Run from the repo root with ffmpeg on PATH:

    python koveriq/tools/make_golden_inputs.py <spike project dir>

<spike project dir> is projects/plantation-shutters-promo of the spike. It
reads the spike's script, scene spans (edit_decisions.json), loudness-
normalised Piper narration (en_GB-cori-high) and its faster-whisper word
timings, and the three cropped CC BY-SA photos.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

GOLDEN = Path(__file__).resolve().parents[1] / "golden"
SECTIONS = ["s1-hook", "s2-measure", "s3-choice", "s4-safe", "s5-control", "s6-cta"]
PHOTOS = {"a-bay": "bay.jpg", "a-arches": "arches.jpg", "a-living": "living.jpg"}

SCENES = [
    {
        "role": "hook",
        "kind": "photo_reveal",
        "type": "broll",
        "description": "Hook: louvres open on a bay window",
        "slots": {
            "assetId": "a-bay",
            "overline": "Plantation shutters",
            "headline": "Light, your way.",
            "subline": "Beautiful light and privacy for every room.",
            "focus": {"x": 0.5, "y": 0.45},
        },
    },
    {
        "role": "product",
        "kind": "photo_pan",
        "type": "broll",
        "description": "Made to measure: slow push on arched windows",
        "slots": {
            "assetId": "a-arches",
            "overline": "Made to measure",
            "headline": "Made for your windows",
            "subline": "Bay windows, arches and awkward shapes",
            "focus": {"x": 0.5, "y": 0.4},
        },
    },
    {
        "role": "options",
        "kind": "swatches",
        "type": "animation",
        "description": "Colours and finishes, natural oak highlighted",
        "slots": {
            "title": "Your louvres. Your colour.",
            "swatches": [
                {"label": "Pure White", "color": "#FAF9F5"},
                {"label": "Silk White", "color": "#EFEADC"},
                {"label": "Stone", "color": "#CFC5B1"},
                {"label": "Natural Oak", "color": "#C39A68"},
                {"label": "Walnut", "color": "#6E4A32"},
            ],
            "highlight": 3,
        },
    },
    {
        "role": "benefit",
        "kind": "text_card",
        "type": "text_card",
        "description": "Child safe: no cords or chains",
        "slots": {
            "overline": "Child safe",
            "headline": "No cords. No chains.",
            "subline": "Child safe and pet friendly by design.",
            "tone": "inverse",
        },
    },
    {
        "role": "benefit",
        "kind": "steps",
        "type": "diagram",
        "description": "Light and privacy: tilt, close, control",
        "slots": {
            "title": "Light and privacy",
            "steps": ["Tilt for light", "Close for privacy", "Total control"],
        },
    },
    {
        "role": "cta",
        "kind": "cta_endcard",
        "type": "text_card",
        "description": "CTA: free home survey, website and brand",
        "slots": {
            "overline": "Free home survey",
            "cta": "Book your free home survey",
            "steps": ["Measure", "Advise", "Fit"],
            "assetId": "a-living",
            "focus": {"x": 0.5, "y": 0.5},
        },
    },
]


def main(spike: Path) -> None:
    artifacts = spike / "artifacts"
    script_in = json.loads((artifacts / "script.json").read_text(encoding="utf-8"))
    cuts = json.loads((artifacts / "edit_decisions.json").read_text(encoding="utf-8"))["cuts"]
    words_in = json.loads((spike / "assets" / "audio" / "word_timings.json").read_text(encoding="utf-8"))
    offsets = {s["id"]: s["start_seconds"] for s in script_in["sections"]}

    scenes, sections, timings = [], [], {}
    for i, (cut, spec, section) in enumerate(zip(cuts, SCENES, script_in["sections"]), start=1):
        sid = f"sc{i}"
        start_ms, end_ms = round(cut["in_seconds"] * 1000), round(cut["out_seconds"] * 1000)
        offset = offsets[section["id"]]
        words = [
            {"w": w["word"].strip(), "startMs": round((offset + w["start"]) * 1000), "endMs": round((offset + w["end"]) * 1000)}
            for w in words_in[section["id"]]
        ]
        timings[sid] = {"startMs": start_ms, "endMs": end_ms, "words": words}
        sections.append(
            {"id": f"s{i}", "text": section["text"], "start_seconds": section["start_seconds"], "end_seconds": section["end_seconds"]}
        )
        scenes.append(
            {
                "id": sid,
                "type": spec["type"],
                "description": spec["description"],
                "start_seconds": start_ms / 1000,
                "end_seconds": end_ms / 1000,
                "script_section_id": f"s{i}",
                "role": spec["role"],
                "kind": spec["kind"],
                "slots": spec["slots"],
            }
        )

    GOLDEN.mkdir(exist_ok=True)
    script = {
        "version": "1.0",
        "title": script_in["title"],
        "total_duration_seconds": cuts[-1]["out_seconds"],
        "sections": sections,
    }
    (GOLDEN / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (GOLDEN / "scene_plan.json").write_text(json.dumps({"version": "1.0", "scenes": scenes}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (GOLDEN / "timings.json").write_text(json.dumps(timings, indent=2) + "\n", encoding="utf-8")

    assets = GOLDEN / "assets"
    assets.mkdir(exist_ok=True)
    for asset_id, name in PHOTOS.items():
        shutil.copyfile(spike / "hyperframes-landscape" / "assets" / name, assets / f"{asset_id}.jpg")

    inputs, chains, labels = [], [], []
    for i, section in enumerate(SECTIONS):
        inputs += ["-i", str(spike / "assets" / "audio" / "norm" / f"{section}.wav")]
        delay = round(offsets[section] * 1000)
        chains.append(f"[{i}:a]adelay={delay}|{delay}[a{i}]")
        labels.append(f"[a{i}]")
    total = cuts[-1]["out_seconds"]
    graph = ";".join(chains) + f";{''.join(labels)}amix=inputs={len(SECTIONS)}:normalize=0,apad=whole_dur={total},atrim=0:{total}[out]"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[out]", "-ac", "1", "-ar", "48000",
         "-c:a", "aac", "-b:a", "96k", "-map_metadata", "-1", "-fflags", "+bitexact", str(assets / "narration.m4a")],
        check=True,
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
