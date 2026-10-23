"""koveriq.compose.build_composition: the contract W1 codes against."""

from __future__ import annotations

import dataclasses
import inspect
import json
import pathlib
import re
import shutil
import subprocess

import pytest

from koveriq.compose import (
    FORMATS,
    STYLES,
    CompositionError,
    CompositionResult,
    build_composition,
)
from koveriq.scenes import KINDS, to_checkpoint_scene_plan
from koveriq.tests.fixtures import brand, make_assets, make_photo, plan_for

DIMS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}
ALL_KINDS = list(KINDS)  # every kind in one video


def _build(tmp_path, kinds=None, style="clean", fmt="16:9", seconds=None, **overrides):
    plan, script, timings = plan_for(kinds or ["photo_reveal", "option_chips", "cta_endcard"], seconds)
    args = dict(
        scene_plan=plan,
        script=script,
        timings=timings,
        assets=make_assets(tmp_path),
        style=style,
        fmt=fmt,
        brand=brand(),
        out_dir=tmp_path / "comp",
    )
    args.update(overrides)
    return build_composition(**args), args


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_contract_signatures() -> None:
    fields = {f.name: f.type for f in dataclasses.fields(CompositionResult)}
    assert list(fields) == ["index_html", "duration_ms", "hook_time_ms", "lint_warnings"]
    params = list(inspect.signature(build_composition).parameters)
    assert params == ["scene_plan", "script", "timings", "assets", "style", "fmt", "brand", "out_dir"]
    from koveriq.compose import apply_params

    assert list(inspect.signature(apply_params).parameters) == ["comp_dir", "params"]
    assert set(STYLES) == {"clean", "bold_offer"}
    assert set(FORMATS) == {"16:9", "9:16", "1:1"}


@pytest.mark.parametrize("style", sorted(STYLES))
@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_every_kind_renders_in_every_style_and_format(tmp_path, style: str, fmt: str) -> None:
    result, args = _build(tmp_path, ALL_KINDS, style=style, fmt=fmt)
    out = args["out_dir"]
    width, height = DIMS[fmt]

    assert result.index_html == out / "index.html"
    index = _read(result.index_html)
    assert 'data-composition-id="main"' in index
    assert f'data-width="{width}"' in index and f'data-height="{height}"' in index
    assert 'src="assets/vendor/gsap.min.js"' in index
    assert (out / "assets" / "vendor" / "gsap.min.js").is_file()
    assert result.duration_ms == 5000 * len(ALL_KINDS)
    assert f'data-duration="{result.duration_ms / 1000:g}"' in index

    for i, kind in enumerate(ALL_KINDS, start=1):
        sid = f"sc{i}"
        host = re.search(rf'<div id="{sid}"[^>]*>', index)
        assert host, sid
        assert f'data-composition-src="compositions/{sid}.html"' in host.group(0)
        assert f'data-start="{(i - 1) * 5:g}"' in host.group(0)
        assert 'data-duration="5"' in host.group(0)
        scene = _read(out / "compositions" / f"{sid}.html")
        assert scene.lstrip().startswith("<template>") and scene.rstrip().endswith("</template>")
        assert f'<div id="root" data-composition-id="{sid}" data-width="{width}" data-height="{height}"' in scene
        assert f'window.__timelines["{sid}"] = tl;' in scene
        assert f"data-kind=\"{kind}\"" in scene


def test_duration_is_the_sum_of_scene_spans_and_hook_is_first_midpoint(tmp_path) -> None:
    result, _ = _build(tmp_path, seconds=[4.2, 6.0, 7.3])
    assert result.duration_ms == 4200 + 6000 + 7300
    assert result.hook_time_ms == 2100


def test_only_referenced_photos_are_copied(tmp_path) -> None:
    _, args = _build(tmp_path, ["text_card", "steps", "cta_endcard"])
    copied = sorted(p.name for p in (args["out_dir"] / "assets" / "img").glob("*"))
    assert copied == ["a-2.jpg"]  # only the CTA photo


def test_slot_text_is_html_escaped(tmp_path) -> None:
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    plan["scenes"][0]["slots"]["headline"] = 'Safe <script>alert("x")</script> & sound'[:48]
    result = build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), tmp_path / "c")
    scene = _read(result.index_html.parent / "compositions" / "sc1.html")
    assert "<script>alert" not in scene
    assert "&lt;script&gt;" in scene and "&amp; sound" in scene


