"""Edge cases and validation branches across the koveriq package."""

from __future__ import annotations

import copy

import pytest
from PIL import Image

from koveriq.checkpoints import approver, write_brief_checkpoint
from koveriq.compose import CompositionError, build_composition
from koveriq.grammar import grammar_errors, word_count_errors
from koveriq.layout import item_beats
from koveriq.scenes import KINDS, load_kind_schema, scene_plan_errors, slot_errors
from koveriq.styles import STYLES, merge_palette, palette_warnings
from koveriq.tests.fixtures import brand, example, make_assets, plan_for
from koveriq.voices import load_voices, voices_errors

REQUIRED = {kind: load_kind_schema()["$defs"][kind].get("required", []) for kind in KINDS}


def _minimal(kind: str) -> dict:
    full = example(kind)
    return {"kind": kind, "slots": {k: v for k, v in full["slots"].items() if k in REQUIRED[kind]}}


@pytest.mark.parametrize("style", sorted(STYLES))
@pytest.mark.parametrize("fmt", ["16:9", "9:16", "1:1"])
def test_every_kind_renders_with_only_its_required_slots(tmp_path, style: str, fmt: str) -> None:
    plan, script, timings = plan_for(list(KINDS))
    for scene in plan["scenes"]:
        scene["slots"] = _minimal(scene["kind"])["slots"]
    result = build_composition(plan, script, timings, make_assets(tmp_path), style, fmt, brand(), tmp_path / "c")
    assert result.duration_ms == 5000 * len(KINDS)
    for i in range(1, len(KINDS) + 1):
        assert (tmp_path / "c" / "compositions" / f"sc{i}.html").is_file()


@pytest.mark.parametrize("direction", ["in", "out", "left", "right"])
def test_photo_pan_directions(tmp_path, direction: str) -> None:
    plan, script, timings = plan_for(["photo_pan", "cta_endcard"])
    plan["scenes"][0]["slots"]["direction"] = direction
    result = build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), tmp_path / "c")
    scene = (result.index_html.parent / "compositions" / "sc1.html").read_text(encoding="utf-8")
    assert 'tl.fromTo("#sc1-photo-img"' in scene
    if direction in ("left", "right"):
        assert "xPercent" in scene.split('tl.fromTo("#sc1-photo-img"')[1].split("\n")[0]


@pytest.mark.parametrize("fmt", ["16:9", "1:1"])
def test_long_chips_wrap_into_rows(tmp_path, fmt: str) -> None:
    plan, script, timings = plan_for(["option_chips", "cta_endcard"])
    plan["scenes"][0]["slots"] = {"title": "Options", "chips": [f"Option number {i}xx" for i in range(1, 7)]}
    result = build_composition(plan, script, timings, make_assets(tmp_path), "bold_offer", fmt, brand(), tmp_path / "c")
    scene = (result.index_html.parent / "compositions" / "sc1.html").read_text(encoding="utf-8")
    assert scene.count('class="k-chiprow"') > 1
    assert not [w for w in result.lint_warnings if w.startswith("text_fit:sc1.chips")]


def test_chips_that_cannot_fit_warn(tmp_path, monkeypatch) -> None:
    import koveriq.kinds as kinds

    plan, script, timings = plan_for(["option_chips", "cta_endcard"])
    plan["scenes"][0]["slots"] = {"chips": ["WWWWWWWWWWWWWWWWWW"]}
    original = kinds._chip_rows

    def tiny(ctx, chips, box_w, max_rows, *, column):
        return original(ctx, chips, 60, max_rows, column=column)

    monkeypatch.setattr(kinds, "_chip_rows", tiny)
    result = build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), tmp_path / "c")
    assert any(w.startswith("text_fit:sc1.chips") for w in result.lint_warnings)


