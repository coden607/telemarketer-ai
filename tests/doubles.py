"""Test doubles for the conversation loop: scripted STT and silent TTS."""

from __future__ import annotations

from telemarketer.voice import AudioResult


class ScriptedSTT:
    """Feeds pre-scripted human lines into the orchestrator, then EOF silence."""

    provider = "scripted-test"

    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)

    def transcribe(self, audio: bytes | None = None) -> AudioResult:
        if self._lines:
            return AudioResult(text=self._lines.pop(0), latency_ms=0, provider=self.provider)
        return AudioResult(text="", latency_ms=0, provider=self.provider)


class SilentTTS:
    provider = "silent-test"

    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> AudioResult:
        self.spoken.append(text)
        return AudioResult(text=text, latency_ms=0, provider=self.provider)
