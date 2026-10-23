"""koveriq/scene_grammar.yaml and the grammar check."""

from __future__ import annotations

import pytest

from koveriq.grammar import grammar_errors, infer_roles, load_grammar
from koveriq.scenes import KINDS
from koveriq.tests.fixtures import plan_for

PROMO = "product_promo"
GOOD_30 = ["photo_reveal", "photo_pan", "option_chips", "swatches", "text_card", "cta_endcard"]


def test_product_promo_grammar_order() -> None:
    grammar = load_grammar()["grammars"][PROMO]
    assert [r["role"] for r in grammar["roles"]] == [
        "hook",
        "product",
        "options",
        "benefit",
        "craft_trust",
        "cta",
    ]


def test_roles_only_name_known_kinds() -> None:
    for name, grammar in load_grammar()["grammars"].items():
        for role in grammar["roles"]:
            assert set(role["kinds"]) <= set(KINDS), (name, role["role"])
            assert 0 <= role["min"] <= role["max"]


@pytest.mark.parametrize("target", [20, 30, 45, 60])
def test_length_bounds_exist_and_word_bounds_follow_the_pace_rule(target: int) -> None:
    grammar = load_grammar()
    bounds = grammar["grammars"][PROMO]["lengths"][str(target)]
    pace = grammar["words_per_second"]
    assert (pace["min"], pace["max"]) == (2.3, 2.7)
    assert bounds["words"]["min"] == round(target * 2.3 + 0.0001)
    assert bounds["words"]["max"] == round(target * 2.7 + 0.0001)
    assert bounds["seconds"]["min"] == pytest.approx(target * 0.8)
    assert bounds["seconds"]["max"] == pytest.approx(target * 1.4)
    assert 1 <= bounds["scenes"]["min"] <= bounds["scenes"]["max"]


def test_a_good_30s_promo_passes() -> None:
    plan, _, _ = plan_for(GOOD_30)
    assert grammar_errors(plan, PROMO, 30) == []
    assert infer_roles(plan, PROMO) == ["hook", "product", "options", "options", "benefit", "cta"]


def test_cta_must_be_last() -> None:
    plan, _, _ = plan_for(["photo_reveal", "photo_pan", "option_chips", "cta_endcard", "text_card"])
    errors = grammar_errors(plan, PROMO, 30)
    assert any("cta_endcard" in e for e in errors)


def test_options_role_is_required() -> None:
    plan, _, _ = plan_for(["photo_reveal", "photo_pan", "text_card", "text_card", "cta_endcard"])
    assert grammar_errors(plan, PROMO, 30)


def test_scene_count_must_fit_the_target_length() -> None:
    plan, _, _ = plan_for(GOOD_30)  # 6 scenes
    errors = grammar_errors(plan, PROMO, 20)  # 20 s allows at most 5
    assert any("scenes" in e for e in errors)


def test_unknown_target_length_is_rejected() -> None:
    plan, _, _ = plan_for(GOOD_30)
    assert grammar_errors(plan, PROMO, 25)


def test_explicit_roles_are_respected() -> None:
    plan, _, _ = plan_for(GOOD_30)
    plan["scenes"][4]["role"] = "craft_trust"  # text_card may be craft/trust
    assert grammar_errors(plan, PROMO, 30) == []
    plan["scenes"][4]["role"] = "hook"  # but not a second hook after the options
    assert grammar_errors(plan, PROMO, 30)


def test_kind_not_allowed_for_its_role() -> None:
    plan, _, _ = plan_for(["option_chips", "photo_pan", "option_chips", "cta_endcard"])
    assert grammar_errors(plan, PROMO, 20)


def test_unknown_video_type() -> None:
    plan, _, _ = plan_for(GOOD_30)
    with pytest.raises(KeyError):
        grammar_errors(plan, "music_video", 30)


def test_total_length_is_checked_when_known() -> None:
    plan, _, _ = plan_for(GOOD_30)
    assert grammar_errors(plan, PROMO, 30, total_seconds=30.0) == []
    assert grammar_errors(plan, PROMO, 30, total_seconds=40.0) == []  # real TTS pacing
    assert any("total length" in e for e in grammar_errors(plan, PROMO, 30, total_seconds=45.0))


def test_word_count_follows_the_pace_rule() -> None:
    from koveriq.grammar import count_words, word_count_errors

    assert count_words("They're child-safe, made to measure: 89mm.") == 6
    script = {"sections": [{"text": " ".join(["word"] * 75)}]}
    assert word_count_errors(script, PROMO, 30) == []
    script = {"sections": [{"text": " ".join(["word"] * 90)}]}
    assert word_count_errors(script, PROMO, 30)
    script = {"sections": [{"text": " ".join(["word"] * 60)}]}
    assert word_count_errors(script, PROMO, 30)
