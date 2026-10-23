"""koveriq.compose.apply_params: the review step's one, validated revision."""

from __future__ import annotations

import json
import re

import jsonschema
import pytest

from koveriq.compose import CompositionError, apply_params, build_composition, load_params_schema
from koveriq.tests.fixtures import brand, make_assets, plan_for


@pytest.fixture()
def comp(tmp_path):
    plan, script, timings = plan_for(["photo_reveal", "photo_pan", "text_card", "before_after", "cta_endcard"])
    build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), tmp_path / "comp")
    return tmp_path / "comp"


def _scene(comp, sid: str) -> str:
    return (comp / "compositions" / f"{sid}.html").read_text(encoding="utf-8")


def _font_sizes(html: str, el_id: str) -> int:
    return int(re.search(rf'id="{el_id}" style="font-size:(\d+)px', html).group(1))


def test_schema_is_valid() -> None:
    jsonschema.Draft202012Validator.check_schema(load_params_schema())


def test_crop_focus_moves_the_photo(comp) -> None:
    apply_params(comp, {"scenes": {"sc2": {"crop_focus": {"x": 0.2, "y": 0.75}}}})
    assert "object-position:20% 75%" in _scene(comp, "sc2")


def test_crop_focus_applies_to_both_before_after_photos(comp) -> None:
    apply_params(comp, {"scenes": {"sc4": {"crop_focus": {"x": 0.3, "y": 0.6}}}})
    assert _scene(comp, "sc4").count("object-position:30% 60%") == 2


def test_font_scale_shrinks_the_scene_text(comp) -> None:
    before = _font_sizes(_scene(comp, "sc3"), "sc3-head")
    apply_params(comp, {"scenes": {"sc3": {"font_scale": 0.8}}})
    after = _font_sizes(_scene(comp, "sc3"), "sc3-head")
    assert after < before
    assert after >= 28


def test_shorten_text_drops_words(comp) -> None:
    apply_params(comp, {"scenes": {"sc3": {"shorten_text": {"headline": "No cords."}}}})
    html = _scene(comp, "sc3")
    assert "No cords." in html and "No chains" not in html


def test_params_replace_not_accumulate(comp) -> None:
    apply_params(comp, {"scenes": {"sc3": {"shorten_text": {"headline": "No cords."}}}})
    apply_params(comp, {"scenes": {"sc2": {"font_scale": 0.9}}})
    assert "No cords. No chains." in _scene(comp, "sc3")
    saved = json.loads((comp / ".koveriq" / "build.json").read_text(encoding="utf-8"))
    assert saved["params"] == {"scenes": {"sc2": {"font_scale": 0.9}}}


def test_same_params_twice_is_idempotent(comp) -> None:
    params = {"scenes": {"sc2": {"crop_focus": {"x": 0.4, "y": 0.4}, "font_scale": 0.85}}}
    apply_params(comp, params)
    first = {p.name: p.read_bytes() for p in (comp / "compositions").glob("*.html")}
    apply_params(comp, params)
    assert first == {p.name: p.read_bytes() for p in (comp / "compositions").glob("*.html")}


@pytest.mark.parametrize(
    "params, message",
    [
        ({"scenes": {"sc9": {"font_scale": 0.9}}}, "no such scene"),
        ({"scenes": {"sc3": {"font_scale": 0.5}}}, "font_scale"),
        ({"scenes": {"sc3": {"font_scale": 1.2}}}, "font_scale"),
        ({"scenes": {"sc3": {"crop_focus": {"x": 0.5, "y": 0.5}}}}, "shows no photo"),
        ({"scenes": {"sc2": {"crop_focus": {"x": 2, "y": 0.5}}}}, "crop_focus"),
        ({"scenes": {"sc3": {"shorten_text": {"headline": "No cords. No chains. Ever."}}}}, "shorter"),
        ({"scenes": {"sc3": {"shorten_text": {"headline": "15% off"}}}}, "only drop words"),
        ({"scenes": {"sc3": {"shorten_text": {"title": "x"}}}}, "no text slot"),
        ({"scenes": {"sc3": {"recolour": "#FF0000"}}}, "Additional properties"),
        ({"scenes": {"sc3": {}}}, "params"),
        ({"scenes": {}}, "params"),
        ({}, "scenes"),
    ],
)
def test_invalid_params_are_refused_and_nothing_changes(comp, params, message) -> None:
    before = {p.name: p.read_bytes() for p in (comp / "compositions").glob("*.html")}
    with pytest.raises(CompositionError, match=message):
        apply_params(comp, params)
    assert before == {p.name: p.read_bytes() for p in (comp / "compositions").glob("*.html")}


def test_needs_a_built_composition(tmp_path) -> None:
    with pytest.raises(CompositionError, match="build_composition"):
        apply_params(tmp_path, {"scenes": {"sc1": {"font_scale": 0.9}}})
