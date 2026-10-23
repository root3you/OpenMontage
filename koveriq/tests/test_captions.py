"""Burned-in captions (lane W3): build_composition(..., captions=True) adds a
caption sub-composition driven by the narration's word timings and keeps the
scenes' text out of the caption band."""

from __future__ import annotations

import inspect
import json
import re

import pytest

from koveriq import captions as caps
from koveriq.compose import FORMATS, STYLES, CompositionError, apply_params, build_composition
from koveriq.layout import FRAMES
from koveriq.tests.fixtures import brand, make_assets, plan_for

KINDS = ["photo_reveal", "photo_pan", "option_chips", "text_card", "cta_endcard"]


def _words(start_ms: int, text: str, *, gap_after: dict[int, int] | None = None, step: int = 320) -> list[dict]:
    out, t = [], start_ms
    for i, w in enumerate(text.split()):
        out.append({"w": w, "startMs": t, "endMs": t + step - 40})
        t += step + (gap_after or {}).get(i, 0)
    return out


def _build(tmp_path, *, style="clean", fmt="16:9", on=True, kinds=None, name="comp"):
    plan, script, timings = plan_for(kinds or KINDS)
    out = tmp_path / name
    result = build_composition(
        plan, script, timings, make_assets(tmp_path), style, fmt, brand(), out, captions=on
    )
    return result, out, timings


def _read(path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- the API


def test_captions_is_a_keyword_only_option_off_by_default() -> None:
    param = inspect.signature(build_composition).parameters["captions"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY and param.default is False


def test_captions_must_be_a_boolean(tmp_path) -> None:
    with pytest.raises(CompositionError, match="captions"):
        _build(tmp_path, on="yes")


def test_captions_is_a_reserved_scene_id(tmp_path) -> None:
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    plan["scenes"][0]["id"] = "captions"
    timings["captions"] = timings.pop("sc1")
    with pytest.raises(CompositionError, match="captions"):
        build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), tmp_path / "c")


# --------------------------------------------------------------------------- grouping


def test_groups_are_two_or_three_words_and_break_at_sentences_and_pauses() -> None:
    words = _words(0, "Light when you want it, privacy when you need it. Made to measure for every window.")
    groups = caps.group_words(words, fits=lambda text: True)
    texts = [" ".join(w["w"] for w in g) for g in groups]
    assert texts == [
        "Light when you",
        "want it,",
        "privacy when you",
        "need it.",
        "Made to measure",
        "for every window.",
    ]
    assert all(1 <= len(g) <= 4 for g in groups)


def test_a_pause_of_150_ms_or_more_starts_a_new_group() -> None:
    words = _words(0, "Tilt the louvres for light", gap_after={1: 200})
    texts = [" ".join(w["w"] for w in g) for g in caps.group_words(words, fits=lambda text: True)]
    assert texts == ["Tilt the", "louvres for light"]


def test_a_sentences_last_word_may_join_a_full_group_rather_than_sit_alone() -> None:
    words = _words(0, "Fitted by our own team.")
    texts = [" ".join(w["w"] for w in g) for g in caps.group_words(words, fits=lambda text: True)]
    assert texts == ["Fitted by our", "own team."]
    words = _words(0, "Made for every window.")
    texts = [" ".join(w["w"] for w in g) for g in caps.group_words(words, fits=lambda text: True)]
    assert texts == ["Made for every window."]


def test_a_group_never_grows_wider_than_the_caption_box() -> None:
    words = _words(0, "Extraordinarily beautiful handcrafted shutters")
    groups = caps.group_words(words, fits=lambda text: len(text) <= 26)
    assert [" ".join(w["w"] for w in g) for g in groups] == [
        "Extraordinarily beautiful",
        "handcrafted shutters",
    ]


def test_display_text_drops_trailing_commas_and_full_stops_only() -> None:
    assert caps.display_text(["want", "it,"]) == "want it"
    assert caps.display_text(["for", "every", "window."]) == "for every window"
    assert caps.display_text(["Ready", "to", "start?"]) == "Ready to start?"
    assert caps.display_text(["15%", "off!"]) == "15% off!"


# --------------------------------------------------------------------------- timing


