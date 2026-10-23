"""The end card: an optional website, and a CTA of up to 120 characters that
always appears in full (lane W3)."""

from __future__ import annotations

import json
import re

import pytest

from koveriq.compose import FORMATS, STYLES, CompositionError, apply_params, build_composition
from koveriq.layout import MIN_TEXT_PX, SIZES
from koveriq.scenes import slot_errors
from koveriq.tests.fixtures import brand, make_assets, plan_for

KINDS = ["photo_reveal", "option_chips", "cta_endcard"]
_CTA_WORDS = (
    "Book your free, no-obligation home survey today and get 15% off made-to-measure "
    "plantation shutters for every window in your home this autumn"
).split()


def cta_of(length: int) -> str:
    """A realistic CTA of exactly `length` characters (whole words, then dots)."""
    out = ""
    for word in _CTA_WORDS:
        if len(f"{out} {word}".strip()) > length:
            break
        out = f"{out} {word}".strip()
    return (out + "." * length)[:length]


def _end_card(tmp_path, *, style="clean", fmt="16:9", brand_kit=None, cta=None, photo=True):
    plan, script, timings = plan_for(KINDS)
    slots = plan["scenes"][-1]["slots"]
    if cta is not None:
        slots["cta"] = cta
    if not photo:
        slots.pop("assetId")
    out = tmp_path / f"comp-{style}-{fmt.replace(':', 'x')}"
    result = build_composition(
        plan, script, timings, make_assets(tmp_path), style, fmt, brand_kit or brand(), out
    )
    return result, (out / "compositions" / "sc3.html").read_text(encoding="utf-8")


def _element(html: str, el_id: str) -> re.Match | None:
    return re.search(rf'<[a-z0-9]+ class="[^"]*" id="{el_id}" style="font-size:(\d+)px;width:(\d+)px">(.*?)</', html)


# --------------------------------------------------------------------------- website


@pytest.mark.parametrize("website", [None, ""], ids=["null", "empty"])
def test_a_brand_without_a_website_builds(tmp_path, website) -> None:
    kit = {"companyName": "Shutters Factory", "website": website}
    result, end = _end_card(tmp_path, brand_kit=kit)
    assert result.duration_ms == 15000
    assert 'id="sc3-pill"' not in end and 'id="sc3-url"' not in end
    assert '"#sc3-pill"' not in end  # no tween targets a missing element
    assert "Shutters Factory" in end  # the lock-up still closes the card


def test_a_missing_website_key_is_the_same_as_none(tmp_path) -> None:
    _, end = _end_card(tmp_path, brand_kit={"companyName": "Shutters Factory"})
    assert 'id="sc3-pill"' not in end


def test_the_website_is_kept_when_present(tmp_path) -> None:
    _, end = _end_card(tmp_path, brand_kit={"companyName": "X", "website": "https://www.example.co.uk/"})
    assert 'id="sc3-pill"' in end and 'id="sc3-url"' in end
    assert "www.example.co.uk<" in end  # scheme and trailing slash stripped for display
    assert '"#sc3-pill"' in end


@pytest.mark.parametrize("website", ["shutters factory.co.uk", "x" * 81, " padded.co.uk", 42])
def test_a_present_website_must_still_be_one_short_line(tmp_path, website) -> None:
    with pytest.raises(CompositionError, match="brand.website"):
        _end_card(tmp_path, brand_kit={"companyName": "X", "website": website})


def test_without_a_website_the_lockup_takes_the_pill_slot(tmp_path) -> None:
    """The lock-up pops in where the pill would, so the card does not end on a gap."""
    _, with_site = _end_card(tmp_path / "a")
    _, without = _end_card(tmp_path / "b", brand_kit={"companyName": "Shutters Factory"})
    pill_at = re.search(r'tl\.fromTo\("#sc3-pill", \{[^}]*\}, \{[^}]*\}, ([0-9.]+)\);', with_site).group(1)
    brand_tween = re.search(r'tl\.fromTo\("#sc3-brand", (\{[^}]*\}), \{[^}]*\}, ([0-9.]+)\);', without)
    assert brand_tween is not None
    assert float(brand_tween.group(2)) == pytest.approx(float(pill_at))
    assert "scale" in brand_tween.group(1)  # the pill's pop, not a plain fade


