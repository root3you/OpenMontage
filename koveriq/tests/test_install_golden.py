"""The install-showcase golden: synthetic KoverIQ-original photos, a plan that
follows the install grammar, a build with no warnings in 9:16 and 1:1, and the
SSIM comparison `make golden-install` uses. No browser is needed here."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from koveriq.compose import build_composition
from koveriq.golden import install, install_photos
from koveriq.golden.ssim import luma, ssim
from koveriq.grammar import grammar_errors, infer_roles
from koveriq.scenes import scene_plan_errors


def test_committed_photos_are_exactly_what_the_generator_draws() -> None:
    for name in install_photos.PHOTOS:
        with Image.open(install_photos.OUT / f"{name}.png") as committed:
            assert committed.size == install_photos.SIZE == (2560, 1920)
            assert committed.convert("RGB").tobytes() == install_photos.draw(name).tobytes(), name


def test_the_generator_is_deterministic(tmp_path: Path) -> None:
    first = install_photos.write(tmp_path / "a")
    second = install_photos.write(tmp_path / "b")
    for a, b in zip(first, second, strict=True):
        assert Image.open(a).tobytes() == Image.open(b).tobytes()


def test_ssim_is_one_for_the_same_frame_and_low_for_noise() -> None:
    frame = luma(install_photos.OUT / "a-after-1.png", 0.25)
    assert ssim(frame, frame) == pytest.approx(1.0)
    noisy = np.clip(frame + np.random.default_rng(7).normal(0, 12, frame.shape), 0, 255)
    assert ssim(frame, noisy) < 0.98
    with pytest.raises(ValueError, match="differ in size"):
        ssim(frame, frame[:-1])


def test_install_golden_plan_is_valid_and_follows_the_grammar() -> None:
    data = install.inputs()
    assert scene_plan_errors(data["scene_plan"]) == []
    total = install.expected()["durationMs"] / 1000
    assert grammar_errors(data["scene_plan"], "install_showcase", 30, total_seconds=total) == []
    assert infer_roles(data["scene_plan"], "install_showcase") == [
        "before",
        "reveal",
        "details",
        "details",
        "town_card",
        "cta",
    ]


@pytest.mark.parametrize("fmt", ["9:16", "1:1"])
def test_install_golden_builds_without_warnings(tmp_path: Path, fmt: str) -> None:
    exp = install.expected()
    result = build_composition(**install.inputs(), style=exp["style"], fmt=fmt, out_dir=tmp_path / "golden")
    assert (result.duration_ms, result.hook_time_ms) == (exp["durationMs"], exp["hookTimeMs"])
    assert result.lint_warnings == []


def _frames(directory: Path, values: list[int]) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, value in enumerate(values):
        path = directory / f"frame-{index}.png"
        Image.new("L", (64, 96), value).save(path)
        paths.append(path)
    return paths


def test_frames_are_compared_only_on_the_platform_that_made_the_references(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(install, "REFERENCE_DIR", tmp_path / "reference")
    frames = _frames(tmp_path / "snap", [120, 200])
    assert install.compare_frames(frames, "9:16", 0.98)["status"] == "skipped"
    install.write_reference({"9:16": frames})
    meta = json.loads((tmp_path / "reference" / "meta.json").read_text())
    assert (meta["platform"], meta["scale"]) == (install.platform_tag(), install.SSIM_SCALE)
    assert install.compare_frames(frames, "9:16", 0.98)["status"] == "passed"
    monkeypatch.setattr(install, "platform_tag", lambda: "elsewhere")
    assert install.compare_frames(frames, "9:16", 0.98)["status"] == "skipped"


def test_a_changed_frame_fails_the_comparison(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(install, "REFERENCE_DIR", tmp_path / "reference")
    install.write_reference({"1:1": _frames(tmp_path / "old", [120, 200])})
    changed = _frames(tmp_path / "new", [120, 200])
    noise = np.random.default_rng(3).integers(0, 255, (96, 64), dtype=np.uint8)
    Image.fromarray(noise).save(changed[1])
    result = install.compare_frames(changed, "1:1", 0.98)
    assert (result["status"], result["failed"]) == ("failed", ["frame-1.png"])
