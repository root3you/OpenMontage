"""The four template styles of the KoverIQ wizard: Clean, Bold offer,
Showroom and Minimal.

A style is a palette, the text roles the CSS and the text fitter share, a
radius, a transition and a style sheet. Every scene kind composes in every
format in every style, and the styles stay apart at a glance.
"""

from __future__ import annotations

import itertools
import re

import pytest

from koveriq import captions as caps
from koveriq.compose import FORMATS, CompositionError, build_composition
from koveriq.scenes import KINDS
from koveriq.styles import PALETTE_KEYS, STYLES, merge_palette, palette_warnings, rgba
from koveriq.textfit import text_width
from koveriq.tests.fixtures import brand, make_assets, plan_for

NEW_STYLES = ("showroom", "minimal")
ALL_STYLES = sorted({*STYLES, *NEW_STYLES})

# The faces HyperFrames 0.8.185 embeds in its CLI (CANONICAL_FONTS in its
# bundle): nothing else renders offline.
EMBEDDED_FACES = {
    "Archivo Black": {400},
    "EB Garamond": {400, 700},
    "IBM Plex Mono": {400, 700},
    "Inter": {400, 700, 900},
    "JetBrains Mono": {400, 700},
    "Lato": {400, 700, 900},
    "League Gothic": {400},
    "Montserrat": {400, 700, 900},
    "Noto Sans JP": {400, 700},
    "Nunito": {400, 700, 900},
    "Open Sans": {400, 700},
    "Oswald": {400, 700},
    "Outfit": {400, 700, 900},
    "Playfair Display": {400, 700, 900},
    "Poppins": {400, 700, 900},
    "Roboto": {400, 700, 900},
    "Source Code Pro": {400, 700},
    "Space Mono": {400, 700},
}
ROLE_CLASSES = {"over": "k-over", "head": "k-head", "big": "k-big", "sub": "k-sub", "item": "k-item", "pill": "k-pilltext", "mark": "k-mark"}
# What the kind templates take from the style sheet, and what each transition adds.
BASE_CLASSES = (
    "k-fill", "k-photo", "k-shade", "k-over", "k-head", "k-big", "k-sub", "k-item", "k-pilltext", "k-mark",
    "k-card", "k-col", "k-center", "k-rule", "k-chip", "k-num", "k-pill", "k-tag", "k-decor", "k-cover",
)  # fmt: skip
TRANSITION_CLASSES = {
    "louvres": ("k-bars", "k-bar", "k-bars-in", "k-bars-out"),
    "blocks": ("k-blocks", "k-block-a", "k-block-b"),
    "fade": ("k-veil",),
}
TRANSITION_MARKUP = {
    "louvres": 'class="k-bars k-bars-in"',
    "blocks": 'class="k-blocks"',
    "fade": 'class="k-veil k-veil-in"',
}
_FACE = re.compile(r'font-family: "([^"]+)"[^;]*; font-weight: (\d+)')


def _build(tmp_path, style, fmt="16:9", kinds=None, kit=None, captions=False):
    plan, script, timings = plan_for(list(kinds or KINDS))
    out = tmp_path / f"{style}-{fmt.replace(':', 'x')}"
    result = build_composition(plan, script, timings, make_assets(tmp_path), style, fmt, kit or brand(), out, captions=captions)
    return result, out


def _page(out, sid):
    return (out / "compositions" / f"{sid}.html").read_text(encoding="utf-8")


def _defines(page: str, cls: str) -> bool:
    return re.search(rf"\.{re.escape(cls)}(?![\w-])[^{{}}]*\{{", page) is not None


# --------------------------------------------------------------------------- tokens


def test_showroom_and_minimal_are_styles() -> None:
    assert set(NEW_STYLES) <= set(STYLES)


@pytest.mark.parametrize("name", ALL_STYLES)
def test_every_palette_passes_the_contrast_pairs(name: str) -> None:
    palette = STYLES[name].palette
    assert set(palette) == set(PALETTE_KEYS)
    assert all(re.fullmatch(r"#[0-9A-F]{6}", value) for value in palette.values()), palette
    assert palette_warnings(palette) == []


@pytest.mark.parametrize("name", ALL_STYLES)
def test_text_roles_use_only_embedded_faces_the_fitter_can_measure(name: str) -> None:
    style = STYLES[name]
    assert set(style.roles) == set(ROLE_CLASSES)
    for role in [*style.roles.values(), caps.ROLES[name]]:
        assert role.weight in EMBEDDED_FACES.get(role.family, set()), (role.family, role.weight)
        # textfit raises KeyError for a face without metrics
        assert text_width("Light, your way: £1,295 – “made to measure”…", role.family, role.weight, px=40) > 0


