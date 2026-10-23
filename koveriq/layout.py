"""Frame geometry, type scale, measured text blocks and narration beats."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from markupsafe import Markup, escape

from koveriq.styles import Style
from koveriq.textfit import fit_text, text_width

MIN_TEXT_PX = 28  # HyperFrames' text_below_floor: 2.6% of a 1080 short side


@dataclass(frozen=True)
class Frame:
    fmt: str
    name: str
    w: int
    h: int
    pad_x: int
    pad_top: int
    pad_bottom: int

    @property
    def content_w(self) -> int:
        return self.w - 2 * self.pad_x

    @property
    def safe_h(self) -> int:
        return self.h - self.pad_top - self.pad_bottom


# 9:16 keeps key text out of the platform header (top) and the caption/button
# band (bottom) of Reels, TikTok and Shorts.
FRAMES = {
    "16:9": Frame("16:9", "landscape", 1920, 1080, pad_x=120, pad_top=140, pad_bottom=110),
    "9:16": Frame("9:16", "portrait", 1080, 1920, pad_x=84, pad_top=260, pad_bottom=430),
    "1:1": Frame("1:1", "square", 1080, 1080, pad_x=80, pad_top=120, pad_bottom=96),
}

# Base sizes (px) per text size key.
SIZES = {
    "landscape": {"over": 26, "head": 92, "head_xl": 112, "title": 72, "sub": 34, "item": 34, "label": 28, "big": 150, "cta": 100, "pill": 38, "num": 30, "badge": 30, "mark": 22},
    "portrait": {"over": 26, "head": 84, "head_xl": 100, "title": 68, "sub": 34, "item": 36, "label": 30, "big": 132, "cta": 90, "pill": 36, "num": 32, "badge": 30, "mark": 22},
    "square": {"over": 24, "head": 74, "head_xl": 88, "title": 60, "sub": 30, "item": 32, "label": 28, "big": 112, "cta": 80, "pill": 34, "num": 28, "badge": 28, "mark": 20},
}


def num(value: float) -> str:
    """Stable short number formatting for HTML/CSS/JS."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


@dataclass
class Text:
    """A measured block of text rendered as fixed lines (white-space: nowrap)."""

    slot: str
    lines: list[str]
    px: int
    width: int
    fits: bool

    @property
    def html(self) -> Markup:
        return Markup("<br>").join(escape(line) for line in self.lines)

    @property
    def style(self) -> str:
        return f"font-size:{self.px}px;width:{self.width}px"


@dataclass
class SceneContext:
    """Everything a kind needs to lay itself out for one scene."""

    sid: str
    kind: str
    slots: dict[str, Any]
    style: Style
    frame: Frame
    duration: float  # seconds
    words: list[tuple[str, float, float]]  # (normalised word, start s, end s), scene-local
    font_scale: float = 1.0
    warnings: list[str] = field(default_factory=list)

    @property
    def sizes(self) -> dict[str, int]:
        return SIZES[self.frame.name]

    def text(
        self,
        slot: str,
        value: Optional[str],
        role: str,
        size: str,
        box_w: float,
        max_lines: int,
        *,
        min_ratio: float = 0.62,
    ) -> Optional[Text]:
        if not value:
            return None
        spec = self.style.roles[role]
        base = max(MIN_TEXT_PX, int(round(self.sizes[size] * self.font_scale)))
        low = max(MIN_TEXT_PX, int(round(base * min_ratio)))
        fit = fit_text(
            value,
            family=spec.family,
            weight=spec.weight,
            box_w=box_w,
            max_lines=max_lines,
            base_px=base,
            min_px=low,
            uppercase=spec.upper,
            letter_spacing_em=spec.tracking,
        )
        if not fit.fits:
            self.warnings.append(
                f"text_fit:{self.sid}.{slot}: does not fit {int(box_w)}px in {max_lines} line(s) "
                f"even at {fit.px}px; shorten it"
            )
        # Element width hugs the widest measured line plus the fitter's margin.
        width = int(min(box_w, fit.width / 0.95 + 4)) if fit.fits else int(fit.width + 4)
        return Text(slot=slot, lines=fit.lines, px=fit.px, width=max(width, 1), fits=fit.fits)

    def measure(self, value: str, role: str, px: float) -> float:
        spec = self.style.roles[role]
        shown = value.upper() if spec.upper else value
        return text_width(shown, spec.family, spec.weight, px=px, letter_spacing_em=spec.tracking)

    def size(self, key: str) -> int:
        return max(MIN_TEXT_PX, int(round(self.sizes[key] * self.font_scale)))


_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def normalise(word: str) -> str:
    return _NON_ALNUM.sub("", word.casefold())


def scene_words(timing: dict[str, Any]) -> list[tuple[str, float, float]]:
    start = timing["startMs"]
    out = []
    for word in timing.get("words") or []:
        out.append((normalise(str(word.get("w", ""))), (word["startMs"] - start) / 1000, (word["endMs"] - start) / 1000))
    return out


def item_beats(
    labels: list[str],
    words: list[tuple[str, float, float]],
    *,
    earliest: float,
    latest: float,
    gap: float = 0.22,
) -> list[float]:
    """When each item appears: on the word that names it, else evenly spaced.

    Times are scene-local, increasing by at least `gap`, within
    [earliest, latest].
    """
    latest = max(latest, earliest)
    n = len(labels)
    matched: list[Optional[float]] = [None] * n
    cursor = 0
    for i, label in enumerate(labels):
        tokens = [normalise(t) for t in label.split() if normalise(t)]
        if not tokens:
            continue
        key = tokens[0]
        for j in range(cursor, len(words)):
            spoken = words[j][0]
            if len(spoken) >= 2 and (spoken == key or (len(key) >= 3 and (spoken.startswith(key) or key.startswith(spoken)))):
                matched[i] = words[j][1] - 0.08
                cursor = j + 1
                break
    # Fill the unmatched ones evenly between their matched neighbours.
    times: list[float] = []
    step = (latest - earliest) / max(n, 1) if n else 0
    default = [earliest + step * i for i in range(n)]
    for i in range(n):
        t = matched[i] if matched[i] is not None else default[i]
        if times:
            t = max(t, times[-1] + gap)
        times.append(min(max(t, earliest), latest))
    # Keep the gap even after clamping at `latest`.
    for i in range(n - 2, -1, -1):
        times[i] = min(times[i], times[i + 1] - gap) if times[i + 1] - times[i] < gap else times[i]
    return [round(max(t, earliest), 3) for t in times]


class Tweens:
    """Collects literal GSAP calls (static, so `hyperframes lint` can read them)."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.ends: list[float] = []

    @staticmethod
    def _vars(values: dict[str, Any]) -> str:
        parts = []
        for key, value in values.items():
            if isinstance(value, bool):
                rendered = "true" if value else "false"
            elif isinstance(value, (int, float)):
                rendered = num(value)
            else:
                rendered = json.dumps(value)
            parts.append(f"{key}: {rendered}")
        return "{ " + ", ".join(parts) + " }"

    def from_to(self, selector: str, frm: dict[str, Any], to: dict[str, Any], at: float) -> None:
        self.lines.append(f"tl.fromTo({json.dumps(selector)}, {self._vars(frm)}, {self._vars(to)}, {num(at)});")
        self.ends.append(at + float(to.get("duration", 0)))

    def to(self, selector: str, to: dict[str, Any], at: float) -> None:
        self.lines.append(f"tl.to({json.dumps(selector)}, {self._vars(to)}, {num(at)});")
        self.ends.append(at + float(to.get("duration", 0)))