def test_cues_never_overlap_never_cross_a_scene_and_hold_a_minimum() -> None:
    timings = {
        "sc1": {"startMs": 0, "endMs": 3000, "words": _words(60, "Light your way. Every window.")},
        "sc2": {"startMs": 3000, "endMs": 6000, "words": _words(3050, "Made to measure.")},
    }
    plan = [{"id": "sc1", "kind": "photo_pan"}, {"id": "sc2", "kind": "text_card"}]
    cues = caps.build_cues(plan, timings, fits=lambda text: True)
    assert [c.text for c in cues] == ["Light your way", "Every window", "Made to measure"]
    assert cues[0].start >= 0.1  # a caption at exactly 0 s looks pre-existing
    for cue in cues:
        assert cue.end - cue.start >= caps.MIN_SHOW - 1e-9
    for a, b in zip(cues, cues[1:]):
        assert a.end <= b.start + 1e-9
    assert cues[1].end <= 3.0 and cues[2].start >= 3.0
    assert cues[0].scene == "sc1" and cues[2].scene == "sc2"


def test_the_end_card_is_not_captioned() -> None:
    """The end card shows the CTA word for word: captions would print it twice."""
    timings = {
        "sc1": {"startMs": 0, "endMs": 3000, "words": _words(100, "Light your way.")},
        "sc2": {"startMs": 3000, "endMs": 6000, "words": _words(3100, "Book your free home survey.")},
    }
    plan = [{"id": "sc1", "kind": "photo_pan"}, {"id": "sc2", "kind": "cta_endcard"}]
    cues = caps.build_cues(plan, timings, fits=lambda text: True)
    assert [c.scene for c in cues] == ["sc1"]


def test_words_outside_their_scene_are_not_captioned() -> None:
    words = _words(100, "Light your way.") + [{"w": "stray", "startMs": 9000, "endMs": 9300}]
    cues = caps.build_cues([{"id": "sc1", "kind": "photo_pan"}], {"sc1": {"startMs": 0, "endMs": 3000, "words": words}}, fits=lambda t: True)
    assert [c.text for c in cues] == ["Light your way"]


# --------------------------------------------------------------------------- the composition


@pytest.mark.parametrize("style", sorted(STYLES))
@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_captions_on_adds_one_captions_track(tmp_path, style, fmt) -> None:
    result, out, _ = _build(tmp_path, style=style, fmt=fmt)
    index = _read(result.index_html)
    host = re.search(r'<div id="captions"[^>]*>', index).group(0)
    assert 'data-composition-src="compositions/captions.html"' in host
    assert 'data-track-kind="captions"' in host and 'data-start="0"' in host
    assert f'data-duration="{result.duration_ms / 1000:g}"' in host
    # Painted last: the captions host follows every scene and the corner mark.
    assert index.index('id="captions"') > index.index('id="brand"')
    page = _read(out / "compositions" / "captions.html")
    assert page.lstrip().startswith("<template>") and 'data-composition-id="captions"' in page
    assert 'window.__timelines["captions"] = tl;' in page
    groups = re.findall(r'<div class="k-cap" id="(captions-g\d+)">', page)
    assert groups
    for gid in groups:  # every group is shown, faded and hard-killed
        assert f'tl.set("#{gid}", {{ visibility: "visible" }}' in page
        assert f'tl.set("#{gid}", {{ visibility: "hidden" }}' in page
    sizes = [int(px) for px in re.findall(r"font-size:(\d+)px", page)]
    assert min(sizes) >= 28


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_captions_off_changes_nothing(tmp_path, fmt) -> None:
    plan, script, timings = plan_for(KINDS)
    assets = make_assets(tmp_path)
    off = build_composition(plan, script, timings, assets, "clean", fmt, brand(), tmp_path / "off", captions=False)
    default = build_composition(plan, script, timings, assets, "clean", fmt, brand(), tmp_path / "default")
    assert not (tmp_path / "off" / "compositions" / "captions.html").exists()
    assert 'id="captions"' not in _read(off.index_html)
    for path in sorted((tmp_path / "default" / "compositions").glob("*.html")):
        assert _read(path) == _read(tmp_path / "off" / "compositions" / path.name), path.name


