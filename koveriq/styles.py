"""The four KoverIQ template styles: tokens, text roles and palette checks.

Clean (warm paper, black serif headlines, louvres), Bold offer (dark,
uppercase, block wipes), Showroom (espresso and brass, a fine serif, framed
photos, louvres) and Minimal (near-monochrome, light type, one accent, soft
fades): the four templates of the KoverIQ wizard and the worker contract.

Text roles are the single source of truth for typography: the style CSS is
generated from them and the text fitter measures with them, so what is
measured is what renders. Only fonts and weights that HyperFrames embeds are
used (no font is downloaded at render time): Montserrat 400/700/900, Playfair
Display 900, Archivo Black 400, EB Garamond 400, Lato 400/700, Inter 400/700.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

PALETTE_KEYS = ("bg", "surface", "ink", "muted", "accent", "accentInk")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
SERIF_FAMILIES = frozenset({"Playfair Display", "EB Garamond"})


@dataclass(frozen=True)
class TextRole:
    family: str
    weight: int
    upper: bool = False
    tracking: float = 0.0  # letter-spacing, em
    line: float = 1.1  # line-height

    def css(self) -> str:
        fallback = "serif" if self.family in SERIF_FAMILIES else "sans-serif"
        parts = [
            f'font-family: "{self.family}", {fallback}',
            f"font-weight: {self.weight}",
            f"line-height: {self.line:g}",
            f"letter-spacing: {self.tracking:g}em",
            f"text-transform: {'uppercase' if self.upper else 'none'}",
        ]
        return "; ".join(parts) + ";"


@dataclass(frozen=True)
class Style:
    name: str
    palette: dict[str, str]
    roles: dict[str, TextRole]
    radius: int
    transition: str  # "louvres" | "blocks" | "fade" (koveriq.kinds.Motion)
    # Colours derived from the (brand-merged) palette: (palette key, opacity).
    shade: tuple[str, float]  # the gradient that settles photos under text
    decor: tuple[str, float]  # the slow-drifting pattern of text-only scenes
    line: tuple[str, float] = ("ink", 0.12)  # hairline frames (Showroom, Minimal)


STYLES: dict[str, Style] = {
    "clean": Style(
        name="clean",
        palette={
            "bg": "#F5EFE4",
            "surface": "#FBF8F2",
            "ink": "#1E2420",
            "muted": "#4A4F49",
            "accent": "#8C6420",
            "accentInk": "#FFFFFF",
        },
        roles={
            "over": TextRole("Montserrat", 700, upper=True, tracking=0.18, line=1.2),
            "head": TextRole("Playfair Display", 900, line=1.06),
            "sub": TextRole("Montserrat", 400, line=1.32),
            "item": TextRole("Montserrat", 700, line=1.15),
            "big": TextRole("Playfair Display", 900, line=1.02),
            "pill": TextRole("Montserrat", 700, tracking=0.02, line=1.1),
            "mark": TextRole("Montserrat", 700, upper=True, tracking=0.24, line=1.1),
        },
        radius=6,
        transition="louvres",
        shade=("ink", 0.55),
        decor=("ink", 0.06),
    ),
    "bold_offer": Style(
        name="bold_offer",
        palette={
            "bg": "#14161B",
            "surface": "#20242C",
            "ink": "#FFFFFF",
            "muted": "#C9CDD6",
            "accent": "#FF5A1F",
            "accentInk": "#14161B",
        },
        roles={
            "over": TextRole("Montserrat", 900, upper=True, tracking=0.14, line=1.2),
            "head": TextRole("Archivo Black", 400, upper=True, line=1.0),
            "sub": TextRole("Montserrat", 700, line=1.3),
            "item": TextRole("Montserrat", 900, upper=True, tracking=0.04, line=1.15),
            "big": TextRole("Archivo Black", 400, upper=True, line=0.98),
            "pill": TextRole("Montserrat", 900, tracking=0.02, line=1.1),
            "mark": TextRole("Montserrat", 900, upper=True, tracking=0.2, line=1.1),
        },
        radius=14,
        transition="blocks",
        shade=("bg", 0.75),
        decor=("accent", 0.16),
    ),
    # A premium interior after dark: espresso and walnut, cream type, brass
    # detail; a fine serif for headlines with widely tracked small capitals,
    # hairline brass frames and the louvre transition.
    "showroom": Style(
        name="showroom",
        palette={
            "bg": "#221A15",
            "surface": "#2E241E",
            "ink": "#F4EBDD",
            "muted": "#CDBDA8",
            "accent": "#C9A36A",
            "accentInk": "#221A15",
        },
        roles={
            "over": TextRole("Lato", 700, upper=True, tracking=0.26, line=1.2),
            "head": TextRole("EB Garamond", 400, line=1.08),
            "sub": TextRole("Lato", 400, line=1.36),
            "item": TextRole("Lato", 700, tracking=0.02, line=1.15),
            "big": TextRole("EB Garamond", 400, line=1.0),
            "pill": TextRole("Lato", 700, tracking=0.06, line=1.1),
            "mark": TextRole("Lato", 700, upper=True, tracking=0.3, line=1.1),
        },
        radius=2,
        transition="louvres",
        shade=("bg", 0.8),
        decor=("accent", 0.18),
        line=("accent", 0.55),
    ),
    # Restraint: off-white and white, near-black type at the lightest embedded
    # weight, one cool accent, hairlines instead of shadows, square corners and
    # soft fades through the background between scenes.
    "minimal": Style(
        name="minimal",
        palette={
            "bg": "#F7F7F5",
            "surface": "#FFFFFF",
            "ink": "#141414",
            "muted": "#5E6166",
            "accent": "#2B5B84",
            "accentInk": "#FFFFFF",
        },
        roles={
            "over": TextRole("Inter", 400, upper=True, tracking=0.24, line=1.2),
            "head": TextRole("Inter", 400, tracking=-0.02, line=1.08),
            "sub": TextRole("Inter", 400, line=1.45),
            "item": TextRole("Inter", 400, line=1.2),
            "big": TextRole("Inter", 400, tracking=-0.03, line=1.0),
            "pill": TextRole("Inter", 400, tracking=0.01, line=1.1),
            "mark": TextRole("Inter", 700, upper=True, tracking=0.22, line=1.1),
        },
        radius=0,
        transition="fade",
        shade=("ink", 0.2),
        decor=("ink", 0.14),
        line=("ink", 0.16),
    ),
}


def merge_palette(style: Style, override: Mapping[str, Any] | None) -> tuple[dict[str, str], list[str]]:
    """The style palette with a brand override applied. Returns (palette, errors)."""
    palette = dict(style.palette)
    errors: list[str] = []
    if override is None:
        return palette, errors
    if not isinstance(override, Mapping):
        return palette, ["brand.palette: must be an object"]
    for key, value in override.items():
        if key not in PALETTE_KEYS:
            errors.append(f"brand.palette.{key}: unknown colour; allowed: {', '.join(PALETTE_KEYS)}")
        elif value is None:
            continue
        elif not isinstance(value, str) or not _HEX.fullmatch(value):
            errors.append(f"brand.palette.{key}: {value!r} is not a #RRGGBB colour")
        else:
            palette[key] = value.upper()
    return palette, errors


def _luminance(hex_colour: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio of two #RRGGBB colours."""
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# (text, background) pairs the templates use for reading text.
CONTRAST_PAIRS = (("ink", "bg"), ("ink", "surface"), ("muted", "surface"), ("accent", "surface"), ("accentInk", "accent"))


def palette_warnings(palette: Mapping[str, str], minimum: float = 4.5) -> list[str]:
    warnings = []
    for fg, bg in CONTRAST_PAIRS:
        ratio = contrast(palette[fg], palette[bg])
        if ratio < minimum:
            warnings.append(f"palette_contrast:{fg}/{bg}: {ratio:.2f} is below {minimum}")
    return warnings


def rgba(hex_colour: str, alpha: float) -> str:
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha:g})"