def test_brand_wordmark_and_website(tmp_path) -> None:
    result, args = _build(tmp_path)
    out = args["out_dir"]
    end = _read(out / "compositions" / "sc3.html")
    assert "shuttersfactory.co.uk" in end
    assert "Shutters Factory" in end
    assert "brand" in _read(result.index_html)


def test_brand_logo_is_copied_and_used(tmp_path) -> None:
    result, args = _build(tmp_path, brand=brand(tmp_path, logo=True))
    out = args["out_dir"]
    assert (out / "assets" / "brand" / "logo.jpg").is_file()
    assert 'src="assets/brand/logo.jpg"' in _read(out / "compositions" / "sc3.html")


def test_palette_override(tmp_path) -> None:
    custom = {**brand(), "palette": {"accent": "#0B6E4F"}}
    _, args = _build(tmp_path, brand=custom)
    assert "#0B6E4F" in _read(args["out_dir"] / "compositions" / "sc1.html")


@pytest.mark.parametrize(
    "bad_brand",
    [
        {"website": "x.co.uk"},
        {"companyName": "X", "website": "x.co.uk", "palette": {"accent": "red"}},
        {"companyName": "X", "website": "x.co.uk", "palette": {"glow": "#FFFFFF"}},
        {"companyName": "X", "website": "x.co.uk", "logoPath": "/nonexistent/logo.png"},
    ],
)
def test_invalid_brand_is_rejected(tmp_path, bad_brand) -> None:
    with pytest.raises(CompositionError):
        _build(tmp_path, brand=bad_brand)


def test_unknown_style_or_format(tmp_path) -> None:
    with pytest.raises(CompositionError):
        _build(tmp_path, style="showroom")
    with pytest.raises(CompositionError):
        _build(tmp_path, fmt="4:5")


def test_checkpoint_shaped_scene_plan_is_accepted(tmp_path) -> None:
    plan, script, timings = plan_for(["photo_reveal", "option_chips", "cta_endcard"])
    result = build_composition(
        to_checkpoint_scene_plan(plan), script, timings, make_assets(tmp_path), "clean", "16:9", brand(), tmp_path / "c"
    )
    assert result.duration_ms == 15000


def test_invalid_slots_are_rejected_with_the_scene_named(tmp_path) -> None:
    plan, script, timings = plan_for(["photo_reveal", "option_chips", "cta_endcard"])
    plan["scenes"][1]["slots"]["chips"] = ["x" * 19]
    with pytest.raises(CompositionError, match="sc2"):
        build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), tmp_path / "c")


def test_missing_asset_is_rejected(tmp_path) -> None:
    assets = make_assets(tmp_path)
    del assets["a-2"]
    with pytest.raises(CompositionError, match="a-2"):
        _build(tmp_path, assets=assets)


def test_unreadable_asset_is_rejected(tmp_path) -> None:
    assets = make_assets(tmp_path)
    bad = tmp_path / "in" / "bad.jpg"
    bad.write_bytes(b"not an image")
    assets["a-1"] = bad
    with pytest.raises(CompositionError, match="a-1"):
        _build(tmp_path, ["photo_pan", "cta_endcard"], assets=assets)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda t: t.pop("sc2"), "sc2"),
        (lambda t: t["sc1"].update(startMs=100), "start at 0"),
        (lambda t: t["sc2"].update(startMs=5100), "contiguous"),
        (lambda t: t["sc2"].update(startMs=4900), "contiguous"),
        (lambda t: t["sc3"].update(endMs=t["sc3"]["startMs"] + 900), "at least"),
        (lambda t: t["sc1"].update(endMs=4000.5), "integer"),
    ],
)
def test_timings_are_validated(tmp_path, mutate, message) -> None:
    plan, script, timings = plan_for(["photo_reveal", "option_chips", "cta_endcard"])
    mutate(timings)
    with pytest.raises(CompositionError, match=message):
        build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), tmp_path / "c")


