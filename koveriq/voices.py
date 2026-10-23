"""The Piper voice allowlist (koveriq/voices.yaml)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

VOICES_PATH = Path(__file__).resolve().parent / "voices.yaml"
_REQUIRED = ("voiceId", "label", "dataset", "licenceUrl", "attributionText", "commercialUse", "files")


class VoiceNotAllowed(ValueError):
    """The voice is not on the KoverIQ allowlist."""


@lru_cache(maxsize=1)
def load_voices() -> dict[str, Any]:
    with open(VOICES_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def voices_errors(data: dict[str, Any]) -> list[str]:
    """Problems with an allowlist document (empty when valid)."""
    errors: list[str] = []
    voices = data.get("voices") or []
    if not voices:
        errors.append("voices: at least one voice is required")
    seen: set[str] = set()
    for i, voice in enumerate(voices):
        vid = voice.get("voiceId", f"voices[{i}]")
        for key in _REQUIRED:
            if voice.get(key) in (None, "", {}):
                errors.append(f"{vid}: {key} is required")
        if voice.get("commercialUse") is not True:
            errors.append(f"{vid}: commercialUse must be true to be listed")
        if not str(voice.get("licenceUrl", "")).startswith("https://"):
            errors.append(f"{vid}: licenceUrl must be an https URL")
        for kind in ("onnx", "config"):
            entry = (voice.get("files") or {}).get(kind) or {}
            if not str(entry.get("url", "")).startswith("https://"):
                errors.append(f"{vid}: files.{kind}.url must be an https URL")
            if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))):
                errors.append(f"{vid}: files.{kind}.sha256 must be a sha256 hex digest")
        if vid in seen:
            errors.append(f"{vid}: listed twice")
        seen.add(vid)
    if sum(1 for v in voices if v.get("default")) != 1:
        errors.append("voices: exactly one voice must be the default")
    rejected = {r.get("voiceId") for r in data.get("rejected") or []}
    for vid in sorted(seen & rejected):
        errors.append(f"{vid}: both allowed and rejected")
    return errors


def get_voice(voice_id: str) -> dict[str, Any]:
    for voice in load_voices()["voices"]:
        if voice["voiceId"] == voice_id:
            return voice
    raise VoiceNotAllowed(f"{voice_id!r} is not an allowlisted voice; see koveriq/voices.yaml")


def default_voice() -> dict[str, Any]:
    return next(v for v in load_voices()["voices"] if v.get("default"))
