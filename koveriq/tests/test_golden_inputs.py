"""The golden inputs are valid and build cleanly (no browser needed)."""

from __future__ import annotations

from koveriq import golden
from koveriq.compose import build_composition
from koveriq.grammar import grammar_errors, infer_roles
from koveriq.scenes import scene_plan_errors


def test_golden_scene_plan_is_valid_and_follows_the_grammar() -> None:
    data = golden.inputs()
    assert scene_plan_errors(data["scene_plan"]) == []
    total = golden.expected()["durationMs"] / 1000
    assert grammar_errors(data["scene_plan"], "product_promo", 30, total_seconds=total) == []
    assert infer_roles(data["scene_plan"], "product_promo") == ["hook", "product", "options", "benefit", "benefit", "cta"]


def test_golden_builds_with_the_expected_timeline_and_no_warnings(tmp_path) -> None:
    exp = golden.expected()
    result = build_composition(**golden.inputs(), style=exp["style"], fmt=exp["fmt"], out_dir=tmp_path / "golden")
    assert result.duration_ms == exp["durationMs"]
    assert result.hook_time_ms == exp["hookTimeMs"]
    assert result.lint_warnings == []
    index = result.index_html.read_text(encoding="utf-8")
    assert 'src="assets/audio/narration.m4a"' in index


def test_golden_beats_follow_the_narration(tmp_path) -> None:
    """Step items appear on the words that name them (Tilt / Close / Total)."""
    exp = golden.expected()
    data = golden.inputs()
    result = build_composition(**data, style=exp["style"], fmt=exp["fmt"], out_dir=tmp_path / "golden")
    scene = (result.index_html.parent / "compositions" / "sc5.html").read_text(encoding="utf-8")
    start = data["timings"]["sc5"]["startMs"]
    spoken = {w["w"].strip(".,").lower(): (w["startMs"] - start) / 1000 for w in data["timings"]["sc5"]["words"]}

    def appears_at(i: int) -> float:
        line = scene.split(f'tl.fromTo("#sc5-step{i}"')[1].split("\n")[0]
        return float(line.rsplit(", ", 1)[1].rstrip(");"))

    # "Tilt" is spoken before the title has entered, so step 1 waits for it;
    # the later steps land 80 ms before the words that name them.
    assert spoken["tilt"] < 0.5 and appears_at(1) <= 1.2
    for i, word in ((2, "close"), (3, "total")):
        assert appears_at(i) == round(spoken[word] - 0.08, 3)
