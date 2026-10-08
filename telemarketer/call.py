"""Call orchestrator: consent check -> mandatory disclosure -> conversation
loop (STT -> LLM -> TTS) -> outcome classification -> audit ledger write."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from .consent import (AuditLedger, CampaignConfig, ConsentError, Contact,
                      ContactStore)
from .llm import END_CALL_SENTINEL, LLMProvider, build_sales_system_prompt
from .voice import PrintTTS, StdinSTT


class CallOutcome(str, Enum):
    INTERESTED = "interested"
    CALLBACK = "callback"
    DO_NOT_CALL = "do-not-call"
    COMPLETED = "completed"
    FAILED = "failed"


STOP_KEYWORDS = ("stop", "hang up", "goodbye", "bye", "end call", "that's all", "thats all")
DNC_KEYWORDS = ("do not call", "don't call", "remove me", "take me off", "never call")
CALLBACK_KEYWORDS = ("call me later", "not a good time", "busy right now", "call back",
                     "another time", "next week", "tomorrow")
INTERESTED_KEYWORDS = ("interested", "sounds good", "set it up", "sign me up", "let's do it",
                       "lets do it", "yes, book", "go ahead", "count me in")


@dataclass
class Transcript:
    turns: list[dict[str, str]] = field(default_factory=list)

    def add(self, role: str, text: str) -> None:
        if text.strip():
            self.turns.append({"role": role, "text": text.strip()})

    @property
    def human_text(self) -> str:
        return " ".join(t["text"].lower() for t in self.turns if t["role"] == "human")


def classify_outcome(transcript: Transcript) -> CallOutcome:
    """Rule-based first pass over the human's words. Cheap, deterministic,
    and good enough for the ledger; a confirmation pass can layer LLM on top
    in wave 2."""
    text = transcript.human_text
    if any(k in text for k in DNC_KEYWORDS):
        return CallOutcome.DO_NOT_CALL
    if any(k in text for k in CALLBACK_KEYWORDS):
        return CallOutcome.CALLBACK
    if any(k in text for k in INTERESTED_KEYWORDS):
        return CallOutcome.INTERESTED
    return CallOutcome.COMPLETED


class CallOrchestrator:
    """Runs one consented call. The consent wall is checked before anything
    else; the disclosure is the first thing spoken; the ledger is written
    no matter how the call ends (other than a consent failure)."""

    def __init__(self, store: ContactStore, ledger: AuditLedger,
                 llm: LLMProvider, *, tts=None, stt=None) -> None:
        self.store = store
        self.ledger = ledger
        self.llm = llm
        self.tts = tts or PrintTTS()
        self.stt = stt or StdinSTT()

    # ------------------------------------------------------------------
    def run(self, contact: Contact, campaign: CampaignConfig) -> CallOutcome:
        # 1. THE WALL — before anything else happens.
        stored = self.store.require(contact.phone)
        if not stored.consent_proof:
            raise ConsentError(f"{contact.phone} has no consent proof — hard blocked")

        transcript = Transcript()
        start = time.monotonic()
        self._say(campaign.disclosure_text, transcript)
        self._say(campaign.recording_notice, transcript)

        # 2. Conversation loop
        messages = [
            {"role": "system", "content": build_sales_system_prompt(campaign, stored)},
            {"role": "assistant", "content": campaign.disclosure_text},
        ]
        outcome = CallOutcome.COMPLETED
        try:
            for _ in range(campaign.max_turns):
                human = self._listen(transcript)
                if not human:
                    break
                hl = human.lower()
                if any(k in hl for k in DNC_KEYWORDS):
                    self._say("Understood — I'll take you off our list right away. Sorry for the trouble.",
                              transcript)
                    outcome = CallOutcome.DO_NOT_CALL
                    break
                if any(k in hl for k in STOP_KEYWORDS):
                    self._say("Of course — have a great day!", transcript)
                    break
                messages.append({"role": "user", "content": human})
                reply = self.llm.chat(messages)
                messages.append({"role": "assistant", "content": reply})
                clean = reply.replace(END_CALL_SENTINEL, "").strip()
                if clean:
                    self._say(clean, transcript)
                if END_CALL_SENTINEL in reply:
                    break
            else:
                outcome = CallOutcome.FAILED  # hit max turns
        except (KeyboardInterrupt, EOFError):
            outcome = CallOutcome.COMPLETED
            transcript.add("system", "call ended by operator/hangup")

        # 3. Outcome + ledger — DNC rule wins over keyword pass when both fired
        if outcome != CallOutcome.DO_NOT_CALL:
            outcome = classify_outcome(transcript)
        if outcome == CallOutcome.DO_NOT_CALL:
            self.store.suppress(contact.phone)
        duration = time.monotonic() - start
        self.ledger.append(contact=stored, campaign=campaign, outcome=outcome.value,
                           duration_s=duration,
                           extra={"turns": len(transcript.turns)})
        return outcome

    # ------------------------------------------------------------------
    def _say(self, text: str, transcript: Transcript) -> None:
        transcript.add("agent", text)
        self.tts.speak(text)

    def _listen(self, transcript: Transcript) -> str:
        heard = self.stt.transcribe()
        transcript.add("human", heard.text)
        return heard.text