def test_town_card_and_option_chips_without_a_photo(tmp_path) -> None:
    plan, script, timings = plan_for(["town_card", "option_chips", "cta_endcard"])
    del plan["scenes"][0]["slots"]["assetId"]
    del plan["scenes"][1]["slots"]["assetId"]
    del plan["scenes"][2]["slots"]["assetId"]
    result = build_composition(plan, script, timings, make_assets(tmp_path), "clean", "9:16", brand(), tmp_path / "c")
    assert sorted(p.name for p in (tmp_path / "c" / "assets" / "img").glob("*")) == []
    assert result.duration_ms == 15000


def test_item_beats_edge_cases() -> None:
    words = [("tilt", 0.3, 0.6), ("close", 2.0, 2.3)]
    assert item_beats(["—", "Close"], words, earliest=0.5, latest=4.0)[1] == pytest.approx(1.92)
    times = item_beats(["a", "b", "c"], [], earliest=1.0, latest=1.2, gap=0.22)
    assert times == sorted(times) and times[0] >= 1.0


def test_highlight_must_index_a_swatch() -> None:
    scene = example("swatches")
    scene["slots"]["highlight"] = 5  # schema allows 0-5, but there are 5 swatches
    assert any("does not index" in e for e in slot_errors(scene))


def test_non_object_inputs_are_reported() -> None:
    assert slot_errors("photo_pan") == ["scene: must be an object"]
    assert scene_plan_errors([]) == ["scene_plan: must be an object"]
    assert any(e.startswith("scene_plan") for e in scene_plan_errors({"version": "1.0", "scenes": "x"}))


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda a: a.update(timings=[]), "timings: must be an object"),
        (lambda a: a["timings"]["sc1"].update(words="none"), "words must be a list"),
        (lambda a: a["timings"]["sc1"]["words"].append({"w": 1}), "needs w"),
        (lambda a: a.update(brand="x"), "brand: must be an object"),
        (lambda a: a.update(brand={"companyName": "X", "website": "x .co.uk"}), "must not contain spaces"),
        (lambda a: a["scene_plan"]["scenes"][0].update(id="1st"), "scene ids must match"),
        (lambda a: a["scene_plan"]["scenes"][0].update(id="brand"), "scene ids must match"),
        (lambda a: a.update(style="nope", fmt="4:3"), "style"),
    ],
)
def test_input_validation(tmp_path, mutate, message) -> None:
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    args = {"scene_plan": plan, "script": script, "timings": timings, "assets": make_assets(tmp_path), "style": "clean", "fmt": "16:9", "brand": brand(), "out_dir": tmp_path / "c"}
    mutate(args)
    with pytest.raises(CompositionError, match=message):
        build_composition(**args)


def test_word_outside_its_scene_is_a_warning(tmp_path) -> None:
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    timings["sc1"]["words"].append({"w": "late", "startMs": 9000, "endMs": 9200})
    result = build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), tmp_path / "c")
    assert any(w.startswith("word_outside_scene:sc1") for w in result.lint_warnings)


def test_unsupported_image_formats_and_logos(tmp_path) -> None:
    gif = tmp_path / "in" / "x.gif"
    gif.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 600)).save(gif, "GIF")
    assets = make_assets(tmp_path)
    assets["a-1"] = gif
    plan, script, timings = plan_for(["photo_pan", "cta_endcard"])
    with pytest.raises(CompositionError, match="a-1"):
        build_composition(plan, script, timings, assets, "clean", "16:9", brand(), tmp_path / "c")
    bad_logo = tmp_path / "in" / "logo.png"
    bad_logo.write_bytes(b"not a png")
    with pytest.raises(CompositionError, match="logoPath"):
        build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", {**brand(), "logoPath": bad_logo}, tmp_path / "c")


def test_svg_logo_is_accepted(tmp_path) -> None:
    svg = tmp_path / "in" / "logo.svg"
    svg.parent.mkdir(parents=True, exist_ok=True)
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60"><rect width="200" height="60"/></svg>')
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    result = build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", {**brand(), "logoPath": svg}, tmp_path / "c")
    assert (result.index_html.parent / "assets" / "brand" / "logo.svg").is_file()


