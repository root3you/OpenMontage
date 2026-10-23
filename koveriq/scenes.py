"""Scene kinds, slot validation and the scene_plan shape the worker writes.

A KoverIQ scene is an OpenMontage `scene_plan` scene plus three keys:

- `kind`: one of the ten template kinds (`KINDS`)
- `slots`: the kind's typed slots (`scene_kinds.schema.json`)
- `role` (optional): its place in the scene grammar (`scene_grammar.yaml`)

OpenMontage's `scene_plan` schema forbids extra keys on a scene, so a
checkpoint cannot carry them inline. `to_checkpoint_scene_plan` moves them into
`metadata.koveriq.scenes[<sceneId>]` (schema-valid), and
`from_checkpoint_scene_plan` puts them back. Everything in this package accepts
either shape.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import jsonschema

from schemas.artifacts import load_schema

PACKAGE_DIR = Path(__file__).resolve().parent
KIND_SCHEMA_PATH = PACKAGE_DIR / "scene_kinds.schema.json"

KINDS = (
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
)
# Kinds that always show a photo, and kinds whose photo is optional.
PHOTO_KINDS = ("photo_pan", "photo_reveal", "before_after")
OPTIONAL_PHOTO_KINDS = ("option_chips", "town_card", "cta_endcard")

# The OpenMontage scene_plan `type` that describes each kind.
KIND_TO_TYPE = {
    "photo_pan": "broll",
    "photo_reveal": "broll",
    "option_chips": "animation",
    "swatches": "animation",
    "text_card": "text_card",
    "offer_card": "text_card",
    "steps": "diagram",
    "before_after": "broll",
    "town_card": "text_card",
    "cta_endcard": "text_card",
}

# Single-line text slots per kind (what `shorten_text` may target).
TEXT_SLOTS = {
    "photo_pan": ("overline", "headline", "subline"),
    "photo_reveal": ("overline", "headline", "subline"),
    "option_chips": ("title",),
    "swatches": ("title",),
    "text_card": ("overline", "headline", "subline"),
    "offer_card": ("overline", "offer", "terms", "badge"),
    "steps": ("title",),
    "before_after": ("beforeLabel", "afterLabel", "headline"),
    "town_card": ("overline", "town", "subline"),
    "cta_endcard": ("overline", "cta"),
}

EXTENSION_KEYS = ("kind", "slots", "role")


class ScenePlanError(ValueError):
    """A scene plan, slot or timing problem. `errors` lists every problem found."""

    def __init__(self, errors: Iterable[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors) if self.errors else "invalid scene plan")


@lru_cache(maxsize=1)
def load_kind_schema() -> dict[str, Any]:
    with open(KIND_SCHEMA_PATH, encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _kind_validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(load_kind_schema())


def _format_error(prefix: str, error: jsonschema.ValidationError) -> str:
    path = ".".join(str(p) for p in error.absolute_path)
    where = f"{prefix}.{path}" if prefix and path else (prefix or path or "scene")
    return f"{where}: {error.message}"


def slot_errors(scene: dict[str, Any], *, prefix: str = "") -> list[str]:
    """Every problem with a scene's kind and slots (empty list when valid)."""
    if not isinstance(scene, dict):
        return [f"{prefix or 'scene'}: must be an object"]
    errors = sorted(
        (_format_error(prefix, e) for e in _kind_validator().iter_errors(scene)),
    )
    if errors:
        return errors
    slots = scene["slots"]
    where = f"{prefix}.slots" if prefix else "slots"
    if scene["kind"] == "swatches" and "highlight" in slots:
        if slots["highlight"] >= len(slots["swatches"]):
            errors.append(f"{where}.highlight: {slots['highlight']} does not index one of the swatches")
    for key in ("chips", "steps"):
        items = slots.get(key)
        if isinstance(items, list) and len({i.casefold() for i in items}) != len(items):
            errors.append(f"{where}.{key}: items must be unique")
    return errors


def scene_asset_ids(scene: dict[str, Any]) -> list[str]:
    """Asset ids a scene's slots reference, in slot order."""
    slots = scene.get("slots") or {}
    ids = [slots[k] for k in ("assetId", "beforeAssetId", "afterAssetId") if slots.get(k)]
    return ids


def scene_has_photo(scene: dict[str, Any]) -> bool:
    return bool(scene_asset_ids(scene))


def from_checkpoint_scene_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with `kind`/`slots`/`role` inline on every scene.

    Accepts a plan that already has them inline, or the checkpoint shape that
    keeps them in `metadata.koveriq.scenes`. Inline keys win.
    """
    plan = copy.deepcopy(plan)
    stored = ((plan.get("metadata") or {}).get("koveriq") or {}).get("scenes") or {}
    for scene in plan.get("scenes") or []:
        extra = stored.get(scene.get("id")) or {}
        for key in EXTENSION_KEYS:
            if key not in scene and key in extra:
                scene[key] = extra[key]
    return plan


def to_checkpoint_scene_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Return a copy that validates against OpenMontage's scene_plan schema.

    `kind`, `slots` and `role` move into `metadata.koveriq.scenes[<sceneId>]`.
    """
    plan = from_checkpoint_scene_plan(plan)
    stored: dict[str, Any] = {}
    for scene in plan.get("scenes") or []:
        extra = {key: scene.pop(key) for key in EXTENSION_KEYS if key in scene}
        if extra:
            stored[scene.get("id")] = extra
    metadata = plan.setdefault("metadata", {})
    metadata.setdefault("koveriq", {})["scenes"] = stored
    return plan


def scene_plan_errors(plan: dict[str, Any]) -> list[str]:
    """OpenMontage scene_plan schema + KoverIQ kind/slot checks for every scene."""
    if not isinstance(plan, dict):
        return ["scene_plan: must be an object"]
    inline = from_checkpoint_scene_plan(plan)
    errors: list[str] = []
    upstream = jsonschema.Draft202012Validator(load_schema("scene_plan"))
    for error in upstream.iter_errors(to_checkpoint_scene_plan(inline)):
        errors.append(_format_error("scene_plan", error))
    seen: set[str] = set()
    for index, scene in enumerate(inline.get("scenes") or []):
        if not isinstance(scene, dict):
            continue
        sid = scene.get("id") or f"scenes[{index}]"
        if sid in seen:
            errors.append(f"{sid}: duplicate scene id")
        seen.add(sid)
        errors.extend(slot_errors(scene, prefix=str(sid)))
    return errors
