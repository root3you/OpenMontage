"""Build a HyperFrames project from a KoverIQ scene plan (the W1 contract).

    build_composition(scene_plan, script, timings, assets, style, fmt, brand, out_dir) -> CompositionResult
    apply_params(comp_dir, params) -> None

Inputs
- scene_plan: OpenMontage scene_plan whose scenes also carry `kind` and
  `slots` (inline, or in metadata.koveriq.scenes — see koveriq.scenes).
- script: OpenMontage script (its title names the composition).
- timings: {sceneId: {"startMs", "endMs", "words": [{"w", "startMs", "endMs"}]}}
  on the final video timeline: integer ms, the first scene starts at 0, each
  scene starts where the previous one ends, every scene lasts >= 1.5 s, words
  lie inside their scene.
- assets: {assetId: Path} to EXIF-stripped JPEG/PNG/WebP photos. Optional
  reserved key "@narration": a full-length narration audio file aligned to
  t=0 (HyperFrames then mixes it in; without it the composition is silent).
- style: "clean" | "bold_offer"; fmt: "16:9" | "9:16" | "1:1".
- brand: {"companyName", "website", "logoPath"?: Path, "palette"?: {bg,
  surface, ink, muted, accent, accentInk as #RRGGBB}}.

Output (out_dir): index.html (root), compositions/<sceneId>.html (one
sub-composition per scene, plus brand.html), assets/ (copied photos, logo,
narration, gsap.min.js), .koveriq/build.json (what apply_params rebuilds from).
Nothing here touches the network or runs a browser.
"""

from __future__ import annotations

import copy
import json
import pathlib
import re
import shutil
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping, Optional

import jsonschema
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup
from PIL import Image, UnidentifiedImageError

from koveriq.kinds import BARS, KIND_BUILDERS, BrandView, Motion, PhotoInfo, Resources
from koveriq.layout import FRAMES, SceneContext, Tweens, num, scene_words
from koveriq.scenes import (
    TEXT_SLOTS,
    from_checkpoint_scene_plan,
    scene_asset_ids,
    scene_plan_errors,
    slot_errors,
)
from koveriq.styles import STYLES as STYLE_DEFS
from koveriq.styles import merge_palette, palette_warnings, rgba
from koveriq.textfit import fit_text
from koveriq.vendor import GsapUnavailable, verified_gsap

PACKAGE_DIR = pathlib.Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
PARAMS_SCHEMA_PATH = PACKAGE_DIR / "params.schema.json"

STYLES = tuple(STYLE_DEFS)
FORMATS = tuple(FRAMES)
NARRATION_KEY = "@narration"
MIN_SCENE_MS = 1500
STATE_FILE = pathlib.Path(".koveriq") / "build.json"

_SCENE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
_RESERVED_IDS = {"main", "root", "brand", "narration"}
_IMAGE_EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac"}
_LINE = re.compile(r"^[^\s\x00-\x1f\x7f](?:[^\x00-\x1f\x7f]*[^\s\x00-\x1f\x7f])?$")


@dataclass
class CompositionResult:
    index_html: pathlib.Path
    duration_ms: int
    hook_time_ms: int
    lint_warnings: list[str]