def test_bad_narration_file_is_rejected(tmp_path) -> None:
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    assets = make_assets(tmp_path)
    txt = tmp_path / "in" / "narration.txt"
    txt.write_text("x")
    assets["@narration"] = txt
    with pytest.raises(CompositionError, match="@narration"):
        build_composition(plan, script, timings, assets, "clean", "16:9", brand(), tmp_path / "c")


def test_medium_long_company_name_shrinks_below_the_floor_with_a_warning(tmp_path) -> None:
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    name = {"companyName": "Northern Window Shutters Ltd", "website": "x.example"}
    result = build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", name, tmp_path / "c")
    assert any(w.startswith("text_floor:brand.companyName") for w in result.lint_warnings)


def test_palette_validation_and_contrast_warnings() -> None:
    style = STYLES["clean"]
    assert merge_palette(style, "red")[1] == ["brand.palette: must be an object"]
    palette, errors = merge_palette(style, {"accent": None})
    assert errors == [] and palette["accent"] == style.palette["accent"]
    low, _ = merge_palette(style, {"ink": "#DDDDDD", "bg": "#FFFFFF"})
    assert any(w.startswith("palette_contrast:ink/bg") for w in palette_warnings(low))


def test_grammar_branches() -> None:
    plan, _, _ = plan_for(["photo_reveal", "photo_pan", "photo_pan", "photo_pan", "option_chips", "cta_endcard"])
    assert grammar_errors(plan, "product_promo", 30)  # three product scenes, max 2
    plan, _, _ = plan_for(["photo_reveal", "photo_pan", "option_chips", "cta_endcard"])
    plan["scenes"][1]["role"] = "hero"
    assert any("unknown role" in e for e in grammar_errors(plan, "product_promo", 20))
    assert word_count_errors({"sections": []}, "product_promo", 25)


def test_voice_validation_branches() -> None:
    data = load_voices()
    voice = data["voices"][0]
    assert voices_errors({"voices": [], "rejected": []})
    broken = copy.deepcopy(voice)
    broken["files"]["onnx"]["url"] = "http://x"
    broken["files"]["config"]["sha256"] = "abc"
    errors = voices_errors({"voices": [broken, broken], "rejected": [{"voiceId": voice["voiceId"], "reason": "x"}]})
    assert any("url must be an https URL" in e for e in errors)
    assert any("sha256" in e for e in errors)
    assert any("listed twice" in e for e in errors)
    assert any("exactly one voice" in e for e in errors)
    assert any("both allowed and rejected" in e for e in errors)


def test_checkpoint_helper_guards(tmp_path) -> None:
    with pytest.raises(ValueError):
        approver(" ")
    brief = {"version": "1.0", "title": "t", "hook": "h", "key_points": ["k"], "tone": "t", "style": "s", "target_platform": "generic", "target_duration_seconds": 30, "metadata": "x"}
    with pytest.raises(ValueError, match="metadata"):
        write_brief_checkpoint(tmp_path, "vid", brief, user_id="u")


@pytest.mark.parametrize(
    "override, message",
    [
        (lambda a: a["assets"].update({"a-1": 5}), "a-1"),
        (lambda a: a.update(style=["clean"]), "style"),
        (lambda a: a.update(fmt={"16:9": 1}), "fmt"),
        (lambda a: a.update(brand={**brand(), "logoPath": 7}), "logoPath"),
        (lambda a: a.update(assets={**a["assets"], "@narration": 3}), "@narration"),
    ],
)
def test_wrong_types_raise_composition_errors_not_type_errors(tmp_path, override, message) -> None:
    plan, script, timings = plan_for(["photo_pan", "cta_endcard"])
    args = {"scene_plan": plan, "script": script, "timings": timings, "assets": make_assets(tmp_path), "style": "clean", "fmt": "16:9", "brand": brand(), "out_dir": tmp_path / "c"}
    override(args)
    with pytest.raises(CompositionError, match=message):
        build_composition(**args)