def test_the_caption_text_comes_from_the_word_timings(tmp_path) -> None:
    _, out, timings = _build(tmp_path)
    page = _read(out / "compositions" / "captions.html")
    shown = " ".join(re.findall(r'<div class="k-capbox"[^>]*>([^<]*)</div>', page))
    spoken = " ".join(w["w"] for sid in ("sc1", "sc2", "sc3", "sc4") for w in timings[sid]["words"])
    assert shown.split() == [w.rstrip(",.") for w in spoken.split()]  # no end-card words
    assert "&lt;" not in shown


def test_caption_text_is_escaped(tmp_path) -> None:
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    timings["sc1"]["words"][0]["w"] = "<b>Bold</b>&"
    out = tmp_path / "c"
    build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), out, captions=True)
    page = _read(out / "compositions" / "captions.html")
    assert "<b>" not in page and "&lt;b&gt;Bold&lt;/b&gt;&amp;" in page


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_scenes_keep_their_text_above_the_caption_band(tmp_path, fmt) -> None:
    """With captions on, every captioned scene is laid out in a frame whose
    bottom safe margin includes the caption band; the end card keeps its layout."""
    frame = FRAMES[fmt]
    band = caps.BAND[frame.name]
    _, off, _ = _build(tmp_path, fmt=fmt, on=False, name="off")
    _, on, _ = _build(tmp_path, fmt=fmt, on=True, name="on")
    pan_on = _read(on / "compositions" / "sc2.html")
    assert f"bottom:{frame.pad_bottom + band.height}px" in pan_on  # photo_pan card lifted
    assert f"bottom:{frame.pad_bottom}px" in _read(off / "compositions" / "sc2.html")
    text_on = _read(on / "compositions" / "sc4.html")
    assert f"height: {frame.safe_h - band.height}px" in text_on
    assert _read(on / "compositions" / "sc5.html") == _read(off / "compositions" / "sc5.html")
    page = _read(on / "compositions" / "captions.html")
    assert f"top: {frame.h - frame.pad_bottom - band.height}px; height: {band.height}px;" in page


def test_portrait_photo_reveal_moves_up_with_the_band(tmp_path) -> None:
    _, off, _ = _build(tmp_path, fmt="9:16", on=False, name="off")
    _, on, _ = _build(tmp_path, fmt="9:16", on=True, name="on")
    shift = caps.BAND["portrait"].height
    assert "top:1130px;width:912px;height:360px" in _read(off / "compositions" / "sc1.html")
    assert f"top:{1130 - shift}px;width:912px;height:360px" in _read(on / "compositions" / "sc1.html")


@pytest.mark.parametrize("style", sorted(STYLES))
def test_each_style_has_its_own_caption_look(tmp_path, style) -> None:
    _, out, _ = _build(tmp_path, style=style)
    page = _read(out / "compositions" / "captions.html")
    rule = re.search(r"\.k-capbox \{[^}]*\}", page).group(0)
    if style == "clean":
        assert '"Montserrat"' in rule and "font-weight: 700" in rule and "text-transform: none" in rule
        assert "rgba(251,248,242,0.94)" in rule  # the paper surface, slightly see-through
    else:
        assert "font-weight: 900" in rule and "text-transform: uppercase" in rule
        assert "rgba(20,22,27,0.86)" in rule and "inset 0 -6px 0" in rule  # dark scrim, accent edge


def test_no_words_means_no_caption_layer_and_a_warning(tmp_path) -> None:
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    for timing in timings.values():
        timing["words"] = []
    out = tmp_path / "c"
    result = build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), out, captions=True)
    assert not (out / "compositions" / "captions.html").exists()
    assert any(w.startswith("captions_empty:") for w in result.lint_warnings)
    assert "bottom:110px" in _read(out / "compositions" / "sc1.html") or "height: 830px" in _read(out / "compositions" / "sc1.html")


def test_apply_params_keeps_the_captions(tmp_path) -> None:
    _, out, _ = _build(tmp_path)
    saved = json.loads(_read(out / ".koveriq" / "build.json"))
    assert saved["captions"] is True
    apply_params(out, {"scenes": {"sc2": {"font_scale": 0.9}}})
    assert (out / "compositions" / "captions.html").is_file()
    assert 'id="captions"' in _read(out / "index.html")