class CompositionError(ValueError):
    """Invalid inputs or params. `errors` lists every problem found."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


# ---------------------------------------------------------------------------
# validation


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _timing_errors(scenes: list[dict[str, Any]], timings: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(timings, Mapping):
        return ["timings: must be an object keyed by scene id"], warnings
    previous_end: Optional[int] = None
    for index, scene in enumerate(scenes):
        sid = scene.get("id")
        timing = timings.get(sid)
        if not isinstance(timing, Mapping):
            errors.append(f"{sid}: no timings for this scene")
            previous_end = None
            continue
        start, end = timing.get("startMs"), timing.get("endMs")
        if not (_is_int(start) and _is_int(end)):
            errors.append(f"{sid}: startMs and endMs must be integer milliseconds")
            previous_end = None
            continue
        if index == 0 and start != 0:
            errors.append(f"{sid}: the first scene must start at 0 ms, not {start}")
        if previous_end is not None and start != previous_end:
            errors.append(f"{sid}: timings must be contiguous; it starts at {start} ms but the previous scene ends at {previous_end} ms")
        if end - start < MIN_SCENE_MS:
            errors.append(f"{sid}: a scene must last at least {MIN_SCENE_MS} ms, not {end - start}")
        words = timing.get("words", [])
        if not isinstance(words, list):
            errors.append(f"{sid}: words must be a list")
        else:
            for i, word in enumerate(words):
                if not (isinstance(word, Mapping) and isinstance(word.get("w"), str) and _is_int(word.get("startMs")) and _is_int(word.get("endMs"))):
                    errors.append(f"{sid}.words[{i}]: needs w (string), startMs and endMs (integer ms)")
                elif not (start - 50 <= word["startMs"] <= word["endMs"] <= end + 50):
                    warnings.append(f"word_outside_scene:{sid}.words[{i}]: {word['w']!r} lies outside the scene and is ignored for beats")
        previous_end = end
    return errors, warnings


def _brand_errors(brand: Any) -> list[str]:
    if not isinstance(brand, Mapping):
        return ["brand: must be an object"]
    errors = []
    for key, limit in (("companyName", 60), ("website", 80)):
        value = brand.get(key)
        if not isinstance(value, str) or not _LINE.match(value) or len(value) > limit:
            errors.append(f"brand.{key}: required, one trimmed line of at most {limit} characters")
    if isinstance(brand.get("website"), str) and re.search(r"\s", brand["website"]):
        errors.append("brand.website: must not contain spaces")
    logo = brand.get("logoPath")
    if logo is not None:
        path = pathlib.Path(logo)
        if not path.is_file():
            errors.append(f"brand.logoPath: {path} does not exist")
        elif path.suffix.lower() != ".svg" and _image_info(path) is None:
            errors.append(f"brand.logoPath: {path} is not a readable PNG, JPEG, WebP or SVG")
    return errors


def _image_info(path: pathlib.Path) -> Optional[tuple[str, int, int]]:
    try:
        with Image.open(path) as image:
            image.load()
            if image.format not in _IMAGE_EXT:
                return None
            return image.format, image.width, image.height
    except (OSError, UnidentifiedImageError, ValueError):
        return None


def _display_website(website: str) -> str:
    return re.sub(r"^https?://", "", website).rstrip("/")


# ---------------------------------------------------------------------------
# rendering


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _apply_scene_params(scene: dict[str, Any], params: Mapping[str, Any]) -> tuple[dict[str, Any], float]:
    slots = copy.deepcopy(scene["slots"])
    for slot, text in (params.get("shorten_text") or {}).items():
        slots[slot] = text
    focus = params.get("crop_focus")
    if focus:
        point = {"x": focus["x"], "y": focus["y"]}
        for key in ("focus", "beforeFocus", "afterFocus"):
            if key == "focus" and scene["kind"] == "before_after":
                continue
            if key != "focus" and scene["kind"] != "before_after":
                continue
            slots[key] = dict(point)
    return slots, float(params.get("font_scale", 1.0))


def _render(out_dir: pathlib.Path, state: dict[str, Any]) -> list[str]:
    style = STYLE_DEFS[state["style"]]
    frame = FRAMES[state["fmt"]]
    brand = state["brand"]
    palette, _ = merge_palette(style, brand.get("palette"))
    warnings: list[str] = list(state.get("input_warnings", []))
    warnings.extend(palette_warnings(palette))

    resources = Resources(
        photos={aid: PhotoInfo(**info) for aid, info in state["photos"].items()},
        brand=BrandView(
            name=brand["companyName"],
            website=_display_website(brand["website"]),
            logo_src=brand.get("logo"),
            logo_w=brand.get("logoW", 0),
            logo_h=brand.get("logoH", 0),
        ),
    )
    env = _env()
    roles = {name: Markup(role.css()) for name, role in style.roles.items()}
    shade = rgba(palette["ink"] if style.name == "clean" else palette["bg"], 0.55 if style.name == "clean" else 0.75)
    decor = rgba(palette["ink"], 0.06) if style.name == "clean" else rgba(palette["accent"], 0.16)
    style_css = Markup(
        env.get_template(f"styles/{style.name}.css.j2").render(roles=roles, radius=style.radius, F=frame, shade=Markup(shade), decor=Markup(decor))
    )
    head, body = style.roles["head"], style.roles["sub"]
    root_vars = Markup(
        " ".join(
            [
                f"--bg: {palette['bg']};",
                f"--surface: {palette['surface']};",
                f"--ink: {palette['ink']};",
                f"--muted: {palette['muted']};",
                f"--accent: {palette['accent']};",
                f"--accent-ink: {palette['accentInk']};",
                f'font-family: "{body.family}", sans-serif;',
            ]
        )
    )

    comps = out_dir / "compositions"
    if comps.exists():
        shutil.rmtree(comps)
    comps.mkdir(parents=True)

    scenes = state["scene_plan"]["scenes"]
    timings = state["timings"]
    params = state["params"]["scenes"]
    hosts = []
    for index, scene in enumerate(scenes):
        sid, kind = scene["id"], scene["kind"]
        timing = timings[sid]
        duration = (timing["endMs"] - timing["startMs"]) / 1000
        slots, font_scale = _apply_scene_params(scene, params.get(sid, {}))
        ctx = SceneContext(
            sid=sid,
            kind=kind,
            slots=slots,
            style=style,
            frame=frame,
            duration=duration,
            words=scene_words(timing),
            font_scale=font_scale,
        )
        tweens = Tweens()
        motion = Motion(style.name, tweens, sid)
        flags = {"tin": index > 0, "tout": index < len(scenes) - 1}
        view = KIND_BUILDERS[kind](ctx, resources, motion, flags)
        if flags["tin"]:
            motion.transition_in()
        if flags["tout"]:
            motion.transition_out(duration)
        html = env.get_template(f"kinds/{kind}.html.j2").render(
            sid=sid,
            kind=kind,
            F=frame,
            v=view,
            root_vars=root_vars,
            style_css=style_css,
            style_name=style.name,
            radius=style.radius,
            tin=flags["tin"],
            tout=flags["tout"],
            transition=style.transition,
            bars=BARS,
            tweens=[Markup(line) for line in tweens.lines],
        )
        (comps / f"{sid}.html").write_text(html, encoding="utf-8")
        warnings.extend(ctx.warnings)
        hosts.append({"id": sid, "start": num(timing["startMs"] / 1000), "duration": num(duration), "track": 1})

    total_ms = timings[scenes[-1]["id"]]["endMs"]
    last = scenes[-1]
    brand_end_ms = timings[last["id"]]["startMs"] if last["kind"] == "cta_endcard" and len(scenes) > 1 else total_ms
    if brand_end_ms >= 1500:
        hosts.append({"id": "brand", "start": "0", "duration": num(brand_end_ms / 1000), "track": 2})
        (comps / "brand.html").write_text(_brand_bug(env, style, frame, palette, resources.brand, brand_end_ms / 1000, warnings), encoding="utf-8")

    title = (state.get("title") or brand["companyName"]).strip() or "KoverIQ video"
    index_html = env.get_template("root.html.j2").render(
        F=frame,
        title=title,
        bg=palette["bg"],
        total=num(total_ms / 1000),
        hosts=hosts,
        narration=state.get("narration"),
    )
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    return warnings


def _brand_bug(env: Environment, style, frame, palette, brand: BrandView, end_s: float, warnings: list[str]) -> str:
    mark_role = style.roles["mark"]
    place = {"landscape": (56, 44), "portrait": (64, 150), "square": (48, 40)}[frame.name]
    mark = None
    if not brand.logo_src:
        fit = fit_text(
            brand.name,
            family=mark_role.family,
            weight=mark_role.weight,
            box_w=640,
            max_lines=1,
            base_px=28,
            min_px=22,
            uppercase=mark_role.upper,
            letter_spacing_em=mark_role.tracking,
        )
        if not fit.fits:
            warnings.append("text_fit:brand.companyName: the company name is too long for the corner mark")
        elif fit.px < 28:
            warnings.append(f"text_floor:brand.companyName: the corner mark is {fit.px}px, below the 28px phone floor")
        from koveriq.layout import Text

        mark = Text(slot="companyName", lines=fit.lines[:1], px=fit.px, width=int(fit.width / 0.95 + 4), fits=fit.fits)
    return env.get_template("brand.html.j2").render(
        F=frame,
        left=place[0],
        top=place[1],
        pad="12px 18px",
        radius=style.radius,
        chip_bg=palette["surface"],
        mark_css=Markup(mark_role.css()),
        mark_color=palette["ink"],
        logo=brand.logo_src,
        logo_h=40,
        mark=mark,
        fade_out=num(max(0.9, end_s - 0.35)),
    )


# ---------------------------------------------------------------------------
# public API


def build_composition(
    scene_plan: dict,
    script: dict,
    timings: dict,
    assets: dict[str, pathlib.Path],
    style: str,
    fmt: str,
    brand: dict,
    out_dir: pathlib.Path,
) -> CompositionResult:
    """Write a HyperFrames project for one style and format into out_dir."""
    errors: list[str] = []
    if style not in STYLE_DEFS:
        errors.append(f"style: {style!r} is not one of {list(STYLES)}")
    if fmt not in FRAMES:
        errors.append(f"fmt: {fmt!r} is not one of {list(FORMATS)}")
    plan = from_checkpoint_scene_plan(scene_plan if isinstance(scene_plan, dict) else {})
    errors.extend(scene_plan_errors(plan))
    scenes = [s for s in plan.get("scenes") or [] if isinstance(s, dict)]
    for scene in scenes:
        sid = scene.get("id")
        if not isinstance(sid, str) or not _SCENE_ID.match(sid) or sid in _RESERVED_IDS:
            errors.append(f"{sid!r}: scene ids must match {_SCENE_ID.pattern} and not be one of {sorted(_RESERVED_IDS)}")
    timing_errors, timing_warnings = _timing_errors(scenes, timings)
    errors.extend(timing_errors)
    errors.extend(_brand_errors(brand))
    palette_errors = merge_palette(STYLE_DEFS.get(style, STYLE_DEFS["clean"]), brand.get("palette") if isinstance(brand, Mapping) else None)[1]
    errors.extend(palette_errors)

    assets = dict(assets or {})
    referenced: dict[str, pathlib.Path] = {}
    photo_meta: dict[str, tuple[str, int, int]] = {}
    for scene in scenes:
        for asset_id in scene_asset_ids(scene):
            if asset_id in referenced or not isinstance(asset_id, str):
                continue
            if asset_id not in assets:
                errors.append(f"{scene.get('id')}: no asset {asset_id!r} was supplied")
                continue
            path = pathlib.Path(assets[asset_id])
            info = _image_info(path) if path.is_file() else None
            if info is None:
                errors.append(f"asset {asset_id}: {path} is not a readable JPEG, PNG or WebP image")
                continue
            referenced[asset_id] = path
            photo_meta[asset_id] = info
    narration = assets.get(NARRATION_KEY)
    if narration is not None:
        narration = pathlib.Path(narration)
        if not narration.is_file() or narration.suffix.lower() not in _AUDIO_EXT:
            errors.append(f"assets[{NARRATION_KEY!r}]: must be an existing {sorted(_AUDIO_EXT)} file")
    try:
        gsap = verified_gsap()
    except GsapUnavailable as exc:
        errors.append(str(exc))
    if errors:
        raise CompositionError(errors)

    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    asset_root = out_dir / "assets"
    for sub in ("img", "brand", "audio", "vendor"):
        if (asset_root / sub).exists():
            shutil.rmtree(asset_root / sub)
    (asset_root / "img").mkdir(parents=True)
    (asset_root / "vendor").mkdir(parents=True)
    (asset_root / "vendor" / "gsap.min.js").write_bytes(gsap)

    photos = {}
    for asset_id, path in referenced.items():
        fmt_name, width, height = photo_meta[asset_id]
        rel = f"assets/img/{asset_id}{_IMAGE_EXT[fmt_name]}"
        shutil.copyfile(path, out_dir / rel)
        photos[asset_id] = {"src": rel, "w": width, "h": height}

    brand_state: dict[str, Any] = {
        "companyName": brand["companyName"],
        "website": brand["website"],
        "palette": dict(brand.get("palette") or {}),
    }
    if brand.get("logoPath"):
        logo = pathlib.Path(brand["logoPath"])
        info = _image_info(logo) if logo.suffix.lower() != ".svg" else ("SVG", 0, 0)
        ext = ".svg" if info[0] == "SVG" else _IMAGE_EXT[info[0]]
        (asset_root / "brand").mkdir(parents=True)
        rel = f"assets/brand/logo{ext}"
        shutil.copyfile(logo, out_dir / rel)
        brand_state.update(logo=rel, logoW=info[1], logoH=info[2])

    narration_rel = None
    if narration is not None:
        (asset_root / "audio").mkdir(parents=True)
        narration_rel = f"assets/audio/narration{narration.suffix.lower()}"
        shutil.copyfile(narration, out_dir / narration_rel)

    state = {
        "version": 1,
        "style": style,
        "fmt": fmt,
        "title": (script or {}).get("title", "") if isinstance(script, Mapping) else "",
        "scene_plan": {"scenes": scenes},
        "timings": {s["id"]: dict(timings[s["id"]]) for s in scenes},
        "photos": photos,
        "brand": brand_state,
        "narration": narration_rel,
        "params": {"scenes": {}},
        "input_warnings": timing_warnings,
    }
    warnings = _render(out_dir, state)
    _save_state(out_dir, state, warnings)
    first = state["timings"][scenes[0]["id"]]
    return CompositionResult(
        index_html=out_dir / "index.html",
        duration_ms=sum(t["endMs"] - t["startMs"] for t in state["timings"].values()),
        hook_time_ms=(first["startMs"] + first["endMs"]) // 2,
        lint_warnings=warnings,
    )


def _save_state(out_dir: pathlib.Path, state: dict[str, Any], warnings: list[str]) -> None:
    path = out_dir / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    saved = {**state, "lint_warnings": warnings}
    path.write_text(json.dumps(saved, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


@lru_cache(maxsize=1)
def load_params_schema() -> dict[str, Any]:
    with open(PARAMS_SCHEMA_PATH, encoding="utf-8") as handle:
        return json.load(handle)


_WORD = re.compile(r"[0-9A-Za-zÀ-ɏ]+")
# Slots that state a fact or must match the brief word for word.
FIXED_SLOTS = {"cta", "offer", "terms", "badge", "town"}
# Words whose removal flips or widens a claim.
NEGATIONS = {"no", "not", "never", "without", "non", "none", "nothing", "nor", "cannot"}
QUALIFIERS = {"only", "from", "up", "excludes", "excluding", "except", "min", "minimum", "max", "maximum", "starting", "plus", "selected"}


def _words(text: str) -> list[str]:
    return [w.casefold() for w in _WORD.findall(text)]


def _is_subsequence(short: list[str], long: list[str]) -> bool:
    it = iter(long)
    return all(any(word == candidate for candidate in it) for word in short)


def params_errors(state: dict[str, Any], params: Any) -> list[str]:
    """Problems with a review revision against a built composition."""
    validator = jsonschema.Draft202012Validator(load_params_schema())
    errors = sorted(
        f"params.{'.'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}" for e in validator.iter_errors(params)
    )
    if errors:
        return errors
    scenes = {s["id"]: s for s in state["scene_plan"]["scenes"]}
    for sid, change in params["scenes"].items():
        scene = scenes.get(sid)
        if scene is None:
            errors.append(f"params.scenes.{sid}: no such scene")
            continue
        if "crop_focus" in change and not scene_asset_ids(scene):
            errors.append(f"params.scenes.{sid}.crop_focus: the {scene['kind']} scene shows no photo")
        for slot, text in (change.get("shorten_text") or {}).items():
            where = f"params.scenes.{sid}.shorten_text.{slot}"
            current = scene["slots"].get(slot)
            if slot in FIXED_SLOTS:
                errors.append(f"{where}: the {slot} slot states a fact or the brief's CTA and cannot be shortened")
                continue
            if slot not in TEXT_SLOTS[scene["kind"]] or not isinstance(current, str):
                errors.append(f"{where}: {scene['kind']} has no text slot {slot!r} to shorten")
                continue
            if len(text) >= len(current):
                errors.append(f"{where}: must be shorter than the current {len(current)} characters")
            old_words, new_words = _words(current), _words(text)
            if not _is_subsequence(new_words, old_words):
                errors.append(f"{where}: may only drop words from {current!r}, not add or change them")
                continue
            kept = set(new_words)
            for group, label in ((NEGATIONS, "negation"), (QUALIFIERS, "qualifier")):
                dropped = sorted({w for w in old_words if w in group} - kept)
                if dropped:
                    errors.append(f"{where}: would drop the {label} {dropped}, which changes the claim")
            figures = {w for w in old_words if any(ch.isdigit() for ch in w)}
            shown = {w for w in new_words if any(ch.isdigit() for ch in w)}
            if shown and shown != figures:
                errors.append(f"{where}: keep all the figures {sorted(figures)} or none of them")
        if not errors:
            slots, _ = _apply_scene_params(scene, change)
            errors.extend(slot_errors({"kind": scene["kind"], "slots": slots}, prefix=f"params.scenes.{sid}"))
    return errors


def apply_params(comp_dir: pathlib.Path, params: dict) -> None:
    """Apply the review step's one revision and rewrite the composition.

    params = {"scenes": {sceneId: {"crop_focus"?: {x, y}, "shorten_text"?:
    {slot: shorter text}, "font_scale"?: 0.8-1.0}}}. The revision replaces any
    earlier one (it is applied to the original slots), so calling again with
    the same params is idempotent. Raises CompositionError listing every
    problem; nothing is written then.
    """
    comp_dir = pathlib.Path(comp_dir)
    state_path = comp_dir / STATE_FILE
    if not state_path.is_file():
        raise CompositionError([f"{comp_dir}: no {STATE_FILE}; build the composition with build_composition first"])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    errors = params_errors(state, params)
    if errors:
        raise CompositionError(errors)
    state["params"] = json.loads(json.dumps(params, sort_keys=True))
    state.pop("lint_warnings", None)
    warnings = _render(comp_dir, state)
    _save_state(comp_dir, state, warnings)
