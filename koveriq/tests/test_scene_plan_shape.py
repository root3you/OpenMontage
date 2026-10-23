"""The scene_plan shape: inline kind/slots for the builder, metadata for checkpoints."""

from __future__ import annotations

from koveriq.scenes import (
    KIND_TO_TYPE,
    KINDS,
    from_checkpoint_scene_plan,
    scene_plan_errors,
    to_checkpoint_scene_plan,
)
from koveriq.tests.fixtures import plan_for
from schemas.artifacts import validate_artifact

KINDS_6 = ["photo_reveal", "photo_pan", "option_chips", "swatches", "text_card", "cta_endcard"]


def test_inline_plan_is_valid() -> None:
    plan, _, _ = plan_for(KINDS_6)
    assert scene_plan_errors(plan) == []


def test_checkpoint_shape_passes_the_upstream_schema_and_round_trips() -> None:
    plan, _, _ = plan_for(KINDS_6)
    stored = to_checkpoint_scene_plan(plan)
    validate_artifact("scene_plan", stored)  # raises if invalid
    assert "kind" not in stored["scenes"][0]
    assert stored["metadata"]["koveriq"]["scenes"]["sc1"]["kind"] == "photo_reveal"
    assert from_checkpoint_scene_plan(stored) == {**plan, "metadata": stored["metadata"]}
    assert scene_plan_errors(stored) == []


def test_inline_keys_fail_the_upstream_schema_which_is_why_the_helper_exists() -> None:
    import jsonschema
    import pytest

    plan, _, _ = plan_for(KINDS_6)
    with pytest.raises(jsonschema.ValidationError):
        validate_artifact("scene_plan", plan)


def test_errors_name_the_scene() -> None:
    plan, _, _ = plan_for(KINDS_6)
    plan["scenes"][2]["slots"]["chips"] = []
    plan["scenes"][3]["id"] = "sc1"
    errors = scene_plan_errors(plan)
    assert any(e.startswith("sc3.slots.chips") for e in errors)
    assert "sc1: duplicate scene id" in errors


def test_every_kind_maps_to_an_upstream_scene_type() -> None:
    from schemas.artifacts import load_schema

    allowed = set(load_schema("scene_plan")["properties"]["scenes"]["items"]["properties"]["type"]["enum"])
    assert set(KIND_TO_TYPE) == set(KINDS)
    assert set(KIND_TO_TYPE.values()) <= allowed