def test_apply_params_rebuilds_a_card_without_a_website(tmp_path) -> None:
    plan, script, timings = plan_for(KINDS)
    out = tmp_path / "comp"
    build_composition(plan, script, timings, make_assets(tmp_path), "clean", "9:16", {"companyName": "X"}, out)
    saved = json.loads((out / ".koveriq" / "build.json").read_text(encoding="utf-8"))
    assert saved["brand"]["website"] is None
    apply_params(out, {"scenes": {"sc3": {"font_scale": 0.9}}})
    assert 'id="sc3-pill"' not in (out / "compositions" / "sc3.html").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- CTA length


def test_the_cta_slot_takes_the_contracts_120_characters() -> None:
    assert slot_errors({"kind": "cta_endcard", "slots": {"cta": cta_of(120)}}) == []
    too_long = slot_errors({"kind": "cta_endcard", "slots": {"cta": cta_of(120) + "x"}})
    assert too_long and "cta" in too_long[0]


@pytest.mark.parametrize("style", sorted(STYLES))
@pytest.mark.parametrize("fmt", sorted(FORMATS))
@pytest.mark.parametrize("photo", [True, False], ids=["photo", "plain"])
@pytest.mark.parametrize("length", [40, 80, 120])
def test_the_full_cta_always_appears(tmp_path, style, fmt, photo, length) -> None:
    cta = cta_of(length)
    result, end = _end_card(tmp_path, style=style, fmt=fmt, cta=cta, photo=photo)
    match = _element(end, "sc3-cta")
    assert match, "no CTA element"
    px, lines = int(match.group(1)), match.group(3).split("<br>")
    assert " ".join(lines) == cta.replace("&", "&amp;")  # every word, in order, nothing cut
    assert not [w for w in result.lint_warnings if w.startswith("text_fit:sc3.cta")]
    frame_name = {"16:9": "landscape", "9:16": "portrait", "1:1": "square"}[fmt]
    # Never under the phone floor; a realistic CTA never under 40% of the base size
    # (the ladder's legible floor is 45%; four lines may go a little under it).
    assert px >= max(MIN_TEXT_PX, round(SIZES[frame_name]["cta"] * 0.4))
    if length <= 40:
        assert len(lines) <= 2
    assert len(lines) <= 4


@pytest.mark.parametrize("style", sorted(STYLES))
@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_two_lines_are_preferred_while_they_stay_legible(tmp_path, style, fmt) -> None:
    """Up to two lines, shrinking in steps; a third line only when two would fall
    below the legible CTA size (45% of the base size)."""
    _, end = _end_card(tmp_path, style=style, fmt=fmt, cta=cta_of(40))
    assert len(_element(end, "sc3-cta").group(3).split("<br>")) <= 2
    if style == "clean":  # Playfair is narrow enough for 80 characters on two lines
        _, end = _end_card(tmp_path / "80", style=style, fmt=fmt, cta=cta_of(80))
        assert len(_element(end, "sc3-cta").group(3).split("<br>")) == 2


def test_an_unbreakable_cta_still_appears_in_full_with_a_warning(tmp_path) -> None:
    cta = "W" * 40 + " " + "M" * 40 + " " + "W" * 38
    result, end = _end_card(tmp_path, style="bold_offer", fmt="9:16", cta=cta)
    lines = _element(end, "sc3-cta").group(3).split("<br>")
    assert " ".join(lines) == cta
    assert any(w.startswith("text_fit:sc3.cta") for w in result.lint_warnings)