def test_the_styles_tell_apart_at_a_glance() -> None:
    assert set(NEW_STYLES) <= set(STYLES)
    for a, b in itertools.combinations(sorted(STYLES), 2):
        first, second = STYLES[a], STYLES[b]
        assert first.palette["bg"] != second.palette["bg"], (a, b)
        assert first.palette["accent"] != second.palette["accent"], (a, b)
        heads = [(s.roles["head"].family, s.roles["head"].weight, s.roles["head"].upper) for s in (first, second)]
        assert heads[0] != heads[1], (a, b)
        assert (first.transition, first.radius) != (second.transition, second.radius), (a, b)


# --------------------------------------------------------------------------- compositions


@pytest.mark.parametrize("name", ALL_STYLES)
@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_every_kind_composes_in_every_format_with_the_styles_own_sheet(tmp_path, name: str, fmt: str) -> None:
    result, out = _build(tmp_path, name, fmt)
    assert result.duration_ms == 5000 * len(KINDS)
    assert not [w for w in result.lint_warnings if w.startswith(("text_fit", "palette_contrast"))], result.lint_warnings
    style = STYLES[name]
    for i, kind in enumerate(KINDS, start=1):
        page = _page(out, f"sc{i}")
        assert f'data-kind="{kind}"' in page
        assert f"/* {name}:" in page  # the style's own sheet
        # The CSS sets exactly the measured roles, so what is measured is what renders.
        for role, cls in ROLE_CLASSES.items():
            assert f".{cls} {{ {style.roles[role].css()}" in page, (kind, cls)
        missing = [c for c in (*BASE_CLASSES, *TRANSITION_CLASSES[style.transition]) if not _defines(page, c)]
        assert missing == [], (kind, missing)
        # Faces named outside the roles (e.g. step numbers) are embedded too.
        for family, weight in _FACE.findall(page):
            assert int(weight) in EMBEDDED_FACES.get(family, set()), (kind, family, weight)


@pytest.mark.parametrize("name", ALL_STYLES)
def test_each_style_uses_its_own_transition(tmp_path, name: str) -> None:
    style = STYLES[name]
    _, out = _build(tmp_path, name, kinds=["photo_reveal", "text_card", "cta_endcard"])
    middle = _page(out, "sc2")
    for kind, markup in TRANSITION_MARKUP.items():
        assert (markup in middle) is (kind == style.transition), kind
    assert 'id="sc2-tin"' in middle and 'id="sc2-tout"' in middle


def test_every_style_moves_within_the_entrance_budget() -> None:
    """Scene timing (kinds.LAST_ENTRANCE, LAST_ITEM) assumes no entrance lasts
    over 0.8 s and no item or pop over 0.55 s, so all finish before the cut."""
    from koveriq.kinds import MOTION

    assert set(MOTION) == set(STYLES)
    for name, preset in MOTION.items():
        for entrance, limit in (("text", 0.8), ("card", 0.8), ("item", 0.55), ("pop", 0.55)):
            frm, to = getattr(preset, entrance)
            assert to["duration"] <= limit, (name, entrance)
            assert frm["opacity"] == 0 and to["opacity"] == 1, (name, entrance)
        assert preset.rule[0] <= 0.8, name


def test_showroom_keeps_the_louvres_and_minimal_fades() -> None:
    assert STYLES["showroom"].transition == "louvres"
    assert STYLES["minimal"].transition == "fade"


def test_minimal_dips_through_its_background_between_scenes(tmp_path) -> None:
    _, out = _build(tmp_path, "minimal", kinds=["photo_reveal", "text_card", "cta_endcard"])
    first, middle = _page(out, "sc1"), _page(out, "sc2")
    assert ".k-veil { position: absolute; inset: 0; z-index: 40; background: var(--bg); }" in middle
    assert re.search(r'tl\.fromTo\("#sc2-tin", \{ opacity: 1 \}, \{ opacity: 0, duration: 0\.4,', middle)
    out_tween = re.search(r'tl\.fromTo\("#sc2-tout", \{ opacity: 0 \}, \{ opacity: 1, duration: ([0-9.]+),[^\n]*\}, ([0-9.]+)\);', middle)
    assert out_tween
    ends = float(out_tween.group(2)) + float(out_tween.group(1))
    assert 4.9 <= ends < 5.0  # fully faded just before the cut
    # The hook frame is never blank: the photo already shows through the veil at 0 s.
    start = re.search(r'tl\.fromTo\("#sc1-cover", \{ opacity: ([0-9.]+) \}, \{ opacity: 0,', first)
    assert start and 0 < float(start.group(1)) < 1


