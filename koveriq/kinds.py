"""Layout and motion for the ten scene kinds.

Each kind function measures its text, places its elements for the frame and
records its GSAP tweens. It returns the view the kind's template renders.
Everything is computed here, deterministically; templates only print it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from koveriq.layout import SceneContext, Text, Tweens, item_beats, num

BARS = 8  # louvres in the clean transition
REVEAL_BARS = 10  # louvres over a revealed photo
CARD_PAD = {"landscape": (44, 52), "portrait": (40, 46), "square": (36, 42)}
UPSCALE_WARNING = 1.5


@dataclass(frozen=True)
class PhotoInfo:
    src: str
    w: int
    h: int


@dataclass(frozen=True)
class BrandView:
    name: str
    website: Optional[str]  # None: the brand kit has no website, the end card has no pill
    logo_src: Optional[str]
    logo_w: int = 0
    logo_h: int = 0


@dataclass
class Resources:
    photos: dict[str, PhotoInfo]
    brand: BrandView


class Motion:
    """Style-specific motion presets, written as literal GSAP calls."""

    def __init__(self, style: str, tweens: Tweens, sid: str):
        self.bold = style == "bold_offer"
        self.tw = tweens
        self.sid = sid

    def text(self, el_id: str, t: float) -> None:
        if self.bold:
            self.tw.from_to(f"#{el_id}", {"opacity": 0, "x": -48}, {"opacity": 1, "x": 0, "duration": 0.5, "ease": "power4.out"}, t)
        else:
            self.tw.from_to(f"#{el_id}", {"opacity": 0, "y": 28}, {"opacity": 1, "y": 0, "duration": 0.7, "ease": "power3.out"}, t)

    def card(self, el_id: str, t: float) -> None:
        if self.bold:
            self.tw.from_to(f"#{el_id}", {"opacity": 0, "xPercent": -8}, {"opacity": 1, "xPercent": 0, "duration": 0.55, "ease": "power4.out"}, t)
        else:
            self.tw.from_to(f"#{el_id}", {"opacity": 0, "y": 36}, {"opacity": 1, "y": 0, "duration": 0.8, "ease": "power3.out"}, t)

    def item(self, el_id: str, t: float) -> None:
        if self.bold:
            self.tw.from_to(f"#{el_id}", {"opacity": 0, "scale": 0.6}, {"opacity": 1, "scale": 1, "duration": 0.45, "ease": "back.out(2)"}, t)
        else:
            self.tw.from_to(f"#{el_id}", {"opacity": 0, "y": 20, "scale": 0.96}, {"opacity": 1, "y": 0, "scale": 1, "duration": 0.5, "ease": "power3.out"}, t)

    def rule(self, el_id: str, t: float) -> None:
        self.tw.from_to(f"#{el_id}", {"scaleX": 0}, {"scaleX": 1, "duration": 0.45 if self.bold else 0.6, "ease": "power3.out"}, t)

    def pop(self, el_id: str, t: float) -> None:
        ease = "back.out(2.2)" if self.bold else "back.out(1.7)"
        self.tw.from_to(f"#{el_id}", {"opacity": 0, "scale": 0.82}, {"opacity": 1, "scale": 1, "duration": 0.55, "ease": ease}, t)

    def pulse(self, el_id: str, t: float) -> None:
        self.tw.to(f"#{el_id}", {"scale": 1.05, "duration": 0.45, "ease": "sine.inOut", "yoyo": True, "repeat": 1}, t)

    def fade(self, el_id: str, t: float, duration: float = 0.4) -> None:
        self.tw.from_to(f"#{el_id}", {"opacity": 0}, {"opacity": 1, "duration": duration, "ease": "power1.out"}, t)

    def photo(self, img_id: str, duration: float, direction: str = "in") -> None:
        push = 1.16 if self.bold else 1.12
        sel = f"#{img_id}"
        if direction == "out":
            self.tw.from_to(sel, {"scale": 1}, {"scale": push - 0.04, "duration": duration, "ease": "none"}, 0)
        elif direction in ("left", "right"):
            sign = 1 if direction == "left" else -1
            self.tw.from_to(sel, {"scale": 1.1, "xPercent": 3 * sign}, {"scale": 1.1, "xPercent": -3 * sign, "duration": duration, "ease": "none"}, 0)
        else:
            self.tw.from_to(sel, {"scale": push}, {"scale": 1, "duration": duration, "ease": "none"}, 0)

    def drift(self, el_id: str, duration: float) -> None:
        """Slow movement of a decorative layer so text-only scenes never freeze."""
        self.tw.from_to(f"#{el_id}", {"y": 0}, {"y": -36, "duration": duration, "ease": "none"}, 0)

    def reveal(self, el_id: str, t: float, *, first: bool) -> None:
        """Open the cover over a photo (louvres, or blocks in bold_offer)."""
        if self.bold:
            # block-b is painted over block-a: it leaves first.
            self.tw.from_to(f"#{el_id} .k-block-b", {"xPercent": 0}, {"xPercent": 102, "duration": 0.7, "ease": "power3.inOut"}, t)
            self.tw.from_to(f"#{el_id} .k-block-a", {"xPercent": 0}, {"xPercent": 102, "duration": 0.7, "ease": "power3.inOut"}, t + 0.12)
        else:
            start = 0.86 if first else 1  # slits at frame 0 so the hook frame is never blank
            self.tw.from_to(f"#{el_id} .k-bar", {"scaleY": start}, {"scaleY": 0, "duration": 0.9, "ease": "power2.inOut", "stagger": 0.05}, t)

    def transition_in(self) -> None:
        sel = f"#{self.sid}-tin"
        if self.bold:
            self.tw.from_to(f"{sel} .k-block-b", {"xPercent": 0}, {"xPercent": 102, "duration": 0.45, "ease": "power3.in"}, 0.02)
            self.tw.from_to(f"{sel} .k-block-a", {"xPercent": 0}, {"xPercent": 102, "duration": 0.45, "ease": "power3.in"}, 0.1)
        else:
            self.tw.from_to(f"{sel} .k-bar", {"scaleY": 1}, {"scaleY": 0, "duration": 0.42, "ease": "power2.out", "stagger": 0.03}, 0.02)

    def transition_out(self, duration: float) -> None:
        sel = f"#{self.sid}-tout"
        if self.bold:
            start = duration - 0.52
            self.tw.from_to(f"{sel} .k-block-a", {"xPercent": -102}, {"xPercent": 0, "duration": 0.4, "ease": "power3.out"}, start)
            self.tw.from_to(f"{sel} .k-block-b", {"xPercent": -102}, {"xPercent": 0, "duration": 0.4, "ease": "power3.out"}, start + 0.08)
        else:
            start = duration - (0.36 + 0.03 * (BARS - 1)) - 0.03
            self.tw.from_to(f"{sel} .k-bar", {"scaleY": 0}, {"scaleY": 1, "duration": 0.36, "ease": "power2.in", "stagger": 0.03}, start)


# ---------------------------------------------------------------------------
# helpers


def _focus(ctx: SceneContext, key: str = "focus") -> tuple[float, float]:
    focus = ctx.slots.get(key) or {}
    return float(focus.get("x", 0.5)), float(focus.get("y", 0.5))


def _photo(ctx: SceneContext, res: Resources, asset_id: str, name: str, box: tuple[int, int, int, int], focus_key: str = "focus", slot: str = "assetId", *, centred: bool = False) -> dict[str, Any]:
    left, top, w, h = box
    info = res.photos[asset_id]
    fx, fy = _focus(ctx, focus_key)
    scale = max(w / info.w, h / info.h) * 1.12
    if scale > UPSCALE_WARNING:
        ctx.warnings.append(
            f"photo_upscaled:{ctx.sid}.{slot}: {asset_id} is {info.w}x{info.h} and is shown at {scale:.1f}x; use a larger photo"
        )
    return {
        "id": f"{ctx.sid}-{name}",
        "img_id": f"{ctx.sid}-{name}-img",
        "src": info.src,
        "pos": f"{num(fx * 100)}% {num(fy * 100)}%",
        # A push scales around the focus; a sideways pan must scale around the
        # centre or its shift exposes the background when the focus is off-centre.
        "origin": "50% 50%" if centred else f"{num(fx * 100)}% {num(fy * 100)}%",
        "box": f"left:{left}px;top:{top}px;width:{w}px;height:{h}px",
    }


def _t0(flags: dict[str, bool]) -> float:
    return 0.5 if flags["tin"] else 0.2


# The out-transition starts 0.6 s before the scene ends (0.52 s in bold_offer)
# and the longest entrance lasts 0.8 s, so no entrance may start later than this.
LAST_ENTRANCE = 0.62 + 0.8
LAST_ITEM = 0.62 + 0.55


def _compress(ctx: SceneContext, t: float) -> float:
    """Squeeze entrance times into short scenes so every entrance has
    finished before the out-transition starts."""
    return min(t, max(0.1, ctx.duration - LAST_ENTRANCE))


def _latest_item(ctx: SceneContext) -> float:
    return max(0.1, ctx.duration - LAST_ITEM)


def _card_texts(ctx: SceneContext, box_w: float, *, head_slot: str = "headline", head_size: str = "head", head_lines: int = 2, sub_lines: int = 2) -> dict[str, Optional[Text]]:
    s = ctx.slots
    return {
        "over": ctx.text("overline", s.get("overline"), "over", "over", box_w, 1),
        "head": ctx.text(head_slot, s.get(head_slot), "head", head_size, box_w, head_lines, min_ratio=0.58),
        "sub": ctx.text("subline", s.get("subline"), "sub", "sub", box_w, sub_lines, min_ratio=0.82),
    }


def _card_text_w(ctx: SceneContext) -> int:
    pad_v, pad_h = CARD_PAD[ctx.frame.name]
    return min(820, ctx.frame.content_w - 2 * pad_h)


def _card_view(ctx: SceneContext, texts: dict[str, Optional[Text]], m: Motion, t: float, *, anchor: str = "bottom-left") -> Optional[dict[str, Any]]:
    if not any(texts.values()):
        return None
    F = ctx.frame
    pad_v, pad_h = CARD_PAD[F.name]
    pos = {
        "bottom-left": f"left:{F.pad_x}px;bottom:{F.pad_bottom}px",
        "center": "left:50%;top:50%",
    }[anchor]
    card_id = f"{ctx.sid}-card"
    m.card(card_id, _compress(ctx, t))
    step = 0.15
    for i, key in enumerate(("over", "head", "sub")):
        if texts[key]:
            m.text(f"{ctx.sid}-{key}", _compress(ctx, t + 0.12 + step * i + (0.35 if key == "sub" else 0)))
    return {"id": card_id, "pos": pos, "pad": f"{pad_v}px {pad_h}px", "anchor": anchor, **texts}


# ---------------------------------------------------------------------------
# kinds


def photo_pan(ctx: SceneContext, res: Resources, m: Motion, flags: dict[str, bool]) -> dict[str, Any]:
    F, s = ctx.frame, ctx.slots
    direction = s.get("direction", "in")
    photo = _photo(ctx, res, s["assetId"], "photo", (0, 0, F.w, F.h), centred=direction in ("left", "right"))
    m.photo(photo["img_id"], ctx.duration, direction)
    card = _card_view(ctx, _card_texts(ctx, _card_text_w(ctx)), m, _t0(flags) + 0.2)
    return {"photo": photo, "card": card}


def photo_reveal(ctx: SceneContext, res: Resources, m: Motion, flags: dict[str, bool]) -> dict[str, Any]:
    F, s = ctx.frame, ctx.slots
    t = 0.25 if not flags["tin"] else 0.55
    if F.name == "landscape":
        box = (840, 0, F.w - 840, F.h)
        col = {"style": f"left:{F.pad_x}px;top:{F.pad_top}px;width:640px;height:{F.safe_h}px", "align": "center"}
        texts = {
            "over": ctx.text("overline", s.get("overline"), "over", "over", 640, 1),
            "head": ctx.text("headline", s.get("headline"), "head", "head_xl", 640, 3, min_ratio=0.55),
            "sub": ctx.text("subline", s.get("subline"), "sub", "sub", 640, 3, min_ratio=0.82),
        }
    elif F.name == "portrait":
        box = (0, 0, F.w, 1080)
        col = {"style": f"left:{F.pad_x}px;top:1130px;width:{F.content_w}px;height:{F.h - F.pad_bottom - 1130}px", "align": "start"}
        texts = {
            "over": ctx.text("overline", s.get("overline"), "over", "over", F.content_w, 1),
            "head": ctx.text("headline", s.get("headline"), "head", "head", F.content_w, 2, min_ratio=0.58),
            "sub": ctx.text("subline", s.get("subline"), "sub", "sub", F.content_w, 2, min_ratio=0.82),
        }
    else:
        box = (0, 0, F.w, F.h)
        col = None
        texts = _card_texts(ctx, _card_text_w(ctx))
    photo = _photo(ctx, res, s["assetId"], "photo", box)
    m.photo(photo["img_id"], ctx.duration, "in")
    cover_id = f"{ctx.sid}-cover"
    m.reveal(cover_id, t, first=not flags["tin"])
    view: dict[str, Any] = {"photo": photo, "cover": {"id": cover_id, "box": photo["box"], "bars": REVEAL_BARS}}
    if col is None:
        view["card"] = _card_view(ctx, texts, m, t + 0.5)
        view["col"] = None
    else:
        base = t + 0.15
        for i, key in enumerate(("over", "head")):
            if texts[key]:
                m.text(f"{ctx.sid}-{key}", _compress(ctx, base + 0.15 * i))
        rule_id = f"{ctx.sid}-rule"
        m.rule(rule_id, _compress(ctx, base + 0.55))
        if texts["sub"]:
            m.text(f"{ctx.sid}-sub", _compress(ctx, base + 0.95))
        view["card"] = None
        view["col"] = {**col, **texts, "rule": rule_id}
    return view


def _chip_rows(ctx: SceneContext, chips: list[str], box_w: float, max_rows: int, *, column: bool) -> tuple[int, list[list[int]], bool]:
    """Font size and row layout for the chips (indices per row)."""
    pad_h, gap = 30, 18
    base = ctx.size("item")
    for px in range(base, 27, -1):
        widths = [ctx.measure(c, "item", px) + 2 * pad_h for c in chips]
        if max(widths) > box_w * 0.95:
            continue
        rows: list[list[int]] = []
        if column:
            rows = [[i] for i in range(len(chips))]
        else:
            current: list[int] = []
            used = 0.0
            for i, w in enumerate(widths):
                need = w if not current else used + gap + w
                if current and need > box_w * 0.95:
                    rows.append(current)
                    current, used = [i], w
                else:
                    current.append(i)
                    used = need
            rows.append(current)
        if len(rows) <= max_rows:
            return px, rows, True
    return 28, [[i] for i in range(len(chips))], False


def option_chips(ctx: SceneContext, res: Resources, m: Motion, flags: dict[str, bool]) -> dict[str, Any]:
    F, s = ctx.frame, ctx.slots
    photo = None
    if s.get("assetId"):
        photo = _photo(ctx, res, s["assetId"], "photo", (0, 0, F.w, F.h))
        m.photo(photo["img_id"], ctx.duration, "in")
    pad_v, pad_h = CARD_PAD[F.name]
    if photo is not None:
        box_w = min(1180 if F.name == "landscape" else F.content_w, F.content_w) - 2 * pad_h
    else:
        box_w = min(1400, F.content_w)
    column = F.name == "portrait"
    max_rows = {"landscape": 2, "portrait": 6, "square": 3}[F.name]
    px, rows, fits = _chip_rows(ctx, s["chips"], box_w, max_rows, column=column)
    if not fits:
        ctx.warnings.append(f"text_fit:{ctx.sid}.chips: the chips do not fit {int(box_w)}px in {max_rows} row(s); shorten them")
    title = ctx.text("title", s.get("title"), "head", "title", box_w, 2, min_ratio=0.6)
    t = _t0(flags) + 0.15
    if title:
        m.text(f"{ctx.sid}-title", _compress(ctx, t))
    times = item_beats(s["chips"], ctx.words, earliest=_compress(ctx, t + 0.45), latest=_latest_item(ctx))
    chip_ids = [f"{ctx.sid}-chip{i + 1}" for i in range(len(s["chips"]))]
    for el_id, at in zip(chip_ids, times):
        m.item(el_id, at)
    panel_id = f"{ctx.sid}-panel"
    if photo is not None:
        m.card(panel_id, _compress(ctx, _t0(flags)))
    decor_id = f"{ctx.sid}-decor"
    if photo is None:
        m.drift(decor_id, ctx.duration)
    return {
        "photo": photo,
        "panel": {"id": panel_id, "pad": f"{pad_v}px {pad_h}px", "on_photo": photo is not None},
        "title": title,
        "chip_px": px,
        "rows": [[{"id": chip_ids[i], "text": s["chips"][i]} for i in row] for row in rows],
        "decor": decor_id,
        "box_w": int(box_w),
    }


def swatches(ctx: SceneContext, res: Resources, m: Motion, flags: dict[str, bool]) -> dict[str, Any]:
    F, s = ctx.frame, ctx.slots
    items = s["swatches"]
    n = len(items)
    if F.name == "landscape":
        cols, dot, gap = n, 170 if n <= 5 else 150, 36
        col_w = min(280, int((F.content_w - gap * (n - 1)) / n))
    elif F.name == "portrait":
        cols, dot, gap = 2, 190, 60
        col_w = int((F.content_w - gap) / 2)
    else:
        cols, dot, gap = 3, 150, 40
        col_w = int((F.content_w - 2 * gap) / 3)
    cols = min(cols, n)
    labels = []
    for i, sw in enumerate(items):
        text = ctx.text(f"swatches.{i}.label", sw["label"], "item", "label", col_w - 8, 2, min_ratio=0.9)
        labels.append(text)
    title = ctx.text("title", s.get("title"), "head", "title", F.content_w, 2, min_ratio=0.6)
    t = _t0(flags) + 0.15
    if title:
        m.text(f"{ctx.sid}-title", _compress(ctx, t))
    ids = [f"{ctx.sid}-sw{i + 1}" for i in range(n)]
    times = item_beats([sw["label"] for sw in items], ctx.words, earliest=_compress(ctx, t + 0.4), latest=_latest_item(ctx))
    for el_id, at in zip(ids, times):
        m.item(el_id, at)
    ring = None
    if "highlight" in s:
        ring = f"{ctx.sid}-ring"
        m.pop(ring, _compress(ctx, max(times[-1] + 0.5, ctx.duration * 0.62)))
    decor_id = f"{ctx.sid}-decor"
    m.drift(decor_id, ctx.duration)
    rows = [list(range(i, min(i + cols, n))) for i in range(0, n, cols)]
    return {
        "title": title,
        "rows": [
            [
                {"id": ids[i], "color": items[i]["color"], "label": labels[i], "ring": ring if s.get("highlight") == i else None}
                for i in row
            ]
            for row in rows
        ],
        "dot": dot,
        "col_w": col_w,
        "gap": gap,
        "decor": decor_id,
    }


def _tone_vars(ctx: SceneContext) -> dict[str, str]:
    tone = ctx.slots.get("tone", "plain")
    return {
        "plain": {"bgc": "var(--bg)", "fg": "var(--ink)", "fg2": "var(--muted)", "kick": "var(--accent)"},
        "inverse": {"bgc": "var(--ink)", "fg": "var(--bg)", "fg2": "var(--bg)", "kick": "var(--bg)"},
        "accent": {"bgc": "var(--accent)", "fg": "var(--accent-ink)", "fg2": "var(--accent-ink)", "kick": "var(--accent-ink)"},
    }[tone]


def text_card(ctx: SceneContext, res: Resources, m: Motion, flags: dict[str, bool]) -> dict[str, Any]:
    F, s = ctx.frame, ctx.slots
    box_w = {"landscape": 1320, "portrait": F.content_w, "square": F.content_w}[F.name]
    texts = {
        "over": ctx.text("overline", s.get("overline"), "over", "over", box_w, 1),
        "head": ctx.text("headline", s.get("headline"), "head", "head_xl", box_w, 3, min_ratio=0.55),
        "sub": ctx.text("subline", s.get("subline"), "sub", "sub", box_w, 2, min_ratio=0.82),
    }
    t = _t0(flags) + 0.1
    for i, key in enumerate(("over", "head")):
        if texts[key]:
            m.text(f"{ctx.sid}-{key}", _compress(ctx, t + 0.15 * i))
    rule_id = f"{ctx.sid}-rule"
    m.rule(rule_id, _compress(ctx, t + 0.55))
    if texts["sub"]:
        m.text(f"{ctx.sid}-sub", _compress(ctx, t + 0.9))
    decor_id = f"{ctx.sid}-decor"
    m.drift(decor_id, ctx.duration)
    return {**texts, "rule": rule_id, "tone": _tone_vars(ctx), "decor": decor_id}


def offer_card(ctx: SceneContext, res: Resources, m: Motion, flags: dict[str, bool]) -> dict[str, Any]:
    F, s = ctx.frame, ctx.slots
    box_w = min(1500, F.content_w)
    texts = {
        "over": ctx.text("overline", s.get("overline"), "over", "over", box_w, 1),
        "offer": ctx.text("offer", s.get("offer"), "head", "big", box_w, 2, min_ratio=0.5),
        "terms": ctx.text("terms", s.get("terms"), "sub", "sub", box_w, 2, min_ratio=0.82),
        "badge": ctx.text("badge", s.get("badge"), "item", "badge", 420, 1, min_ratio=0.9),
    }
    t = _t0(flags) + 0.1
    if texts["badge"]:
        m.pop(f"{ctx.sid}-badge", _compress(ctx, t))
    if texts["over"]:
        m.text(f"{ctx.sid}-over", _compress(ctx, t + 0.2))
    m.pop(f"{ctx.sid}-offer", _compress(ctx, t + 0.35))
    if texts["terms"]:
        m.text(f"{ctx.sid}-terms", _compress(ctx, t + 1.0))
    decor_id = f"{ctx.sid}-decor"
    m.drift(decor_id, ctx.duration)
    return {**texts, "decor": decor_id}


def steps(ctx: SceneContext, res: Resources, m: Motion, flags: dict[str, bool]) -> dict[str, Any]:
    F, s = ctx.frame, ctx.slots
    items = s["steps"]
    n = len(items)
    row = F.name == "landscape"
    circle = {"landscape": 84, "portrait": 92, "square": 76}[F.name]
    if row:
        gap = 48
        label_w = min(440, int((F.content_w - gap * (n - 1)) / n))
    else:
        gap = 0
        label_w = F.content_w - circle - 32
    labels = [ctx.text(f"steps.{i}", text, "item", "item", label_w, 2, min_ratio=0.85) for i, text in enumerate(items)]
    title = ctx.text("title", s.get("title"), "head", "title", F.content_w, 2, min_ratio=0.6)
    t = _t0(flags) + 0.15
    if title:
        m.text(f"{ctx.sid}-title", _compress(ctx, t))
    ids = [f"{ctx.sid}-step{i + 1}" for i in range(n)]
    times = item_beats(items, ctx.words, earliest=_compress(ctx, t + 0.45), latest=_latest_item(ctx))
    for el_id, at in zip(ids, times):
        m.item(el_id, at)
    decor_id = f"{ctx.sid}-decor"
    m.drift(decor_id, ctx.duration)
    return {
        "title": title,
        "row": row,
        "circle": circle,
        "gap": gap,
        "label_w": label_w,
        "num_px": ctx.size("num"),
        "entries": [{"id": ids[i], "n": i + 1, "label": labels[i]} for i in range(n)],
        "decor": decor_id,
    }


def before_after(ctx: SceneContext, res: Resources, m: Motion, flags: dict[str, bool]) -> dict[str, Any]:
    F, s = ctx.frame, ctx.slots
    full = (0, 0, F.w, F.h)
    before = _photo(ctx, res, s["beforeAssetId"], "before", full, "beforeFocus", "beforeAssetId")
    after = _photo(ctx, res, s["afterAssetId"], "after", full, "afterFocus", "afterAssetId")
    labels = {
        "before": ctx.text("beforeLabel", s.get("beforeLabel", "Before"), "item", "item", 360, 1, min_ratio=0.85),
        "after": ctx.text("afterLabel", s.get("afterLabel", "After"), "item", "item", 360, 1, min_ratio=0.85),
    }
    wipe_at = min(max(0.42 * ctx.duration, 1.2), max(0.5, ctx.duration - 1.8))
    m.fade(f"{ctx.sid}-blabel", _compress(ctx, _t0(flags) + 0.1))
    win = f"{ctx.sid}-win"
    m.tw.from_to(f"#{win}", {"xPercent": 100}, {"xPercent": 0, "duration": 1.1, "ease": "power2.inOut"}, wipe_at)
    m.tw.from_to(f"#{after['img_id']}", {"xPercent": -100}, {"xPercent": 0, "duration": 1.1, "ease": "power2.inOut"}, wipe_at)
    m.tw.to(f"#{ctx.sid}-blabel", {"opacity": 0, "duration": 0.3, "ease": "power1.in"}, wipe_at + 0.25)
    m.fade(f"{ctx.sid}-alabel", _compress(ctx, wipe_at + 0.8))
    m.photo(before["img_id"], ctx.duration, "in")
    card = None
    if s.get("headline"):
        texts = {"over": None, "head": ctx.text("headline", s["headline"], "head", "head", _card_text_w(ctx), 2, min_ratio=0.58), "sub": None}
        card = _card_view(ctx, texts, m, min(wipe_at + 1.0, ctx.duration - 1.2))
    return {"before": before, "after": after, "win": win, "labels": labels, "card": card}


def town_card(ctx: SceneContext, res: Resources, m: Motion, flags: dict[str, bool]) -> dict[str, Any]:
    F, s = ctx.frame, ctx.slots
    photo = None
    if s.get("assetId"):
        photo = _photo(ctx, res, s["assetId"], "photo", (0, 0, F.w, F.h))
        m.photo(photo["img_id"], ctx.duration, "in")
    pad_v, pad_h = CARD_PAD[F.name]
    box_w = min(1100, F.content_w - (2 * pad_h if photo else 0))
    texts = {
        "over": ctx.text("overline", s.get("overline"), "over", "over", box_w, 1),
        "town": ctx.text("town", s.get("town"), "head", "big", box_w, 2, min_ratio=0.5),
        "sub": ctx.text("subline", s.get("subline"), "sub", "sub", box_w, 2, min_ratio=0.82),
    }
    t = _t0(flags) + 0.1
    block = f"{ctx.sid}-block"
    if photo is not None:
        m.card(block, _compress(ctx, t))
    m.pop(f"{ctx.sid}-pin", _compress(ctx, t + 0.15))
    if texts["over"]:
        m.text(f"{ctx.sid}-over", _compress(ctx, t + 0.3))
    m.text(f"{ctx.sid}-town", _compress(ctx, t + 0.45))
    if texts["sub"]:
        m.text(f"{ctx.sid}-sub", _compress(ctx, t + 1.0))
    decor_id = f"{ctx.sid}-decor"
    if photo is None:
        m.drift(decor_id, ctx.duration)
    return {"photo": photo, "block": block, "pad": f"{pad_v}px {pad_h}px", "decor": decor_id, **texts}


def cta_endcard(ctx: SceneContext, res: Resources, m: Motion, flags: dict[str, bool]) -> dict[str, Any]:
    F, s = ctx.frame, ctx.slots
    brand = res.brand
    photo = None
    if s.get("assetId"):
        box = {
            "landscape": (1160, 0, F.w - 1160, F.h),
            "portrait": (0, 0, F.w, 760),
            "square": (0, 0, F.w, 420),
        }[F.name]
        photo = _photo(ctx, res, s["assetId"], "photo", box)
        m.photo(photo["img_id"], ctx.duration, "in")
    if F.name == "landscape":
        col_w = 960 if photo else 1400
        col = f"left:{F.pad_x}px;top:{F.pad_top}px;width:{col_w}px;height:{F.safe_h}px"
        justify = "center"
    else:
        top = (820 if F.name == "portrait" else 470) if photo else F.pad_top
        bottom = F.h - F.pad_bottom
        col_w = F.content_w
        col = f"left:{F.pad_x}px;top:{top}px;width:{col_w}px;height:{bottom - top}px"
        justify = "start" if photo else "center"
    texts = {
        "over": ctx.text("overline", s.get("overline"), "over", "over", col_w, 1),
        # The CTA is the brief's, word for word (up to 120 characters): it is
        # never cut, only shrunk and wrapped (two lines while they stay legible).
        "cta": ctx.text_ladder("cta", s.get("cta"), "head", "cta", col_w),
        "website": ctx.text("website", brand.website, "pill", "pill", min(col_w, 900) - 96, 1, min_ratio=0.75),
    }
    step_texts = [ctx.text(f"steps.{i}", t_, "item", "item", 300, 1, min_ratio=0.85) for i, t_ in enumerate(s.get("steps") or [])]
    mark = None if brand.logo_src else ctx.text("brand", brand.name, "mark", "mark", min(col_w, 700), 1, min_ratio=1.0)
    cover = None
    t = _t0(flags) + 0.1
    if photo is not None:
        cover = {"id": f"{ctx.sid}-cover", "box": photo["box"], "bars": REVEAL_BARS}
        m.reveal(cover["id"], t, first=not flags["tin"])
    if texts["over"]:
        m.text(f"{ctx.sid}-over", _compress(ctx, t + 0.2))
    m.text(f"{ctx.sid}-cta", _compress(ctx, t + 0.35))
    step_ids = [f"{ctx.sid}-step{i + 1}" for i in range(len(step_texts))]
    times = item_beats(s.get("steps") or [], ctx.words, earliest=_compress(ctx, t + 1.0), latest=max(0.6, ctx.duration - 2.4))
    for el_id, at in zip(step_ids, times):
        m.item(el_id, at)
    pill_at = _compress(ctx, max(t + 1.3, (times[-1] + 0.4) if times else 0))
    pill_at = min(pill_at, max(0.3, ctx.duration - 2.0))
    if texts["website"]:
        m.pop(f"{ctx.sid}-pill", pill_at)
        m.text(f"{ctx.sid}-brand", min(pill_at + 0.4, max(0.4, ctx.duration - 1.6)))
        if ctx.duration - pill_at > 2.6:
            m.pulse(f"{ctx.sid}-pill", pill_at + 1.4)
    else:
        # No website: the lock-up closes the card and takes the pill's beat.
        m.pop(f"{ctx.sid}-brand", pill_at)
    return {
        "photo": photo,
        "cover": cover,
        "col": col,
        "justify": justify,
        "steps": [{"id": step_ids[i], "n": i + 1, "label": step_texts[i]} for i in range(len(step_texts))],
        "mark": mark,
        "logo": brand.logo_src,
        "logo_h": {"landscape": 76, "portrait": 84, "square": 64}[F.name],
        **texts,
    }


KIND_BUILDERS: dict[str, Callable[[SceneContext, Resources, Motion, dict[str, bool]], dict[str, Any]]] = {
    "photo_pan": photo_pan,
    "photo_reveal": photo_reveal,
    "option_chips": option_chips,
    "swatches": swatches,
    "text_card": text_card,
    "offer_card": offer_card,
    "steps": steps,
    "before_after": before_after,
    "town_card": town_card,
    "cta_endcard": cta_endcard,
}
