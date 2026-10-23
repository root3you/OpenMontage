"""Burned-in captions from the narration's word timings (lane W3).

`build_composition(..., captions=True)` adds one sub-composition,
`compositions/captions.html`, hosted on its own captions track above every
scene. It shows the current phrase, two or three words at a time, in the
template's caption style:

- Groups follow HyperFrames' caption guidance (references/captions.md): two
  or three words; a group ends at a sentence end, after a clause comma once
  it has two words, before a pause of 150 ms or more, and before it would
  grow wider than the caption box. A sentence's last word may join a full
  group rather than sit alone.
- One group is visible at a time. A group opens just before its first word
  (never at exactly 0 s), closes a moment after its last word, at the latest
  when the next group opens or its scene ends, and is hard-killed
  (visibility hidden) when it closes. Groups never span two scenes.
- The end card is not captioned: it shows the brief's CTA word for word, so
  a caption would print the call to action twice.
- The captions sit in a band at the bottom of the format's safe area (above
  the 9:16 platform UI band), and every captioned scene is laid out in a
  frame whose bottom margin includes that band, so no scene text sits under
  a caption. Plain words read on a translucent backing sized to the text.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from koveriq.layout import Frame, Tweens
from koveriq.styles import TextRole

MAX_WORDS = 3
PAUSE = 0.15  # s: a gap this long between two words starts a new group
LEAD = 0.08  # s: a group opens this long before its first word
HOLD = 0.3  # s: and stays this long after its last word
MIN_SHOW = 0.3  # s: shortest time a group is on screen
FIRST_AT = 0.1  # s: never at exactly 0 s, which looks pre-existing
EDGE = 0.05  # s: a group closes this long before its scene ends
FADE_IN = 0.14
FADE_OUT = 0.12
NOT_CAPTIONED = ("cta_endcard",)
_SENTENCE_END = (".", "!", "?", "…")
_CLAUSE_END = (",", ";", ":", "—")
_STRIP = ",;:."


@dataclass(frozen=True)
class Band:
    """The caption band: its height (reserved above the bottom safe margin),
    the caption's base and minimum size, and the widest caption text."""

    height: int
    px: int
    min_px: int
    text_w: int
    pad_v: int
    pad_h: int


# Portrait captions stay narrow, clear of the platforms' right-hand button rail.
BAND = {
    "landscape": Band(height=104, px=46, min_px=34, text_w=1300, pad_v=12, pad_h=26),
    "portrait": Band(height=112, px=50, min_px=38, text_w=760, pad_v=12, pad_h=24),
    "square": Band(height=96, px=42, min_px=32, text_w=820, pad_v=11, pad_h=22),
}

ROLES = {
    "clean": TextRole("Montserrat", 700, line=1.2),
    "bold_offer": TextRole("Montserrat", 900, upper=True, tracking=0.03, line=1.15),
}


@dataclass(frozen=True)
class Cue:
    scene: str
    start: float  # s, on the video timeline
    end: float
    text: str


def captioned_frame(frame: Frame) -> Frame:
    """The frame captioned scenes are laid out in: the band joins the bottom margin."""
    return replace(frame, pad_bottom=frame.pad_bottom + BAND[frame.name].height)


def display_text(tokens: Sequence[str]) -> str:
    """A group's words as shown: a trailing comma, colon or full stop is dropped."""
    words = [str(t) for t in tokens]
    words[-1] = words[-1].rstrip(_STRIP) or words[-1]
    return " ".join(words)


def group_words(words: Sequence[Mapping[str, Any]], *, fits: Callable[[str], bool]) -> list[list[Mapping[str, Any]]]:
    """Split one scene's words (in order) into caption groups.

    `fits(text)` says whether a candidate group fits the caption box on one
    line at the caption's base size.
    """
    groups: list[list[Mapping[str, Any]]] = []
    current: list[Mapping[str, Any]] = []
    for word in words:
        token = str(word["w"]).strip()
        if not token:
            continue
        if current:
            pause = (word["startMs"] - current[-1]["endMs"]) / 1000 >= PAUSE
            full = len(current) >= MAX_WORDS and not token.endswith(_SENTENCE_END)
            wide = not fits(display_text([w["w"] for w in current] + [token]))
            if pause or full or wide:
                groups.append(current)
                current = []
        current.append({**word, "w": token})
        if token.endswith(_SENTENCE_END) or (token.endswith(_CLAUSE_END) and len(current) >= 2):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def build_cues(scenes: Sequence[Mapping[str, Any]], timings: Mapping[str, Any], *, fits: Callable[[str], bool]) -> list[Cue]:
    """Timed caption groups for every captioned scene, on the video timeline."""
    cues: list[Cue] = []
    for scene in scenes:
        if scene["kind"] in NOT_CAPTIONED:
            continue
        timing = timings[scene["id"]]
        start, end = timing["startMs"], timing["endMs"]
        inside = [w for w in timing.get("words") or [] if start - 50 <= w["startMs"] <= w["endMs"] <= end + 50]
        groups = group_words(inside, fits=fits)
        opens = [max(g[0]["startMs"] / 1000 - LEAD, start / 1000, FIRST_AT) for g in groups]
        last_close = end / 1000 - EDGE
        for i, group in enumerate(groups):
            limit = opens[i + 1] if i + 1 < len(groups) else last_close
            close = min(group[-1]["endMs"] / 1000 + HOLD, limit)
            if close - opens[i] < MIN_SHOW:
                close = min(opens[i] + MIN_SHOW, limit)
            if close - opens[i] < 0.05:  # no room at all (a word at the very end of a scene)
                continue
            cues.append(Cue(scene=scene["id"], start=round(opens[i], 3), end=round(close, 3), text=display_text([w["w"] for w in group])))
    return cues


def tweens(cues: Sequence[Cue], ids: Sequence[str]) -> Tweens:
    """Show, fade and hard-kill every group (HyperFrames' caption pattern)."""
    tw = Tweens()
    for cue, el_id in zip(cues, ids):
        sel = f"#{el_id}"
        fade_out = min(FADE_OUT, (cue.end - cue.start) / 3)
        tw.set(sel, {"visibility": "visible"}, cue.start)
        tw.from_to(sel, {"opacity": 0, "y": 10}, {"opacity": 1, "y": 0, "duration": FADE_IN, "ease": "power2.out"}, cue.start)
        tw.to(sel, {"opacity": 0, "duration": round(fade_out, 3), "ease": "power2.in"}, cue.end - fade_out)
        tw.set(sel, {"visibility": "hidden"}, cue.end)
    return tw


def band_top(frame: Frame) -> int:
    """Where the band starts, in the format's own (uncaptioned) frame."""
    return frame.h - frame.pad_bottom - BAND[frame.name].height