@pytest.mark.parametrize("name", NEW_STYLES)
def test_the_new_styles_have_their_own_end_card(tmp_path, name: str) -> None:
    _, out = _build(tmp_path, name, kinds=["photo_reveal", "cta_endcard"])
    end = _page(out, "sc2")
    assert 'id="sc2-pill"' in end and 'id="sc2-cta"' in end and 'id="sc2-brand"' in end
    pill = re.search(r"\.k-pill \{[^}]*\}", end).group(0)
    if name == "showroom":  # a brass plate with espresso lettering
        assert "background: var(--accent)" in pill and "color: var(--accent-ink)" in pill
    else:  # a hairline outline, no fill
        assert "background: transparent" in pill and "inset 0 0 0 2px var(--ink)" in pill


def test_showroom_frames_photos_except_across_the_before_after_wipe(tmp_path) -> None:
    """The inset frame would ride on the after photo's sliding window."""
    _, out = _build(tmp_path, "showroom", kinds=["photo_reveal", "before_after", "cta_endcard"])
    frame = '.k-photo::after { content: ""; position: absolute; inset: 26px;'
    assert frame in _page(out, "sc1") and ".k-photo::after { display: none; }" not in _page(out, "sc1")
    assert ".k-photo::after { display: none; }" in _page(out, "sc2")


def test_showroom_edges_every_swatch_in_brass(tmp_path) -> None:
    """A dark finish (walnut, black) still reads on the espresso surface."""
    _, out = _build(tmp_path, "showroom", kinds=["swatches", "cta_endcard"])
    dot = re.search(r"\.k-dot \{[^}]*\}", _page(out, "sc1")).group(0)
    assert "inset 0 0 0 2px var(--line)" in dot


@pytest.mark.parametrize("name", ALL_STYLES)
def test_brand_palette_overrides_every_style(tmp_path, name: str) -> None:
    style = STYLES[name]
    override = {"accent": "#0B6E4F", "bg": "#FAFAFA", "surface": "#FFFDF8"}
    _, out = _build(tmp_path, name, kinds=["text_card", "offer_card", "cta_endcard"], kit={**brand(), "palette": override}, captions=True)
    page = _page(out, "sc1")
    assert "--accent: #0B6E4F;" in page and "--bg: #FAFAFA;" in page
    palette, errors = merge_palette(style, override)
    assert errors == []
    # The style's derived colours (decorative pattern, photo shade) follow the brand palette ...
    decor_colour, decor_alpha = style.decor
    assert rgba(palette[decor_colour], decor_alpha) in page
    shade_colour, shade_alpha = style.shade
    assert rgba(palette[shade_colour], shade_alpha) in _page(out, "sc1")
    # ... and so does the caption box.
    backing, shadow = caps.backing(name, palette)
    rule = re.search(r"\.k-capbox \{[^}]*\}", (out / "compositions" / "captions.html").read_text(encoding="utf-8")).group(0)
    assert f"background: {backing};" in rule and f"box-shadow: {shadow};" in rule
    # A clash is a warning on the result, never a silent pass.
    clash, _ = _build(tmp_path / "clash", name, kinds=["text_card", "cta_endcard"], kit={**brand(), "palette": {"ink": "#777777", "bg": "#808080"}})
    assert any(w.startswith("palette_contrast:ink/bg") for w in clash.lint_warnings)
    with pytest.raises(CompositionError, match="brand.palette.accent"):
        _build(tmp_path / "bad", name, kinds=["text_card", "cta_endcard"], kit={**brand(), "palette": {"accent": "brass"}})


@pytest.mark.parametrize("name", NEW_STYLES)
@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_the_new_styles_caption_every_spoken_scene(tmp_path, name: str, fmt: str) -> None:
    result, out = _build(tmp_path, name, fmt, captions=True)
    assert not [w for w in result.lint_warnings if w.startswith(("text_fit", "captions_empty"))], result.lint_warnings
    page = (out / "compositions" / "captions.html").read_text(encoding="utf-8")
    assert caps.ROLES[name].css() in page
