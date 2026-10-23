"""Text fitting from the real glyph widths of the bundled fonts."""

from __future__ import annotations

import pytest

from koveriq.textfit import fit_text, text_width, wrap

HEAD = ("Playfair Display", 900)
BODY = ("Montserrat", 700)


def test_width_scales_with_size_and_case() -> None:
    small = text_width("Shutters", *BODY, px=20)
    big = text_width("Shutters", *BODY, px=40)
    assert big == pytest.approx(small * 2)
    assert text_width("SHUTTERS", *BODY, px=40) > big
    assert text_width("Shutters", *BODY, px=40, letter_spacing_em=0.2) > big


def test_known_glyph_widths_are_used() -> None:
    # Montserrat 700: "M" is 0.955 em, "i" is much narrower.
    assert text_width("M", *BODY, px=100) == pytest.approx(95.5)
    assert text_width("i", *BODY, px=100) < 40


def test_unknown_characters_fall_back_to_the_face_average() -> None:
    assert text_width("中", *BODY, px=100) > 0


def test_wrap_breaks_on_spaces_within_the_box() -> None:
    lines = wrap("Made for every window in your home", *HEAD, px=90, box_w=700)
    assert len(lines) > 1
    assert " ".join(lines) == "Made for every window in your home"
    for line in lines:
        assert text_width(line, *HEAD, px=90) <= 700


def test_short_text_keeps_the_base_size() -> None:
    fit = fit_text("Light, your way.", family=HEAD[0], weight=HEAD[1], box_w=860, max_lines=2, base_px=92, min_px=56)
    assert fit.px == 92 and fit.fits and len(fit.lines) == 1


def test_long_text_shrinks_but_stays_within_max_lines() -> None:
    text = "Made to measure for every window in your home"
    fit = fit_text(text, family=HEAD[0], weight=HEAD[1], box_w=860, max_lines=2, base_px=92, min_px=40)
    assert fit.fits and fit.px < 92 and len(fit.lines) <= 2


def test_text_that_cannot_fit_reports_it() -> None:
    fit = fit_text("x" * 60, family=HEAD[0], weight=HEAD[1], box_w=300, max_lines=1, base_px=92, min_px=60)
    assert not fit.fits and fit.px == 60


def test_uppercase_is_measured_in_capitals() -> None:
    lower = fit_text("offer ends soon", family="Montserrat", weight=900, box_w=500, max_lines=1, base_px=80, min_px=20)
    upper = fit_text("offer ends soon", family="Montserrat", weight=900, box_w=500, max_lines=1, base_px=80, min_px=20, uppercase=True)
    assert upper.px < lower.px
    # Measured in capitals, returned in the original casing (CSS uppercases).
    assert upper.lines == ["offer ends soon"]


def test_lines_keep_the_original_casing_when_wrapped_in_capitals() -> None:
    fit = fit_text("Straße und Weg straße", family="Montserrat", weight=900, box_w=420, max_lines=3, base_px=60, min_px=60, uppercase=True)
    assert " ".join(fit.lines) == "Straße und Weg straße"
    assert len(fit.lines) > 1


def test_unknown_face_is_an_error() -> None:
    with pytest.raises(KeyError):
        text_width("x", "Comic Sans MS", 400, px=10)
