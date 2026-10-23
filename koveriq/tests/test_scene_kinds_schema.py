"""koveriq/scene_kinds.schema.json: typed slots for the ten scene kinds."""

from __future__ import annotations

import copy

import jsonschema
import pytest

from koveriq.scenes import KINDS, PHOTO_KINDS, load_kind_schema, slot_errors
from koveriq.tests.fixtures import KIND_EXAMPLES, example


def test_schema_is_a_valid_2020_12_schema() -> None:
    schema = load_kind_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_the_ten_kinds_are_declared() -> None:
    assert set(KINDS) == {
        "photo_pan",
        "photo_reveal",
        "option_chips",
        "swatches",
        "text_card",
        "offer_card",
        "steps",
        "before_after",
        "town_card",
        "cta_endcard",
    }
    assert set(load_kind_schema()["properties"]["kind"]["enum"]) == set(KINDS)
    assert set(KIND_EXAMPLES) == set(KINDS)


@pytest.mark.parametrize("kind", sorted(KIND_EXAMPLES))
def test_every_kind_example_is_valid(kind: str) -> None:
    assert slot_errors(example(kind)) == []


@pytest.mark.parametrize("kind", sorted(KIND_EXAMPLES))
def test_unknown_slots_are_rejected(kind: str) -> None:
    scene = example(kind)
    scene["slots"]["html"] = "<b>x</b>"
    assert slot_errors(scene)


def test_photo_kinds_reference_an_asset_id() -> None:
    assert set(PHOTO_KINDS) == {"photo_pan", "photo_reveal", "before_after"}
    for kind in ("photo_pan", "photo_reveal"):
        scene = example(kind)
        del scene["slots"]["assetId"]
        assert any("assetId" in e for e in slot_errors(scene)), kind
    scene = example("before_after")
    del scene["slots"]["afterAssetId"]
    assert slot_errors(scene)


@pytest.mark.parametrize("bad_id", ["../etc/passwd", "a/b", "", "a b", "x" * 65, ".hidden"])
def test_asset_ids_cannot_escape_the_assets_dir(bad_id: str) -> None:
    scene = example("photo_pan")
    scene["slots"]["assetId"] = bad_id
    assert slot_errors(scene)


def test_option_chips_allow_at_most_six_chips_of_eighteen_chars() -> None:
    scene = example("option_chips")
    scene["slots"]["chips"] = [f"{i}" + "x" * 17 for i in range(6)]
    assert slot_errors(scene) == []
    scene["slots"]["chips"] = [f"{i}" + "x" * 17 for i in range(7)]
    assert slot_errors(scene)
    scene["slots"]["chips"] = ["47mm", "47MM"]
    assert any("unique" in e for e in slot_errors(scene))
    scene["slots"]["chips"] = ["x" * 19]
    assert slot_errors(scene)
    scene["slots"]["chips"] = []
    assert slot_errors(scene)


def test_text_slots_have_max_lengths() -> None:
    scene = example("photo_pan")
    scene["slots"]["headline"] = "x" * 41
    assert slot_errors(scene)
    scene = example("cta_endcard")
    scene["slots"]["cta"] = "x" * 41
    assert slot_errors(scene)


@pytest.mark.parametrize("bad", ["  leading", "trailing ", "two\nlines", "tab\there"])
def test_text_slots_are_single_trimmed_lines(bad: str) -> None:
    scene = example("text_card")
    scene["slots"]["headline"] = bad
    assert slot_errors(scene)


def test_swatch_colours_are_hex() -> None:
    scene = example("swatches")
    scene["slots"]["swatches"][0]["color"] = "white"
    assert slot_errors(scene)
    scene = example("swatches")
    scene["slots"]["highlight"] = 9
    assert slot_errors(scene)  # highlight must index an existing swatch


def test_focus_is_a_unit_square_point() -> None:
    scene = example("photo_pan")
    scene["slots"]["focus"] = {"x": 1.2, "y": 0.5}
    assert slot_errors(scene)


def test_kind_must_be_known() -> None:
    assert slot_errors({"kind": "video_clip", "slots": {}})


def test_a_full_scene_object_validates() -> None:
    scene = {
        "id": "sc1",
        "type": "broll",
        "description": "Hook",
        "start_seconds": 0,
        "end_seconds": 5,
        "role": "hook",
        **copy.deepcopy(example("photo_reveal")),
    }
    assert slot_errors(scene) == []
