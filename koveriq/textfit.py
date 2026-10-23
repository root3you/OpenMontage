"""Deterministic text fitting from the glyph advance widths in font_metrics.json.

The templates set every text box's width and font size explicitly, so the
browser wraps at the same width the fitter measured. Kerning is ignored; the
`safety` factor (default 0.95 of the box) absorbs it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

METRICS_PATH = Path(__file__).resolve().parent / "font_metrics.json"


@lru_cache(maxsize=1)
def _metrics() -> dict:
    with open(METRICS_PATH, encoding="utf-8") as handle:
        return json.load(handle)["faces"]


def _face(family: str, weight: int) -> dict:
    faces = _metrics()
    if family not in faces or str(weight) not in faces[family]:
        raise KeyError(f"no metrics for {family!r} {weight}; known: { {f: sorted(w) for f, w in faces.items()} }")
    return faces[family][str(weight)]


def text_width(text: str, family: str, weight: int, *, px: float, letter_spacing_em: float = 0.0) -> float:
    """Rendered width in px of a single line of text."""
    face = _face(family, weight)
    widths, default = face["widths"], face["default"]
    ems = sum(widths.get(ch, default) for ch in text)
    return (ems + letter_spacing_em * len(text)) * px


def wrap(
    text: str,
    family: str,
    weight: int,
    *,
    px: float,
    box_w: float,
    letter_spacing_em: float = 0.0,
) -> list[str]:
    """Greedy word wrap, as the browser does for `white-space: normal`."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if not current or text_width(candidate, family, weight, px=px, letter_spacing_em=letter_spacing_em) <= box_w:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


@dataclass(frozen=True)
class Fit:
    px: int
    lines: list[str] = field(default_factory=list)
    width: float = 0.0
    fits: bool = True


def fit_text(
    text: str,
    *,
    family: str,
    weight: int,
    box_w: float,
    max_lines: int,
    base_px: int,
    min_px: int,
    uppercase: bool = False,
    letter_spacing_em: float = 0.0,
    safety: float = 0.95,
) -> Fit:
    """Largest size from base_px down to min_px at which `text` wraps into
    at most `max_lines` lines inside `box_w`. Reports `fits=False` at min_px
    when nothing fits."""
    shown = text.upper() if uppercase else text
    usable = box_w * safety
    min_px = min(min_px, base_px)
    for px in range(int(base_px), int(min_px) - 1, -1):
        lines = wrap(shown, family, weight, px=px, box_w=usable, letter_spacing_em=letter_spacing_em)
        widest = max((text_width(l, family, weight, px=px, letter_spacing_em=letter_spacing_em) for l in lines), default=0.0)
        if len(lines) <= max_lines and widest <= usable:
            return Fit(px=px, lines=_original_case(text, lines), width=widest, fits=True)
    lines = wrap(shown, family, weight, px=min_px, box_w=usable, letter_spacing_em=letter_spacing_em)
    widest = max((text_width(l, family, weight, px=min_px, letter_spacing_em=letter_spacing_em) for l in lines), default=0.0)
    return Fit(px=int(min_px), lines=_original_case(text, lines), width=widest, fits=False)


def _original_case(text: str, lines: list[str]) -> list[str]:
    """Re-chunk the original words like the measured (maybe uppercased) lines.

    Uppercasing never changes where words break, so the word counts match;
    CSS `text-transform` does the visual uppercasing.
    """
    words = text.split()
    out, cursor = [], 0
    for line in lines:
        count = len(line.split())
        out.append(" ".join(words[cursor : cursor + count]))
        cursor += count
    return out
