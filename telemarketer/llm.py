"""Pluggable LLM seam.

One OpenAI-compatible chat interface drives ChatGPT (OPENAI_API_KEY),
Grok (XAI_API_KEY), or any OpenRouter model (OPENROUTER_API_KEY).
MockLLM runs the full pipeline with zero keys — tests and demos use it.
"""

from __future__ import annotations

import os
from typing import Protocol, Sequence

from .consent import CampaignConfig, Contact

END_CALL_SENTINEL = "<<END_CALL>>"

# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------

class LLMProvider(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str: ...


class OpenAICompatProvider:
    """Minimal /chat/completions client. `requests` is imported lazily so the
    package (and keyless simulate mode) works without it installed."""

    def __init__(self, api_key: str, model: str, base_url: str,
                 *, timeout_s: float = 30.0, extra_headers: dict | None = None) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.extra_headers = extra_headers or {}

    def chat(self, messages: list[dict[str, str]]) -> str:
        import requests  # lazy: only needed for live providers
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json", **self.extra_headers},
            json={"model": self.model, "messages": messages, "temperature": 0.4},
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


class MockLLM:
    """Scripted provider for tests and keyless runs. Pops canned responses in
    order; repeats the last one (or `default`) when the queue is dry."""

    def __init__(self, responses: Sequence[str] = (), default: str = "Okay!") -> None:
        self._responses = list(responses)
        self._default = default
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if self._responses:
            return self._responses.pop(0)
        return self._default


# ---------------------------------------------------------------------------
# Provider resolution
# ---------------------------------------------------------------------------

PROVIDERS = {
    "openai":     {"env": "OPENAI_API_KEY",     "base": "https://api.openai.com/v1",
                   "model": "gpt-4o-mini"},
    "xai":        {"env": "XAI_API_KEY",        "base": "https://api.xai/v1",
                   "model": "grok-2-latest"},
    "openrouter": {"env": "OPENROUTER_API_KEY", "base": "https://openrouter.ai/api/v1",
                   "model": "openrouter/auto"},
}


def resolve_provider(prefer: str | None = None) -> tuple[LLMProvider, str]:
    """Pick a live provider from env keys (explicit `prefer` wins, else the
    order above). Falls back to MockLLM when no key is set."""
    if prefer == "mock":
        return MockLLM(default="Got it — real quick, what is your biggest headache with follow-ups right now?"), "mock"
    order = [prefer] if prefer else []
    order += [n for n in PROVIDERS if n not in order]
    for name in order:
        spec = PROVIDERS[name]
        key = os.environ.get(spec["env"], "").strip()
        if key:
            headers = {"HTTP-Referer": "https://github.com/coden607/telemarketer-ai",
                       "X-Title": "telemarketer-ai"} if name == "openrouter" else None
            return OpenAICompatProvider(key, spec["model"], spec["base"],
                                        extra_headers=headers or {}), name
    return MockLLM(default="Got it — real quick, what is your biggest headache with follow-ups right now?"), "mock"


# ---------------------------------------------------------------------------
# The quality ceiling: human-grade voice salesperson system prompt
# ---------------------------------------------------------------------------

def build_sales_system_prompt(campaign: CampaignConfig, contact: Contact) -> str:
    """Persona prompt for a conversational voice agent that does not read
    scripts robotically. This prompt is a first-class artifact — iterate on it
    like product copy, not like plumbing."""
    return f"""You are {campaign.agent_name}, an AI phone assistant calling on behalf of {campaign.client_name}.
You are talking to {contact.name}. This is a real phone conversation, not a chat window.

Conversation rules — these define whether you sound human:
1. ONE short turn at a time. Under 25 words. Sentence fragments are fine. Never monologue.
2. Use natural backchannels when the other person speaks: "mm-hm", "right", "got it", "sure".
3. Do NOT read a script. Respond to exactly what they said, in their order, in their words when possible.
4. Mirror their pace and tone. If they're brisk, be brisk. If they're chatty, warm up.
5. Handle objections honestly — price, timing, "not interested". Give ONE soft reframe at most,
   then respect their answer. Arguing is how robots sound.
6. If asked whether you are an AI or a human, answer truthfully: you are an AI assistant.
7. If they say stop, ask to be removed, or seem upset: apologize briefly, confirm removal, and end.
8. Goal: {campaign.goal}. Confirm any details (time, callback number, email) back to them before ending.
9. When the conversation is resolved, output the token {END_CALL_SENTINEL} as your entire final turn.

You already opened the call by introducing yourself as an AI assistant; never hide that."""
