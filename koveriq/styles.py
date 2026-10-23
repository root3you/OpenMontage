"""The two KoverIQ template styles: tokens, text roles and palette checks.

Text roles are the single source of truth for typography: the style CSS is
generated from them and the text fitter measures with them, so what is
measured is what renders. Only fonts and weights that HyperFrames embeds are
used (no font is downloaded at render time).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

PALETTE_KEYS = ("bg", "surface", "ink", "muted", "accent", "accentInk")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class TextRole:
    family: str
    weight: int
    upper: bool = False
    tracking: float = 0.0  # letter-spacing, em
    line: float = 1.1  # line-height

    def css(self) -> str:
        fallback = "serif" if self.family == "Playfair Display" else "sans-serif"
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
    transition: str  # "louvres" | "blocks"


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