def test_build_is_deterministic(tmp_path) -> None:
    plan, script, timings = plan_for(ALL_KINDS)
    assets = make_assets(tmp_path)
    a = build_composition(plan, script, timings, assets, "bold_offer", "9:16", brand(), tmp_path / "a")
    b = build_composition(plan, script, timings, assets, "bold_offer", "9:16", brand(), tmp_path / "b")
    files_a = sorted(p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(tmp_path / "b") for p in (tmp_path / "b").rglob("*") if p.is_file())
    assert files_a == files_b
    for rel in files_a:
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes(), rel
    assert a.lint_warnings == b.lint_warnings


def test_rebuild_removes_stale_scenes(tmp_path) -> None:
    out = tmp_path / "comp"
    _build(tmp_path, ["photo_reveal", "option_chips", "swatches", "cta_endcard"], out_dir=out)
    _build(tmp_path, ["photo_reveal", "cta_endcard"], out_dir=out)
    assert sorted(p.name for p in (out / "compositions").glob("*.html")) == ["brand.html", "sc1.html", "sc2.html"]


def test_text_that_cannot_fit_is_a_lint_warning(tmp_path) -> None:
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    plan["scenes"][0]["slots"]["headline"] = "Wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww"
    result = build_composition(plan, script, timings, make_assets(tmp_path), "clean", "9:16", brand(), tmp_path / "c")
    assert any(w.startswith("text_fit:sc1.headline") for w in result.lint_warnings)


def test_low_resolution_photo_is_a_lint_warning(tmp_path) -> None:
    assets = make_assets(tmp_path)
    assets["a-1"] = make_photo(tmp_path / "in" / "tiny.jpg", size=(640, 480))
    plan, script, timings = plan_for(["photo_pan", "cta_endcard"])
    result = build_composition(plan, script, timings, assets, "clean", "16:9", brand(), tmp_path / "c")
    assert any(w.startswith("photo_upscaled:sc1") for w in result.lint_warnings)


def test_optional_narration_track(tmp_path) -> None:
    assets = make_assets(tmp_path)
    wav = tmp_path / "in" / "narration.wav"
    wav.write_bytes(b"RIFF....WAVEfmt ")
    assets["@narration"] = wav
    result, args = _build(tmp_path, assets=assets)
    index = _read(result.index_html)
    assert '<audio id="narration" src="assets/audio/narration.wav"' in index
    assert (args["out_dir"] / "assets" / "audio" / "narration.wav").is_file()


def test_silent_without_narration(tmp_path) -> None:
    result, _ = _build(tmp_path)
    assert "<audio" not in _read(result.index_html)


def test_build_inputs_are_persisted_for_apply_params(tmp_path) -> None:
    _, args = _build(tmp_path)
    saved = json.loads(_read(args["out_dir"] / ".koveriq" / "build.json"))
    assert saved["style"] == "clean" and saved["fmt"] == "16:9"
    assert saved["params"] == {"scenes": {}}
    assert [s["id"] for s in saved["scene_plan"]["scenes"]] == ["sc1", "sc2", "sc3"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("style", sorted(STYLES))
def test_generated_scripts_are_valid_javascript(tmp_path, style: str) -> None:
    result, args = _build(tmp_path, ALL_KINDS, style=style)
    files = [result.index_html, *sorted((args["out_dir"] / "compositions").glob("*.html"))]
    for path in files:
        for i, body in enumerate(re.findall(r"<script>(.*?)</script>", _read(path), re.S)):
            js = tmp_path / f"{path.stem}-{i}.js"
            js.write_text(body, encoding="utf-8")
            proc = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
            assert proc.returncode == 0, f"{path.name}: {proc.stderr}"


def test_scenes_isolate_their_stacking_context(tmp_path) -> None:
    """Scene z-indexes must not paint over the brand mark mounted after the scenes."""
    result, args = _build(tmp_path, ["photo_reveal", "before_after", "cta_endcard"])
    for path in sorted((args["out_dir"] / "compositions").glob("sc*.html")):
        root_rule = re.search(r"#root \{[^}]*\}", _read(path)).group(0)
        assert "isolation: isolate" in root_rule, path.name


def test_before_label_hides_once_the_after_photo_wipes_in(tmp_path) -> None:
    _, args = _build(tmp_path, ["photo_reveal", "before_after", "cta_endcard"])
    scene = _read(args["out_dir"] / "compositions" / "sc2.html")
    assert re.search(r'tl\.to\("#sc2-blabel", \{ opacity: 0', scene)
