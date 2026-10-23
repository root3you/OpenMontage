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


def balance(
    text: str,
    lines: int,
    *,
    family: str,
    weight: int,
    px: float,
    uppercase: bool = False,
    letter_spacing_em: float = 0.0,
) -> list[str]:
    """Break `text` into exactly `lines` lines (fewer if it has fewer words) so
    the widest line is as narrow as possible, as CSS `text-wrap: balance` does.

    Greedy wrapping can leave one word alone on the last line ("Book your free
    home / survey"); this never makes the widest line wider than greedy's, so
    whatever fitted still fits. Lines keep the original case.
    """
    words = text.split()
    n = max(1, min(lines, len(words)))
    shown = [w.upper() for w in words] if uppercase else words

    def width(i: int, j: int) -> float:
        return text_width(" ".join(shown[i:j]), family, weight, px=px, letter_spacing_em=letter_spacing_em)

    # best[k][i]: (widest line, breaks) for words[i:] in k lines.
    inf = (float("inf"), ())
    best = [[inf] * (len(words) + 1) for _ in range(n + 1)]
    best[0][len(words)] = (0.0, ())
    for k in range(1, n + 1):
        for i in range(len(words) - 1, -1, -1):
            for j in range(i + 1, len(words) - k + 2):
                rest = best[k - 1][j]
                if rest[0] == float("inf"):
                    continue
                candidate = (max(width(i, j), rest[0]), (j, *rest[1]))
                if candidate[0] < best[k][i][0]:
                    best[k][i] = candidate
    cuts = [0, *best[n][0][1]]
    return [" ".join(words[a:b]) for a, b in zip(cuts, cuts[1:])]


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
