"""Run the pinned HyperFrames CLI on a built composition (lint, snapshot, render).

The worker and `make golden` call these; the unit tests do not need them.
Every call runs `npx --prefer-offline hyperframes@<pinned>` with telemetry,
update checks and auto-installs switched off, so a render never reaches the
network once the CLI and its Chrome are in the cache/image.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

HYPERFRAMES_VERSION = os.environ.get("KOVERIQ_HYPERFRAMES_VERSION", "0.8.185")

OFFLINE_ENV = {
    "HYPERFRAMES_NO_TELEMETRY": "1",
    "DO_NOT_TRACK": "1",
    "HYPERFRAMES_NO_UPDATE_CHECK": "1",
    "HYPERFRAMES_NO_AUTO_INSTALL": "1",
    "HYPERFRAMES_SKIP_SKILLS": "1",
}


def available() -> bool:
    return shutil.which("npx") is not None and shutil.which("node") is not None


def run(args: list[str], comp_dir: Path, *, timeout: int = 900) -> subprocess.CompletedProcess:
    cmd = ["npx", "--prefer-offline", "--yes", f"hyperframes@{HYPERFRAMES_VERSION}", *args]
    env = {**os.environ, **OFFLINE_ENV}
    return subprocess.run(cmd, cwd=str(comp_dir), capture_output=True, text=True, timeout=timeout, env=env, check=False)


def _json(stdout: str) -> Optional[Any]:
    start, end = stdout.find("{"), stdout.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(stdout[start : end + 1])
    except json.JSONDecodeError:
        return None


@dataclass
class LintReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw: Optional[dict] = None


def lint(comp_dir: Path) -> LintReport:
    proc = run(["lint", "--json"], comp_dir, timeout=180)
    report = _json(proc.stdout)
    if not isinstance(report, dict):
        return LintReport(ok=False, errors=[f"lint produced no report (exit {proc.returncode}): {proc.stderr[-800:]}"])
    errors, warnings = [], []
    for finding in report.get("findings", []):
        where = finding.get("file") or finding.get("filePath") or ""
        text = f"{finding.get('code')}: {finding.get('message')} {where}".strip()
        (errors if finding.get("severity") == "error" else warnings).append(text)
    return LintReport(ok=report.get("errorCount", len(errors)) == 0 and proc.returncode == 0, errors=errors, warnings=warnings, raw=report)


@dataclass
class CheckReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw: Optional[dict] = None


CHECK_SECTIONS = ("lint", "runtime", "layout", "motion", "contrast", "craft")


def check(comp_dir: Path, *, samples: int = 9, caption_zone: Optional[str] = None, timeout: int = 900) -> CheckReport:
    """`hyperframes check`: lint plus the browser audits (layout overflow and
    overlap, contrast, craft). `caption_zone` is the CLI's --caption-zone value
    (fractions of the canvas, with `seek` fractions of the duration to test at).
    Info findings (transients at one sample) are ignored."""
    args = ["check", "--json", "--samples", str(samples)]
    if caption_zone:
        args += ["--caption-zone", caption_zone]
    proc = run(args, comp_dir, timeout=timeout)
    report = _json(proc.stdout)
    if not isinstance(report, dict):
        return CheckReport(ok=False, errors=[f"check produced no report (exit {proc.returncode}): {proc.stderr[-800:]}"])
    errors, warnings = [], []
    for section in CHECK_SECTIONS:
        for finding in (report.get(section) or {}).get("findings") or []:
            where = finding.get("selector") or finding.get("file") or ""
            text = f"{section}:{finding.get('code')}: {where} {finding.get('message', '')}".replace("  ", " ").strip()
            if finding.get("severity") == "error":
                errors.append(text)
            elif finding.get("severity") == "warning":
                warnings.append(text)
    return CheckReport(ok=bool(report.get("ok")) and not errors, errors=errors, warnings=warnings, raw=report)


def snapshot(comp_dir: Path, times: list[float], output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    at = ",".join(f"{t:g}" for t in times)
    proc = run(["snapshot", "--at", at, "--no-end", "--output", str(output)], comp_dir, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"hyperframes snapshot failed (exit {proc.returncode}): {proc.stderr[-1500:]}")
    return sorted(output.glob("frame-*.png"))


def render(comp_dir: Path, output: Path, *, fps: int = 30, quality: str = "standard") -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    proc = run(["render", "--output", str(output), "--fps", str(fps), "--quality", quality], comp_dir, timeout=3600)
    if proc.returncode != 0 or not output.is_file():
        raise RuntimeError(f"hyperframes render failed (exit {proc.returncode}): {proc.stderr[-2000:]}")
    return output
