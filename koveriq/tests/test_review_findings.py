"""Regression tests for the independent review of the compose builder (2026-10-23)."""

from __future__ import annotations

import json
import re

import pytest

from koveriq import compose, kinds
from koveriq.compose import CompositionError, apply_params, build_composition
from koveriq.layout import scene_words
from koveriq.scenes import slot_errors
from koveriq.styles import STYLES, merge_palette
from koveriq.tests.fixtures import brand, example, make_assets, plan_for
from koveriq.vendor import GsapUnavailable


def _args(tmp_path, kinds_=("photo_reveal", "photo_pan", "text_card", "cta_endcard")):
    plan, script, timings = plan_for(list(kinds_))
    return {"scene_plan": plan, "script": script, "timings": timings, "assets": make_assets(tmp_path), "style": "clean", "fmt": "16:9", "brand": brand(), "out_dir": tmp_path / "c"}


def _files(comp):
    return {p.name: p.read_bytes() for p in (comp / "compositions").glob("*.html")}


# 1. non-finite numbers


def test_nan_font_scale_is_refused_and_nothing_is_destroyed(tmp_path) -> None:
    args = _args(tmp_path)
    build_composition(**args)
    before = _files(args["out_dir"])
    with pytest.raises(CompositionError, match="finite"):
        apply_params(args["out_dir"], json.loads('{"scenes": {"sc2": {"font_scale": NaN}}}'))
    with pytest.raises(CompositionError, match="finite"):
        apply_params(args["out_dir"], json.loads('{"scenes": {"sc2": {"crop_focus": {"x": NaN, "y": 0.5}}}}'))
    assert _files(args["out_dir"]) == before


def test_nan_focus_in_slots_is_refused() -> None:
    scene = example("photo_pan")
    scene["slots"]["focus"] = {"x": float("nan"), "y": 0.5}
    assert any("finite" in e for e in slot_errors(scene))


def test_a_render_failure_leaves_the_previous_composition_intact(tmp_path, monkeypatch) -> None:
    args = _args(tmp_path)
    build_composition(**args)
    before = _files(args["out_dir"])

    def boom(*a, **k):
        raise RuntimeError("render bug")

    monkeypatch.setitem(kinds.KIND_BUILDERS, "text_card", boom)
    with pytest.raises(RuntimeError):
        apply_params(args["out_dir"], {"scenes": {"sc2": {"font_scale": 0.9}}})
    assert _files(args["out_dir"]) == before


# 2. shorten_text compares whole visible words


@pytest.mark.parametrize(
    "current, shorter",
    [
        ("Save 20% on all made-to-measure shutters", "Save £20 on shutters"),
        ("No cords. No chains.", "no cords."),
        ("欢迎光临本店的客人们", "免费"),
        ("Light, your way.", "Light your"),
    ],
)
def test_shorten_text_drops_whole_words_only(tmp_path, current: str, shorter: str) -> None:
    args = _args(tmp_path)
    args["scene_plan"]["scenes"][2]["slots"]["headline"] = current
    build_composition(**args)
    with pytest.raises(CompositionError, match="only drop"):
        apply_params(args["out_dir"], {"scenes": {"sc3": {"shorten_text": {"headline": shorter}}}})


def test_trailing_sentence_punctuation_may_go_with_the_dropped_words(tmp_path) -> None:
    args = _args(tmp_path)
    args["scene_plan"]["scenes"][2]["slots"]["headline"] = "Light, your way."
    build_composition(**args)
    apply_params(args["out_dir"], {"scenes": {"sc3": {"shorten_text": {"headline": "Light"}}}})


# 3. and 6. wrong-typed plan content


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["scenes"][0].update(slots=["x"]),
        lambda p: p["scenes"][0]["slots"].update(assetId=["a-1"]),
        lambda p: p["scenes"][0].update(id=["sc1"]),
        lambda p: p.update(scenes=5),
    ],
)
def test_wrong_typed_plan_content_raises_composition_error(tmp_path, mutate) -> None:
    args = _args(tmp_path)
    mutate(args["scene_plan"])
    with pytest.raises(CompositionError):
        build_composition(**args)


def test_non_string_script_title_does_not_crash(tmp_path) -> None:
    args = _args(tmp_path)
    args["script"]["title"] = 123
    assert build_composition(**args).duration_ms == 20000


# 4. no trailing newline sneaks past an anchored pattern