def test_the_build_is_still_deterministic_with_captions(tmp_path) -> None:
    plan, script, timings = plan_for(KINDS)
    assets = make_assets(tmp_path)
    for name in ("a", "b"):
        build_composition(plan, script, timings, assets, "bold_offer", "9:16", brand(), tmp_path / name, captions=True)
    a = _read(tmp_path / "a" / "compositions" / "captions.html")
    assert a == _read(tmp_path / "b" / "compositions" / "captions.html")


# --------------------------------------------------------------------------- edges


def test_blank_words_are_skipped() -> None:
    words = _words(0, "Made to measure.")
    words.insert(1, {"w": "  ", "startMs": 300, "endMs": 310})
    groups = caps.group_words(words, fits=lambda text: True)
    assert [" ".join(w["w"] for w in g) for g in groups] == ["Made to measure."]


def test_a_group_opening_late_still_stays_up_long_enough() -> None:
    """A word in the first 0.1 s opens at 0.1 s and still holds MIN_SHOW."""
    timings = {"sc1": {"startMs": 0, "endMs": 3000, "words": [{"w": "Hi", "startMs": 0, "endMs": 20}]}}
    cues = caps.build_cues([{"id": "sc1", "kind": "text_card"}], timings, fits=lambda t: True)
    assert [(c.start, c.end) for c in cues] == [(0.1, 0.1 + caps.MIN_SHOW)]


def test_a_word_at_the_very_end_of_a_scene_is_not_captioned() -> None:
    words = _words(100, "Light.") + [{"w": "late", "startMs": 3000, "endMs": 3040}]
    timings = {"sc1": {"startMs": 0, "endMs": 3000, "words": words}}
    cues = caps.build_cues([{"id": "sc1", "kind": "text_card"}], timings, fits=lambda t: True)
    assert [c.text for c in cues] == ["Light"]


def test_a_single_word_too_long_for_the_box_is_shown_with_a_warning(tmp_path) -> None:
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    timings["sc1"]["words"][0]["w"] = "Pneumonoultramicroscopicsilicovolcanoconiosis-Pneumono"
    out = tmp_path / "c"
    result = build_composition(plan, script, timings, make_assets(tmp_path), "clean", "9:16", brand(), out, captions=True)
    assert any(w.startswith("text_fit:captions.g1") for w in result.lint_warnings)
    assert "Pneumonoultramicroscopicsilicovolcanoconiosis-Pneumono" in _read(out / "compositions" / "captions.html")


def test_a_cue_too_short_for_both_fades_is_cut_not_faded() -> None:
    """Two fades on one opacity inside a few frames flicker: a short cue fades in
    within its span and is hard-cut (visibility hidden) instead of faded out."""
    cues = [caps.Cue("sc1", 1.0, 1.2, "Hi"), caps.Cue("sc1", 1.2, 2.0, "there my friend")]
    lines = caps.tweens(cues, ["g1", "g2"]).lines
    short = [line for line in lines if '"#g1"' in line]
    assert not any(line.startswith('tl.to("#g1"') for line in short)
    assert 'duration: 0.14' in next(line for line in short if line.startswith("tl.fromTo"))
    assert short[-1] == 'tl.set("#g1", { visibility: "hidden" }, 1.2);'
    tiny = caps.tweens([caps.Cue("sc1", 3.0, 3.06, "Oh")], ["g3"]).lines
    assert "duration: 0.06" in next(line for line in tiny if line.startswith("tl.fromTo"))
    full = [line for line in lines if '"#g2"' in line]
    assert any(line.startswith('tl.to("#g2", { opacity: 0, duration: 0.12') for line in full)


def test_a_word_running_past_the_cut_is_still_captioned() -> None:
    """A word belongs to the scene it starts in (as for beats); its caption
    closes at the cut."""
    words = _words(2400, "Light your way.")  # "way." ends at 3.0 + 0.04 s
    words[-1]["endMs"] = 3100
    timings = {"sc1": {"startMs": 0, "endMs": 3000, "words": words}}
    cues = caps.build_cues([{"id": "sc1", "kind": "text_card"}], timings, fits=lambda t: True)
    assert [c.text for c in cues] == ["Light your way"]
    assert cues[0].end == pytest.approx(3.0 - caps.EDGE)
