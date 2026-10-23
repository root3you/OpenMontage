"""Scene grammar check (koveriq/scene_grammar.yaml)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

from koveriq.scenes import from_checkpoint_scene_plan

GRAMMAR_PATH = Path(__file__).resolve().parent / "scene_grammar.yaml"


@lru_cache(maxsize=1)
def load_grammar() -> dict[str, Any]:
    with open(GRAMMAR_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _grammar(video_type: str) -> dict[str, Any]:
    grammars = load_grammar()["grammars"]
    if video_type not in grammars:
        raise KeyError(f"no scene grammar for video type {video_type!r}; known: {sorted(grammars)}")
    return grammars[video_type]


def _assign(kinds: list[str], explicit: list[Optional[str]], roles: list[dict]) -> Optional[list[str]]:
    """Assign each scene to a role, in role order, honouring min/max and kinds."""
    n, count_roles = len(kinds), len(roles)
    memo: dict[tuple[int, int, int], Optional[tuple[str, ...]]] = {}

    def go(i: int, r: int, count: int) -> Optional[tuple[str, ...]]:
        key = (i, r, count)
        if key in memo:
            return memo[key]
        result: Optional[tuple[str, ...]] = None
        role = roles[r]
        if i == n:
            if count >= role["min"] and all(later["min"] == 0 for later in roles[r + 1 :]):
                result = ()
        else:
            if (
                count < role["max"]
                and kinds[i] in role["kinds"]
                and explicit[i] in (None, role["role"])
            ):
                rest = go(i + 1, r, count + 1)
                if rest is not None:
                    result = (role["role"],) + rest
            if result is None and count >= role["min"] and r + 1 < count_roles:
                result = go(i, r + 1, 0)
        memo[key] = result
        return result

    found = go(0, 0, 0)
    return list(found) if found is not None else None


def _scenes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in from_checkpoint_scene_plan(plan).get("scenes") or [] if isinstance(s, dict)]


def infer_roles(plan: dict[str, Any], video_type: str) -> Optional[list[str]]:
    """The role of each scene, or None when the order does not fit the grammar."""
    scenes = _scenes(plan)
    return _assign(
        [s.get("kind") for s in scenes],
        [s.get("role") for s in scenes],
        _grammar(video_type)["roles"],
    )


def grammar_errors(
    plan: dict[str, Any],
    video_type: str,
    target_seconds: int,
    *,
    total_seconds: Optional[float] = None,
) -> list[str]:
    """Every grammar problem with a scene plan (empty list when it fits).

    `total_seconds` (the sum of real scene spans after TTS) is checked against
    the length bounds when given.
    """
    grammar = _grammar(video_type)
    roles = grammar["roles"]
    scenes = _scenes(plan)
    kinds = [s.get("kind") for s in scenes]
    errors: list[str] = []

    bounds = grammar["lengths"].get(str(int(target_seconds))) if target_seconds == int(target_seconds) else None
    if bounds is None:
        errors.append(
            f"no {video_type} length bounds for {target_seconds} s; use one of {sorted(grammar['lengths'], key=int)}"
        )
    else:
        low, high = bounds["scenes"]["min"], bounds["scenes"]["max"]
        if not low <= len(scenes) <= high:
            errors.append(f"a {target_seconds} s {video_type} needs {low}-{high} scenes, got {len(scenes)}")
        if total_seconds is not None:
            s_low, s_high = bounds["seconds"]["min"], bounds["seconds"]["max"]
            if not s_low <= total_seconds <= s_high:
                errors.append(f"total length {total_seconds:.2f} s is outside {s_low}-{s_high} s for a {target_seconds} s video")

    if _assign(kinds, [s.get("role") for s in scenes], roles) is None:
        errors.append(f"scene order {kinds} does not fit the {video_type} grammar: {grammar['description']}")
        if kinds and kinds[0] not in roles[0]["kinds"]:
            errors.append(f"the first scene must be a {roles[0]['role']} ({' | '.join(roles[0]['kinds'])})")
        last = roles[-1]
        if last["min"] and (not kinds or kinds[-1] not in last["kinds"]):
            errors.append(f"the last scene must be a {' | '.join(last['kinds'])}")
        for role in roles:
            if role["min"] and not any(k in role["kinds"] for k in kinds):
                errors.append(f"no scene for the required role {role['role']!r} ({' | '.join(role['kinds'])})")
        role_names = {r["role"] for r in roles}
        for scene in scenes:
            if scene.get("role") and scene["role"] not in role_names:
                errors.append(f"{scene.get('id')}: unknown role {scene['role']!r}; roles are {[r['role'] for r in roles]}")
    return errors


_WORD = re.compile(r"[A-Za-z0-9À-ɏ]+(?:['’-][A-Za-z0-9À-ɏ]+)*")


def count_words(text: str) -> int:
    return len(_WORD.findall(text or ""))


def word_count_errors(script: dict[str, Any], video_type: str, target_seconds: int) -> list[str]:
    """Narration length check: target x 2.3-2.7 words per second."""
    bounds = _grammar(video_type)["lengths"].get(str(int(target_seconds)))
    if bounds is None:
        return [f"no {video_type} length bounds for {target_seconds} s"]
    words = sum(count_words(s.get("text", "")) for s in script.get("sections") or [])
    low, high = bounds["words"]["min"], bounds["words"]["max"]
    if not low <= words <= high:
        return [f"narration has {words} words; a {target_seconds} s video needs {low}-{high}"]
    return []
