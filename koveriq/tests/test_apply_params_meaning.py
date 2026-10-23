"""shorten_text may drop words, but never in a way that changes the claim.

Dropping words cannot add a fact, but it can still change the meaning: drop
a negation ("No cords" -> "cords"), a qualifier ("Up to 15% off" -> "15% off"),
part of a range ("47mm to 89mm" -> "47mm"), or the exclusions from offer
terms. The CTA must stay brief.cta word for word (spec §8.5).
"""

from __future__ import annotations

import pytest

from koveriq.compose import CompositionError, apply_params, build_composition
from koveriq.tests.fixtures import brand, make_assets, plan_for


@pytest.fixture()
def comp(tmp_path):
    plan, script, timings = plan_for(["text_card", "photo_pan", "offer_card", "town_card", "cta_endcard"])
    plan["scenes"][0]["slots"].update(headline="Child safe, no cords", subline="Free fitting, except the Highlands")
    plan["scenes"][1]["slots"].update(
        headline="47mm to 89mm louvres in white",
        overline="No cords. No chains.",
        subline="Up to 15% off all made-to-measure shutters",
    )
    build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), tmp_path / "comp")
    return tmp_path / "comp"


@pytest.mark.parametrize(
    "scene, slot, text",
    [
        ("sc5", "cta", "Book your survey"),
        ("sc3", "offer", "15% off shutters"),
        ("sc3", "terms", "Ends November"),
        ("sc3", "badge", "Limited"),
        ("sc4", "town", "Harro"),
    ],
)
def test_fact_slots_cannot_be_shortened(comp, scene: str, slot: str, text: str) -> None:
    with pytest.raises(CompositionError, match="cannot be shortened"):
        apply_params(comp, {"scenes": {scene: {"shorten_text": {slot: text}}}})


@pytest.mark.parametrize(
    "slot, text, message",
    [
        ("headline", "Child safe", "negation"),
        ("subline", "Free fitting", "qualifier"),
    ],
)
def test_negations_and_qualifiers_must_stay(comp, slot: str, text: str, message: str) -> None:
    with pytest.raises(CompositionError, match=message):
        apply_params(comp, {"scenes": {"sc1": {"shorten_text": {slot: text}}}})


def test_figures_stay_all_or_none(comp) -> None:
    with pytest.raises(CompositionError, match="figures"):
        apply_params(comp, {"scenes": {"sc2": {"shorten_text": {"headline": "47mm"}}}})
    apply_params(comp, {"scenes": {"sc2": {"shorten_text": {"headline": "47mm to 89mm louvres"}}}})


def test_meaning_preserving_shortening_is_allowed(comp) -> None:
    apply_params(comp, {"scenes": {"sc2": {"shorten_text": {"overline": "No cords.", "subline": "Up to 15% off"}}}})