def test_trailing_newlines_are_rejected(tmp_path) -> None:
    scene = example("photo_pan")
    scene["slots"]["headline"] = "Made for your windows\n"
    assert slot_errors(scene)
    scene = example("photo_pan")
    scene["slots"]["assetId"] = "a-1\n"
    assert slot_errors(scene)
    assert merge_palette(STYLES["clean"], {"accent": "#FFFFFF\n"})[1]
    args = _args(tmp_path)
    args["scene_plan"]["scenes"][0]["id"] = "sc1\n"
    args["timings"]["sc1\n"] = args["timings"].pop("sc1")
    with pytest.raises(CompositionError):
        build_composition(**args)
    args = _args(tmp_path)
    build_composition(**args)
    with pytest.raises(CompositionError):
        apply_params(args["out_dir"], {"scenes": {"sc2\n": {"font_scale": 0.9}}})


# 5. a pan never exposes the background


@pytest.mark.parametrize("direction", ["left", "right"])
def test_pans_scale_around_the_centre(tmp_path, direction: str) -> None:
    args = _args(tmp_path, ("photo_pan", "cta_endcard"))
    args["scene_plan"]["scenes"][0]["slots"].update(direction=direction, focus={"x": 0.1, "y": 0.5})
    build_composition(**args)
    scene = (args["out_dir"] / "compositions" / "sc1.html").read_text(encoding="utf-8")
    img = re.search(r'<img id="sc1-photo-img"[^>]*>', scene).group(0)
    assert "object-position:10% 50%" in img
    assert "transform-origin:50% 50%" in img


# 7. an environment problem is not an input problem


def test_missing_gsap_is_not_a_composition_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KOVERIQ_GSAP_JS", str(tmp_path / "missing.js"))
    with pytest.raises(GsapUnavailable):
        build_composition(**_args(tmp_path))


# 8. timing details


def test_short_scenes_finish_their_entrances_before_the_cover(tmp_path) -> None:
    for style in ("clean", "bold_offer"):
        plan, script, timings = plan_for(["photo_reveal", "photo_pan", "option_chips", "text_card", "cta_endcard"], [4, 1.6, 1.8, 2.2, 4])
        build_composition(plan, script, timings, make_assets(tmp_path), style, "16:9", brand(), tmp_path / style)
        for sid, dur in (("sc2", 1.6), ("sc3", 1.8), ("sc4", 2.2)):
            scene = (tmp_path / style / "compositions" / f"{sid}.html").read_text(encoding="utf-8")
            cover = min(float(m) for m in re.findall(rf'tl\.fromTo\("#{sid}-tout[^\n]*\}}, ([0-9.]+)\);', scene))
            for line in re.findall(r"tl\.fromTo\(\"#[^\"]+\"[^\n]*", scene):
                if "-tout" in line or "-tin" in line or "-img" in line or "-decor" in line:
                    continue
                at = float(line.rsplit(", ", 1)[1].rstrip(");"))
                duration = float(re.search(r"duration: ([0-9.]+)", line).group(1))
                assert at + duration <= cover + 1e-6, (style, sid, line)


def test_cards_paint_above_photo_covers(tmp_path) -> None:
    args = _args(tmp_path, ("photo_reveal", "cta_endcard"))
    args["fmt"] = "1:1"
    build_composition(**args)
    scene = (args["out_dir"] / "compositions" / "sc1.html").read_text(encoding="utf-8")
    card_z = int(re.search(r"\.k-card \{[^}]*z-index: (\d+)", scene).group(1))
    cover_z = int(re.search(r"\.k-cover \{[^}]*z-index: (\d+)", scene).group(1))
    assert card_z > cover_z


def test_words_outside_the_scene_are_ignored_for_beats() -> None:
    timing = {"startMs": 1000, "endMs": 3000, "words": [{"w": "early", "startMs": 0, "endMs": 200}, {"w": "in", "startMs": 1500, "endMs": 1600}, {"w": "late", "startMs": 3500, "endMs": 3600}]}
    assert [w[0] for w in scene_words(timing)] == ["in"]


# 9. ids that differ only by case would share a file on macOS/Windows


