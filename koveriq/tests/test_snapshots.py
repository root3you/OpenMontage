"""Rendered evidence for lane W3: the end card's CTA at 40, 80 and 120
characters (with and without a website) and burned-in captions on and off, in
both styles and all three formats.

Each composition is linted, audited in the browser with `hyperframes check`
(no layout errors: nothing overflows, is clipped or overlaps; with captions
on, the --caption-zone gate fails any scene text inside the caption band) and
snapshotted. Frames and one contact sheet per case go to
$KOVERIQ_SNAPSHOT_DIR (default koveriq/golden/out/w3-snapshots, git-ignored).

Opt-in: needs Node, the pinned HyperFrames CLI and its Chrome in the cache.

    KOVERIQ_HF_SNAPSHOT=1 pytest koveriq/tests/test_snapshots.py
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from PIL import Image

from koveriq import captions as caps
from koveriq import golden, hyperframes
from koveriq.compose import FORMATS, STYLES, build_composition
from koveriq.layout import FRAMES
from koveriq.tests.test_endcard import cta_of

pytestmark = pytest.mark.skipif(
    os.environ.get("KOVERIQ_HF_SNAPSHOT") != "1" or not hyperframes.available(),
    reason="set KOVERIQ_HF_SNAPSHOT=1 (needs node and the hyperframes CLI cache)",
)

OUT = Path(os.environ.get("KOVERIQ_SNAPSHOT_DIR") or golden.GOLDEN_DIR / "out" / "w3-snapshots")
CARD_SECONDS = 5
SITE = {"companyName": "Demo Shutters Co.", "website": "demo-shutters.example"}
NO_SITE = {"companyName": "Demo Shutters Co."}


def _slug(fmt: str) -> str:
    return fmt.replace(":", "x")


def _sheet(frames: list[Path], target: Path) -> Path:
    images = [Image.open(f).convert("RGB") for f in frames]
    landscape = images[0].width >= images[0].height
    width = 480 if landscape else 300
    height = round(images[0].height * width / images[0].width)
    cols = min(len(images), 3 if landscape else 6)
    rows = -(-len(images) // cols)
    sheet = Image.new("RGB", (cols * width + (cols - 1) * 8, rows * height + (rows - 1) * 8), "white")
    for i, image in enumerate(images):
        sheet.paste(image.resize((width, height)), ((i % cols) * (width + 8), (i // cols) * (height + 8)))
    sheet.save(target, quality=85)
    return target


def _held(report: hyperframes.CheckReport) -> list[str]:
    return report.errors + [w for w in report.warnings if w.startswith("layout:")]


# --------------------------------------------------------------------------- CTA


@pytest.mark.parametrize("style", sorted(STYLES))
@pytest.mark.parametrize("fmt", sorted(FORMATS))
@pytest.mark.parametrize("site", [True, False], ids=["website", "no-website"])
def test_cta_end_cards(style: str, fmt: str, site: bool) -> None:
    """Every CTA appears in full and nothing on the card overflows or overlaps."""
    variants = [(40, True), (80, True), (120, True), (120, False)] if site else [(40, True), (120, True), (80, False)]
    scenes, timings, start = [], {}, 0
    for i, (length, photo) in enumerate(variants, start=1):
        slots = {"overline": "Free home survey", "cta": cta_of(length), "steps": ["Measure", "Advise", "Fit"]}
        if photo:
            slots["assetId"] = "a-living"
        end = start + CARD_SECONDS * 1000
        scenes.append({"id": f"e{i}", "type": "text_card", "description": f"CTA {length}", "start_seconds": start / 1000,
                       "end_seconds": end / 1000, "kind": "cta_endcard", "slots": slots})
        timings[f"e{i}"] = {"startMs": start, "endMs": end, "words": []}
        start = end
    name = f"cta-{style}-{_slug(fmt)}-{'website' if site else 'no-website'}"
    comp = OUT / name / "composition"
    photo = {"a-living": golden.inputs()["assets"]["a-living"]}
    result = build_composition({"version": "1.0", "scenes": scenes}, {"title": name}, timings, photo, style, fmt,
                               SITE if site else NO_SITE, comp)
    assert not [w for w in result.lint_warnings if w.startswith("text_fit")], result.lint_warnings
    for i, (length, _) in enumerate(variants, start=1):
        page = (comp / "compositions" / f"e{i}.html").read_text(encoding="utf-8")
        shown = re.search(rf'id="e{i}-cta" style="[^"]*">(.*?)</h2>', page).group(1)
        assert shown.replace("<br>", " ") == cta_of(length).replace("&", "&amp;")
        assert ('id="e%d-pill"' % i in page) is site
    lint = hyperframes.lint(comp)
    assert lint.errors == [], lint.errors
    report = hyperframes.check(comp, samples=4 * len(variants))
    assert _held(report) == [], _held(report)
    frames = hyperframes.snapshot(comp, [CARD_SECONDS * i + 4.2 for i in range(len(variants))], OUT / name / "frames")
    assert len(frames) == len(variants)
    _sheet(frames, OUT / f"{name}.jpg")


# --------------------------------------------------------------------------- captions


def _caption_times(page: str, timings: dict) -> dict[str, float]:
    """A moment inside a caption of each captioned scene (its middle cue)."""
    shown = dict(re.findall(r'tl\.set\("#(captions-g\d+)", \{ visibility: "visible" \}, ([0-9.]+)\);', page))
    hidden = dict(re.findall(r'tl\.set\("#(captions-g\d+)", \{ visibility: "hidden" \}, ([0-9.]+)\);', page))
    out = {}
    for sid, timing in timings.items():
        cues = [(float(shown[g]), float(hidden[g])) for g in shown if timing["startMs"] / 1000 <= float(shown[g]) < timing["endMs"] / 1000]
        if cues:
            a, b = cues[len(cues) // 2]
            out[sid] = round((a + b) / 2 + 0.05, 2)
    return out


@pytest.mark.parametrize("style", sorted(STYLES))
@pytest.mark.parametrize("fmt", sorted(FORMATS))
@pytest.mark.parametrize("on", [True, False], ids=["captions-on", "captions-off"])
def test_burned_in_captions(style: str, fmt: str, on: bool) -> None:
    """The golden promo (real photos, real narration timings) with captions."""
    inputs = golden.inputs()
    name = f"captions-{style}-{_slug(fmt)}-{'on' if on else 'off'}"
    comp = OUT / name / "composition"
    result = build_composition(**inputs, style=style, fmt=fmt, out_dir=comp, captions=on)
    assert not [w for w in result.lint_warnings if w.startswith(("text_fit", "captions_empty"))], result.lint_warnings
    lint = hyperframes.lint(comp)
    assert lint.errors == [], lint.errors
    timings = inputs["timings"]
    kinds = {s["id"]: s["kind"] for s in inputs["scene_plan"]["scenes"]}
    if on:
        page = (comp / "compositions" / "captions.html").read_text(encoding="utf-8")
        times = _caption_times(page, timings)
        assert set(times) == {sid for sid, kind in kinds.items() if kind not in caps.NOT_CAPTIONED}
        frame, band = FRAMES[fmt], caps.BAND[FRAMES[fmt].name]
        y0 = (frame.h - frame.pad_bottom - band.height) / frame.h
        y1 = (frame.h - frame.pad_bottom) / frame.h
        seek = ",".join(f"{t / (result.duration_ms / 1000):.4f}" for t in times.values())
        report = hyperframes.check(comp, samples=20, caption_zone=f"x0=0;y0={y0:.4f};x1=1;y1={y1:.4f};severity=error;seek={seek}")
        assert _held(report) == [], _held(report)
        at = list(times.values())
    else:
        at = [round((t["startMs"] + t["endMs"]) / 2000, 2) for sid, t in timings.items() if kinds[sid] not in caps.NOT_CAPTIONED]
    frames = hyperframes.snapshot(comp, at, OUT / name / "frames")
    assert len(frames) == len(at)
    _sheet(frames, OUT / f"{name}.jpg")
