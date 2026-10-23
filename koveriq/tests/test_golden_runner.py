"""The golden runner's pass/fail logic and the HyperFrames CLI wrapper, with fakes."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from koveriq import hyperframes
from koveriq.golden import __main__ as runner


def _fake_cli(monkeypatch, *, lint_errors=0, render_ok=True):
    calls = []

    def fake_run(args, comp_dir, *, timeout=900):
        calls.append(args[0])
        if args[0] == "lint":
            findings = [{"severity": "error", "code": "x", "message": "bad"}] * lint_errors
            payload = {"ok": not lint_errors, "errorCount": lint_errors, "findings": findings}
            return subprocess.CompletedProcess(args, 1 if lint_errors else 0, "banner\n" + json.dumps(payload), "")
        if args[0] == "snapshot":
            out = Path(args[args.index("--output") + 1])
            for i, t in enumerate(args[args.index("--at") + 1].split(",")):
                (out / f"frame-{i:02d}-at-{t}s.png").write_bytes(b"png")
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[0] == "render":
            if render_ok:
                Path(args[args.index("--output") + 1]).write_bytes(b"mp4")
            return subprocess.CompletedProcess(args, 0 if render_ok else 1, "", "boom")
        raise AssertionError(args)

    monkeypatch.setattr(hyperframes, "run", fake_run)
    return calls


def _probe(duration=38.5, width=1920, height=1080):
    return lambda mp4: {"durationSeconds": duration, "width": width, "height": height, "fps": 30.0, "videoCodec": "h264", "audioCodec": "aac"}


def test_golden_passes_and_writes_a_report(tmp_path, monkeypatch) -> None:
    calls = _fake_cli(monkeypatch)
    monkeypatch.setattr(runner, "_probe", _probe())
    monkeypatch.setattr(runner, "_loudness", lambda mp4: -16.0)
    assert runner.main(["--out", str(tmp_path / "out")]) == 0
    assert calls == ["lint", "snapshot", "render"]
    report = json.loads((tmp_path / "out" / "golden-report.json").read_text())
    assert report["ok"] and report["failures"] == []
    assert len(report["snapshots"]) == 3
    assert report["build"]["durationMs"] == 38500


@pytest.mark.parametrize(
    "probe, message",
    [(_probe(duration=38.75), "duration"), (_probe(width=1080, height=1920), "resolution")],
)
def test_golden_fails_on_duration_or_resolution(tmp_path, monkeypatch, probe, message) -> None:
    _fake_cli(monkeypatch)
    monkeypatch.setattr(runner, "_probe", probe)
    monkeypatch.setattr(runner, "_loudness", lambda mp4: None)
    assert runner.main(["--out", str(tmp_path / "out")]) == 1
    report = json.loads((tmp_path / "out" / "golden-report.json").read_text())
    assert not report["ok"] and message in report["failures"][0]


def test_golden_stops_on_lint_errors(tmp_path, monkeypatch) -> None:
    calls = _fake_cli(monkeypatch, lint_errors=1)
    assert runner.main(["--out", str(tmp_path / "out")]) == 1
    assert calls == ["lint"]


def test_render_failure_raises(tmp_path, monkeypatch) -> None:
    _fake_cli(monkeypatch, render_ok=False)
    with pytest.raises(RuntimeError, match="render failed"):
        hyperframes.render(tmp_path, tmp_path / "x.mp4")


def test_snapshot_failure_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(hyperframes, "run", lambda args, comp_dir, timeout=900: subprocess.CompletedProcess(args, 2, "", "no chrome"))
    with pytest.raises(RuntimeError, match="snapshot failed"):
        hyperframes.snapshot(tmp_path, [1.0], tmp_path / "s")


def test_lint_without_a_report_is_a_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(hyperframes, "run", lambda args, comp_dir, timeout=900: subprocess.CompletedProcess(args, 1, "not json", "npx: offline"))
    report = hyperframes.lint(tmp_path)
    assert not report.ok and "no report" in report.errors[0]


def test_cli_runs_pinned_and_offline(tmp_path, monkeypatch) -> None:
    seen = {}

    def fake_subprocess_run(cmd, **kwargs):
        seen["cmd"], seen["env"] = cmd, kwargs["env"]
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    hyperframes.run(["lint", "--json"], tmp_path)
    assert seen["cmd"][:4] == ["npx", "--prefer-offline", "--yes", f"hyperframes@{hyperframes.HYPERFRAMES_VERSION}"]
    for key, value in hyperframes.OFFLINE_ENV.items():
        assert seen["env"][key] == value
    assert hyperframes._json("x {bad") is None
    assert isinstance(hyperframes.available(), bool)


def test_probe_and_loudness_parse_real_tool_output(tmp_path, monkeypatch) -> None:
    payload = {
        "format": {"duration": "38.500000"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "30/1"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }
    outputs = {"ffprobe": json.dumps(payload), "ffmpeg": ""}
    errors = {"ffprobe": "", "ffmpeg": "Summary:\n  Integrated loudness:\n    I:         -16.2 LUFS\n"}

    def fake(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, outputs[cmd[0]], errors[cmd[0]])

    monkeypatch.setattr(subprocess, "run", fake)
    probe = runner._probe(tmp_path / "x.mp4")
    assert probe == {"durationSeconds": 38.5, "width": 1920, "height": 1080, "fps": 30.0, "videoCodec": "h264", "audioCodec": "aac"}
    assert runner._loudness(tmp_path / "x.mp4") == -16.2


def test_check_collects_errors_and_warnings_from_every_section(monkeypatch, tmp_path) -> None:
    report = {
        "ok": False,
        "lint": {"ok": True, "findings": []},
        "layout": {
            "ok": False,
            "findings": [
                {"severity": "error", "code": "caption_zone_collision", "selector": "#sc2-head", "message": "overlaps the band"},
                {"severity": "info", "code": "container_overflow", "selector": "#sc1-photo-img", "message": "Ken Burns"},
            ],
        },
        "craft": {"ok": True, "findings": [{"severity": "warning", "code": "dead_stretch", "message": "nothing moves"}]},
        "hdr": None,
    }
    seen = {}

    def fake_run(args, comp_dir, timeout=900):
        seen["args"] = args
        return subprocess.CompletedProcess(args, 1, "check\n" + json.dumps(report), "")

    monkeypatch.setattr(hyperframes, "run", fake_run)
    result = hyperframes.check(tmp_path, samples=12, caption_zone="x0=0;y0=.8;x1=1;y1=.9;seek=.5")
    assert seen["args"] == ["check", "--json", "--samples", "12", "--caption-zone", "x0=0;y0=.8;x1=1;y1=.9;seek=.5"]
    assert not result.ok
    assert result.errors == ["layout:caption_zone_collision: #sc2-head overlaps the band"]
    assert result.warnings == ["craft:dead_stretch: nothing moves"]
    assert result.raw == report


def test_check_without_a_report_is_not_ok(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hyperframes, "run", lambda args, comp_dir, timeout=900: subprocess.CompletedProcess(args, 1, "", "no chrome"))
    result = hyperframes.check(tmp_path)
    assert not result.ok and "no report" in result.errors[0]


def test_a_clean_check_is_ok(monkeypatch, tmp_path) -> None:
    clean = {"ok": True, "layout": {"ok": True, "findings": []}}
    monkeypatch.setattr(hyperframes, "run", lambda args, comp_dir, timeout=900: subprocess.CompletedProcess(args, 0, json.dumps(clean), ""))
    assert hyperframes.check(tmp_path).ok