def test_ids_differing_only_by_case_are_rejected(tmp_path) -> None:
    args = _args(tmp_path)
    args["scene_plan"]["scenes"][1]["id"] = "SC1"
    args["timings"]["SC1"] = args["timings"].pop("sc2")
    with pytest.raises(CompositionError, match="case"):
        build_composition(**args)
    args = _args(tmp_path)
    args["assets"]["A-1"] = args["assets"]["a-1"]
    args["scene_plan"]["scenes"][2]["kind"] = "photo_pan"
    args["scene_plan"]["scenes"][2]["slots"] = {"assetId": "A-1"}
    with pytest.raises(CompositionError, match="case"):
        build_composition(**args)


# second review pass


def test_shorten_text_only_cuts_words_off_the_end(tmp_path) -> None:
    """Dropping a middle word can flip a claim ("Free survey, fitting extra"
    -> "Free fitting"); cutting the end of the line cannot add one."""
    args = _args(tmp_path)
    args["scene_plan"]["scenes"][2]["slots"]["headline"] = "Free survey, fitting extra"
    build_composition(**args)
    with pytest.raises(CompositionError, match="only drop"):
        apply_params(args["out_dir"], {"scenes": {"sc3": {"shorten_text": {"headline": "Free fitting"}}}})
    apply_params(args["out_dir"], {"scenes": {"sc3": {"shorten_text": {"headline": "Free survey"}}}})


def test_decompression_bomb_is_an_unreadable_image(tmp_path) -> None:
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    bomb = tmp_path / "bomb.png"
    header = struct.pack(">IIBBBBB", 30000, 30000, 8, 2, 0, 0, 0)
    bomb.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"\x00")) + chunk(b"IEND", b""))
    args = _args(tmp_path)
    args["assets"]["a-1"] = bomb
    with pytest.raises(CompositionError, match="a-1"):
        build_composition(**args)


def test_dict_scene_id_is_a_composition_error(tmp_path) -> None:
    args = _args(tmp_path)
    args["scene_plan"]["scenes"][0]["id"] = {"x": 1}
    with pytest.raises(CompositionError):
        build_composition(**args)


def test_scene_ids_cannot_collide_with_element_ids(tmp_path) -> None:
    """Element ids are <sceneId>-<name>, so a scene id may not contain '-'."""
    args = _args(tmp_path)
    args["scene_plan"]["scenes"][0]["id"] = "hero"
    args["timings"]["hero"] = args["timings"].pop("sc1")
    args["scene_plan"]["scenes"][1]["id"] = "hero-card"
    args["timings"]["hero-card"] = args["timings"].pop("sc2")
    with pytest.raises(CompositionError, match="hero-card"):
        build_composition(**args)


def test_malformed_stored_extensions_do_not_crash(tmp_path) -> None:
    args = _args(tmp_path)
    scene = args["scene_plan"]["scenes"][0]
    scene.pop("kind")
    scene.pop("slots")
    args["scene_plan"]["metadata"] = {"koveriq": {"scenes": {"sc1": ["kind", "slots"]}}}
    with pytest.raises(CompositionError):
        build_composition(**args)


@pytest.mark.parametrize(
    "kinds_, hidden",
    [
        (("cta_endcard",), None),
        (("photo_pan", "cta_endcard", "text_card"), (5.0, 10.0)),
    ],
)
def test_corner_mark_is_hidden_on_end_cards(tmp_path, kinds_, hidden) -> None:
    args = _args(tmp_path, kinds_)
    result = build_composition(**args)
    index = result.index_html.read_text(encoding="utf-8")
    if hidden is None:
        assert 'id="brand"' not in index
        return
    bug = (args["out_dir"] / "compositions" / "brand.html").read_text(encoding="utf-8")
    start, end = hidden
    assert re.search(rf'tl\.to\("#brand-bug", \{{ opacity: 0[^\n]*\}}, {start - 0.35:g}\);', bug)
    assert re.search(rf'tl\.to\("#brand-bug", \{{ opacity: 1[^\n]*\}}, {end + 0.3:g}\);', bug)


def test_extra_non_json_content_is_not_saved(tmp_path) -> None:
    args = _args(tmp_path)
    args["timings"]["sc1"]["debug"] = {1, 2}
    args["scene_plan"]["scenes"][0]["required_assets"] = [{"type": "photo", "description": "x", "source": "provided", "obj": object()}]
    result = build_composition(**args)
    saved = json.loads((args["out_dir"] / ".koveriq" / "build.json").read_text(encoding="utf-8"))
    assert "debug" not in saved["timings"]["sc1"]
    assert set(saved["scene_plan"]["scenes"][0]) <= {"id", "kind", "slots", "role"}
    assert result.duration_ms == 20000
