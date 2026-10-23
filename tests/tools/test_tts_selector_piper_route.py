"""Explicit TTS routes must not drop Piper when a Piper voice is requested.

Piper's ``model`` input is a free-form voice name (``en_GB-cori-high``), not a
closed enum, and Piper has no ``_MODELS`` catalogue. ``filter_explicit_route``
used to treat any ``model`` it could not find in an enum or catalogue as "this
tool cannot serve it", so asking ``tts_selector`` for a specific Piper voice
dropped Piper and failed with "No TTS provider available." even though Piper
was installed. The fix lets a provider declare its open model vocabulary as a
JSON-schema ``pattern``; models outside the pattern are still rejected, so an
explicit route keeps its "never falls back" meaning.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from tools.audio.piper_tts import PiperTTS
from tools.audio.tts_selector import TTSSelector
from tools.base_tool import ToolStatus
from tools.provider_routing import filter_explicit_route


@pytest.mark.parametrize(
    "model",
    [
        "en_GB-cori-high",
        "en_GB-jenny_dioco-medium",
        "en_GB-northern_english_male-medium",
        "en_US-lessac-medium",
        "/opt/voices/en_GB-alan-medium.onnx",
    ],
)
def test_explicit_route_keeps_piper_for_a_piper_voice(model: str) -> None:
    piper = PiperTTS()
    assert filter_explicit_route({"model": model}, [piper]) == [piper]


@pytest.mark.parametrize("model", ["eleven_v3", "gpt-4o-mini-tts", "en_GB-cori"])
def test_explicit_route_still_drops_piper_for_a_foreign_model(model: str) -> None:
    assert filter_explicit_route({"model": model}, [PiperTTS()]) == []


def test_selector_picks_piper_for_a_custom_voice_model(monkeypatch) -> None:
    import lib.scoring

    piper = PiperTTS()
    monkeypatch.setattr(piper, "get_status", lambda: ToolStatus.AVAILABLE)
    monkeypatch.setattr(
        lib.scoring,
        "rank_providers",
        lambda tools, ctx: [
            SimpleNamespace(provider=t.provider, tool_name=t.name) for t in tools
        ],
    )

    tool, _ = TTSSelector()._select_best_tool(
        {"text": "Hello", "model": "en_GB-cori-high"}, [piper], {}
    )

    assert tool is piper


def _capture_piper_command(monkeypatch, tmp_path, inputs: dict) -> list[str]:
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        out = cmd[cmd.index("--output_file") + 1]
        with open(out, "wb") as handle:
            handle.write(b"RIFF")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    PiperTTS()._generate({"text": "Hello", "output_path": str(tmp_path / "a.wav"), **inputs})
    assert len(calls) == 1
    return calls[0]


def test_piper_uses_a_piper_voice_name_passed_as_voice(monkeypatch, tmp_path) -> None:
    cmd = _capture_piper_command(monkeypatch, tmp_path, {"voice": "en_GB-cori-high"})
    assert cmd[cmd.index("--model") + 1] == "en_GB-cori-high"


def test_piper_model_wins_over_voice(monkeypatch, tmp_path) -> None:
    cmd = _capture_piper_command(
        monkeypatch, tmp_path, {"model": "en_GB-alan-medium", "voice": "en_GB-cori-high"}
    )
    assert cmd[cmd.index("--model") + 1] == "en_GB-alan-medium"


def test_piper_ignores_a_voice_that_is_not_a_piper_voice(monkeypatch, tmp_path) -> None:
    cmd = _capture_piper_command(monkeypatch, tmp_path, {"voice": "Rachel"})
    assert cmd[cmd.index("--model") + 1] == "en_US-lessac-medium"


def test_piper_cache_key_distinguishes_voices() -> None:
    """A voice that now selects the model must also key the asset cache."""
    piper = PiperTTS()
    a = piper.cache_key({"text": "Hello", "voice": "en_GB-cori-high"})
    b = piper.cache_key({"text": "Hello", "voice": "en_GB-alan-medium"})
    assert a != b
