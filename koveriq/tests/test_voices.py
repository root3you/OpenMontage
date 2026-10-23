"""koveriq/voices.yaml: only commercially usable en_GB Piper voices."""

from __future__ import annotations

import re

import pytest

from koveriq.voices import VoiceNotAllowed, default_voice, get_voice, load_voices, voices_errors
from tools.audio.piper_tts import PIPER_VOICE_PATTERN

REVISION = re.compile(r"^https://huggingface\.co/rhasspy/piper-voices/resolve/[0-9a-f]{40}/en/en_GB/")


def test_the_file_is_valid() -> None:
    assert voices_errors(load_voices()) == []


def test_every_voice_allows_commercial_use_and_cites_its_licence() -> None:
    voices = load_voices()["voices"]
    assert voices
    for voice in voices:
        assert voice["commercialUse"] is True, voice["voiceId"]
        assert voice["licenceUrl"].startswith("https://"), voice["voiceId"]
        assert voice["dataset"] and voice["attributionText"], voice["voiceId"]


@pytest.mark.parametrize("voice", load_voices()["voices"], ids=lambda v: v["voiceId"])
def test_voice_files_are_pinned_and_hashed(voice: dict) -> None:
    vid = voice["voiceId"]
    assert re.match(PIPER_VOICE_PATTERN, vid)
    assert vid.startswith("en_GB-")
    name, quality = vid.split("-")[1], vid.split("-")[2]
    for key, suffix in (("onnx", ".onnx"), ("config", ".onnx.json")):
        entry = voice["files"][key]
        assert REVISION.match(entry["url"]), entry["url"]
        assert entry["url"].endswith(f"/{name}/{quality}/{vid}{suffix}")
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
        assert re.fullmatch(r"[0-9a-f]{32}", entry["md5"])
        assert entry["bytes"] > 0


def test_rejected_voices_are_not_selectable() -> None:
    data = load_voices()
    allowed = {v["voiceId"] for v in data["voices"]}
    rejected = {v["voiceId"] for v in data["rejected"]}
    assert allowed.isdisjoint(rejected)
    assert all(v["reason"] for v in data["rejected"])
    for vid in rejected:
        with pytest.raises(VoiceNotAllowed):
            get_voice(vid)


def test_known_non_commercial_voices_are_rejected() -> None:
    rejected = {v["voiceId"] for v in load_voices()["rejected"]}
    assert {"en_GB-semaine-medium", "en_GB-northern_english_male-medium", "en_GB-alan-medium"} <= rejected


def test_unknown_voice_is_not_allowed() -> None:
    with pytest.raises(VoiceNotAllowed):
        get_voice("en_US-lessac-medium")


def test_exactly_one_default_voice() -> None:
    defaults = [v for v in load_voices()["voices"] if v.get("default")]
    assert len(defaults) == 1
    assert default_voice()["voiceId"] == defaults[0]["voiceId"]


def test_validation_catches_a_non_commercial_entry() -> None:
    data = load_voices()
    bad = {**data, "voices": [{**data["voices"][0], "commercialUse": False}]}
    assert voices_errors(bad)
    bad = {**data, "voices": [{k: v for k, v in data["voices"][0].items() if k != "licenceUrl"}]}
    assert voices_errors(bad)
