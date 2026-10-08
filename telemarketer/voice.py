"""Pluggable voice seam: TTS/STT adapter protocols, ElevenLabs stub, and the
latency budget every live adapter must fit.

Scaffold reality check: only the text/print simulation path is implemented.
ElevenLabs + streaming STT land in wave 2 behind the same interfaces, per
docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


# ---------------------------------------------------------------------------
# Latency budget — the <800 ms turn contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LatencyBudget:
    """End-to-end voice-turn budget. Live adapters must declare measured
    latency against these numbers; anything over budget is flagged in the
    audit ledger and, in strict mode, rejected."""

    turn_ms: int = 800          # total target per conversational turn
    stt_ms: int = 150           # speech -> transcript
    llm_first_token_ms: int = 400
    tts_first_byte_ms: int = 250

    def describe(self) -> str:
        return (f"turn target <{self.turn_ms}ms "
                f"(stt<{self.stt_ms}, llm-ttft<{self.llm_first_token_ms}, "
                f"tts-ttfb<{self.tts_first_byte_ms})")


DEFAULT_LATENCY_BUDGET = LatencyBudget()


# ---------------------------------------------------------------------------
# Adapter protocols
# ---------------------------------------------------------------------------

@dataclass
class AudioResult:
    text: str
    latency_ms: int = 0
    provider: str = "unknown"


class TTSAdapter(Protocol):
    """text -> audio (or, in simulation, printed text)."""
    provider: str
    def speak(self, text: str) -> AudioResult: ...


class STTAdapter(Protocol):
    """audio -> transcript. In simulation this is replaced by stdin."""
    provider: str
    def transcribe(self, audio: bytes | None = None) -> AudioResult: ...


# ---------------------------------------------------------------------------
# Concrete adapters
# ---------------------------------------------------------------------------

class PrintTTS:
    """Simulation TTS: renders agent turns to stdout. Zero keys, zero deps."""
    provider = "print-sim"

    def __init__(self, echo: bool = True) -> None:
        self.echo = echo

    def speak(self, text: str) -> AudioResult:
        if self.echo:
            print(f"[agent] {text}")
        return AudioResult(text=text, latency_ms=0, provider=self.provider)


class StdinSTT:
    """Simulation STT: reads the human's typed replies."""
    provider = "stdin-sim"

    def __init__(self, input_func=input) -> None:
        self._input = input_func

    def transcribe(self, audio: bytes | None = None) -> AudioResult:
        try:
            text = self._input("[you] ")
        except EOFError:
            text = ""
        return AudioResult(text=text.strip(), latency_ms=0, provider=self.provider)


class ElevenLabsTTS:
    """Wave-2 stub. Real request shape is fixed now so wave 2 is plumbing, not
    design: POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream
    with header xi-api-key and body {text, model_id, voice_settings}. Streaming
    first-byte latency target: see LatencyBudget.tts_first_byte_ms."""

    provider = "elevenlabs"

    def __init__(self, voice_id: str = "21m00Tcm4TlvDq8ikWAM",
                 model_id: str = "eleven_turbo_v2_5") -> None:
        self.voice_id = voice_id
        self.model_id = model_id

    def configured(self) -> bool:
        return bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())

    def speak(self, text: str) -> AudioResult:
        if not self.configured():
            raise RuntimeError(
                "ElevenLabsTTS is a wave-2 stub: set ELEVENLABS_API_KEY and implement "
                "the streaming call (see docs/ARCHITECTURE.md) before using live audio."
            )
        raise NotImplementedError("wave 2: wire the streaming endpoint here")


class LocalTTSFallback:
    """Zero-cost dev fallback (e.g. espeak-ng / OS `say`). Robotic by
    definition — simulation-only, never presented as human-grade output."""

    provider = "local-fallback"

    def speak(self, text: str) -> AudioResult:
        raise RuntimeError(
            "LocalTTSFallback is intentionally unimplemented at scaffold: a robotic "
            "voice is not the product. Use PrintTTS for text simulation."
        )
