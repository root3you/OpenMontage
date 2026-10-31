"""Deterministic install-showcase golden (spec §8.4, §13.5).

    python -m koveriq.golden.install [--quality draft|standard|high] [--out DIR] [--update-reference]

For each format in install-showcase/expected.json (9:16 and 1:1, style clean)
it builds the composition, runs `hyperframes lint` (0 errors), takes
`hyperframes snapshot` frames at the expected times and compares each with
SSIM against install-showcase/reference/<fmt>/ (luma, half size, at least
ssimMin), then renders the MP4 and checks its duration and resolution with
ffprobe. The plan is the worker's handwritten install plan on three synthetic
KoverIQ-original photos (install_photos.py). There is no narration, so the
frames depend on nothing but the templates.

--update-reference replaces the reference frames with this run's snapshots:
look at them before committing. References compare only on the platform that
made them (Chrome's text antialiasing differs between macOS and Linux), so on
another platform the SSIM step reports "skipped", never "passed".
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from koveriq import hyperframes
from koveriq.compose import build_composition
from koveriq.golden import GOLDEN_DIR
from koveriq.golden.__main__ import _probe
from koveriq.golden.ssim import luma, ssim

CASE_DIR = GOLDEN_DIR / "install-showcase"
REFERENCE_DIR = CASE_DIR / "reference"
ASSET_IDS = ("a-before-1", "a-after-1", "a-after-2")
SSIM_SCALE = 0.5


def _load(name: str) -> dict:
    return json.loads((CASE_DIR / name).read_text(encoding="utf-8"))


def expected() -> dict:
    return _load("expected.json")


def inputs() -> dict:
    """Keyword arguments for build_composition, minus style/fmt/out_dir."""
    return {
        "scene_plan": _load("scene_plan.json"),
        "script": _load("script.json"),
        "timings": _load("timings.json"),
        "assets": {asset_id: CASE_DIR / "assets" / f"{asset_id}.png" for asset_id in ASSET_IDS},
        "brand": _load("brand.json"),
    }


def slug(fmt: str) -> str:
    return fmt.replace(":", "x")


def platform_tag() -> str:
    return f"{sys.platform}-{platform.machine()}"


def compare_frames(frames: list[Path], fmt: str, minimum: float) -> dict:
    meta_path = REFERENCE_DIR / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else None
    if meta is None or meta.get("platform") != platform_tag():
        made_on = meta.get("platform") if meta else "no platform yet"
        return {"status": "skipped", "reason": f"reference frames come from {made_on}; this is {platform_tag()}"}
    scores: dict[str, float | None] = {}
    for frame in frames:
        reference = REFERENCE_DIR / slug(fmt) / frame.name
        scores[frame.name] = (
            round(ssim(luma(frame, SSIM_SCALE), luma(reference)), 4) if reference.is_file() else None
        )
    failed = [name for name, score in scores.items() if score is None or score < minimum]
    return {"status": "failed" if failed else "passed", "scores": scores, "failed": failed}


def write_reference(frames_by_fmt: dict[str, list[Path]]) -> None:
    """Replace the reference frames with half-size luma copies of these snapshots."""
    if REFERENCE_DIR.exists():
        shutil.rmtree(REFERENCE_DIR)
    for fmt, frames in frames_by_fmt.items():
        target = REFERENCE_DIR / slug(fmt)
        target.mkdir(parents=True)
        for frame in frames:
            Image.fromarray(luma(frame, SSIM_SCALE).astype(np.uint8)).save(target / frame.name)
    meta = {"platform": platform_tag(), "hyperframes": hyperframes.HYPERFRAMES_VERSION, "scale": SSIM_SCALE}
    (REFERENCE_DIR / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def _check_mp4(fmt: str, mp4: Path, exp: dict) -> tuple[dict, list[str]]:
    probe = _probe(mp4)
    width, height = exp["sizes"][fmt]
    expected_s = exp["durationMs"] / 1000
    failures = []
    if abs(probe["durationSeconds"] - expected_s) > exp["toleranceSeconds"]:
        failures.append(
            f"{fmt}: duration {probe['durationSeconds']:.3f} s is not within {exp['toleranceSeconds']} s of {expected_s} s"
        )
    if (probe["width"], probe["height"]) != (width, height):
        failures.append(f"{fmt}: resolution {probe['width']}x{probe['height']} is not {width}x{height}")
    return {"path": mp4.name, "bytes": mp4.stat().st_size, **probe}, failures


def run_format(fmt: str, exp: dict, out: Path, quality: str, update: bool) -> tuple[dict, list[Path], list[str]]:
    comp = out / slug(fmt) / "composition"
    result = build_composition(**inputs(), style=exp["style"], fmt=fmt, out_dir=comp)
    entry: dict = {
        "durationMs": result.duration_ms,
        "hookTimeMs": result.hook_time_ms,
        "lintWarnings": result.lint_warnings,
    }
    lint = hyperframes.lint(comp)
    entry["lint"] = {"errors": lint.errors, "warnings": lint.warnings}
    if lint.errors or not lint.ok:
        return entry, [], [f"{fmt}: hyperframes lint errors: {lint.errors}"]
    frames = hyperframes.snapshot(comp, exp["snapshotTimes"], out / slug(fmt) / "snapshots")
    failures = []
    if len(frames) != len(exp["snapshotTimes"]):
        failures.append(f"{fmt}: expected {len(exp['snapshotTimes'])} snapshots, got {len(frames)}")
    entry["ssim"] = {"status": "updating"} if update else compare_frames(frames, fmt, exp["ssimMin"])
    if entry["ssim"]["status"] == "failed":
        failures.append(f"{fmt}: SSIM below {exp['ssimMin']} for {entry['ssim']['failed']}")
    mp4 = hyperframes.render(
        comp, out / f"golden-install-{exp['style']}-{slug(fmt)}.mp4", fps=exp["fps"], quality=quality
    )
    entry["mp4"], mp4_failures = _check_mp4(fmt, mp4, exp)
    return entry, frames, failures + mp4_failures


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m koveriq.golden.install")
    parser.add_argument("--quality", default="standard", choices=["draft", "standard", "high"])
    parser.add_argument("--out", type=Path, default=GOLDEN_DIR / "out" / "install")
    parser.add_argument("--update-reference", action="store_true")
    args = parser.parse_args(argv)
    exp = expected()
    out: Path = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    report: dict = {
        "expected": exp,
        "quality": args.quality,
        "hyperframes": hyperframes.HYPERFRAMES_VERSION,
        "platform": platform_tag(),
        "formats": {},
    }
    failures: list[str] = []
    frames_by_fmt: dict[str, list[Path]] = {}
    for fmt in exp["formats"]:
        entry, frames, fmt_failures = run_format(fmt, exp, out, args.quality, args.update_reference)
        report["formats"][fmt] = entry
        frames_by_fmt[fmt] = frames
        failures += fmt_failures
    if args.update_reference and not failures:
        write_reference(frames_by_fmt)
        report["referenceUpdated"] = True
    report["ok"] = not failures
    report["failures"] = failures
    (out / "golden-install-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = {fmt: entry.get("ssim") for fmt, entry in report["formats"].items()}
    print(json.dumps({"ok": report["ok"], "failures": failures, "ssim": summary}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
