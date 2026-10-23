"""Run the deterministic golden: build -> lint -> snapshot x3 -> render -> ffprobe.

    python -m koveriq.golden [--quality draft|standard|high] [--out DIR]

Exits non-zero if lint reports an error, if the MP4's duration is more than
the tolerance away from the timeline, or if its resolution is not the
format's. Writes out/golden-report.json with the measurements and wall times.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from koveriq import golden, hyperframes
from koveriq.compose import build_composition


def _probe(mp4: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate", "-of", "json", str(mp4)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    audio = [s for s in data["streams"] if s["codec_type"] == "audio"]
    num, den = (int(x) for x in video["avg_frame_rate"].split("/"))
    return {
        "durationSeconds": float(data["format"]["duration"]),
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": round(num / den, 3) if den else None,
        "videoCodec": video.get("codec_name"),
        "audioCodec": audio[0].get("codec_name") if audio else None,
    }


def _loudness(mp4: Path) -> float | None:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4), "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    match = re.findall(r"I:\s+(-?[0-9.]+) LUFS", proc.stderr)
    return float(match[-1]) if match else None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m koveriq.golden")
    parser.add_argument("--quality", default="standard", choices=["draft", "standard", "high"])
    parser.add_argument("--out", type=Path, default=golden.GOLDEN_DIR / "out")
    args = parser.parse_args(argv)
    exp = golden.expected()
    out: Path = args.out
    comp = out / "composition"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    report: dict = {"expected": exp, "quality": args.quality, "hyperframes": hyperframes.HYPERFRAMES_VERSION, "steps": {}}
    started = time.monotonic()

    def step(name: str, t0: float) -> None:
        report["steps"][name] = round(time.monotonic() - t0, 2)
        print(f"[golden] {name}: {report['steps'][name]} s", flush=True)

    t0 = time.monotonic()
    result = build_composition(**golden.inputs(), style=exp["style"], fmt=exp["fmt"], out_dir=comp)
    step("build", t0)
    report["build"] = {"durationMs": result.duration_ms, "hookTimeMs": result.hook_time_ms, "lintWarnings": result.lint_warnings}

    t0 = time.monotonic()
    lint = hyperframes.lint(comp)
    step("lint", t0)
    report["lint"] = {"errors": lint.errors, "warnings": lint.warnings}
    if lint.errors or not lint.ok:
        print("[golden] FAIL: hyperframes lint errors:\n  " + "\n  ".join(lint.errors), file=sys.stderr)
        (out / "golden-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 1

    t0 = time.monotonic()
    frames = hyperframes.snapshot(comp, exp["snapshotTimes"], out / "snapshots")
    step("snapshot", t0)
    report["snapshots"] = [p.name for p in frames]

    t0 = time.monotonic()
    mp4 = hyperframes.render(comp, out / f"golden-{exp['style']}-{exp['fmt'].replace(':', 'x')}.mp4", fps=exp["fps"], quality=args.quality)
    step("render", t0)

    probe = _probe(mp4)
    probe["loudnessLUFS"] = _loudness(mp4)
    report["mp4"] = {"path": mp4.name, "bytes": mp4.stat().st_size, **probe}
    report["steps"]["total"] = round(time.monotonic() - started, 2)

    failures = []
    expected_s = exp["durationMs"] / 1000
    if abs(probe["durationSeconds"] - expected_s) > exp["toleranceSeconds"]:
        failures.append(f"duration {probe['durationSeconds']:.3f} s is not within {exp['toleranceSeconds']} s of {expected_s} s")
    if (probe["width"], probe["height"]) != (exp["width"], exp["height"]):
        failures.append(f"resolution {probe['width']}x{probe['height']} is not {exp['width']}x{exp['height']}")
    if len(frames) != len(exp["snapshotTimes"]):
        failures.append(f"expected {len(exp['snapshotTimes'])} snapshots, got {len(frames)}")
    report["ok"] = not failures
    report["failures"] = failures
    (out / "golden-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ok", "failures", "steps", "mp4")}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
