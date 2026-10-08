# ARCHITECTURE.md

## Design goals

1. **Compliance is load-bearing.** The consent wall sits in front of every dial path; nothing routes around it.
2. **Human-grade conversation quality.** Short turns, natural backchannels, honest objection handling, knows when to stop. The LLM seam is provider-agnostic so the best available model can be imposed per campaign.
3. **Pluggable everything.** LLM, TTS, STT, and telephony are adapter interfaces. The app compiles and tests with zero API keys.
4. **Latency budget is a contract.** Voice turns target **< 800 ms** end-to-end; every adapter must fit the budget or declare itself simulation-only.

## Module map

```
┌──────────────────────────────────────────────────────────┐
│  cli.py  ── simulate | audit | validate                  │
├──────────────────────────────────────────────────────────┤
│  call.py ── CallOrchestrator                              │
│    consent check → disclosure → STT→LLM→TTS loop          │
│    → outcome classification → ledger write                │
├──────────────┬──────────────┬────────────────────────────┤
│  consent.py  │  llm.py      │  voice.py                  │
│  WALL +      │  Provider    │  TTS/STT adapters          │
│  ledger      │  seam +      │  + latency budget          │
│              │  MockLLM     │                            │
└──────────────┴──────────────┴────────────────────────────┘
```

## The consent wall (`consent.py`)

- `Contact`: frozen dataclass — `name`, `phone`, `consent_proof`, `consent_date`, `source`.
- `ContactStore.load(path)`: parses JSON or JSONL, **rejects any record without `consent_proof`** with a per-row error report. There is intentionally no `force=True`.
- `CampaignConfig`: `agent_name`, `client_name`, `goal`, `disclosure_text`, `recording_notice`. The disclosure fields are validated non-empty at construction — a campaign cannot exist without them. Default disclosure: *"Hi, this is {agent_name}, an AI assistant calling on behalf of {client_name}. This call may be recorded for quality and compliance."*
- `AuditLedger`: in-memory list + JSONL append. One line per call (see COMPLIANCE.md §6).

## Conversation loop (`call.py`)

`CallOrchestrator.run()`:

1. **Consent check** — contact must exist in the store with valid proof, else `ConsentError` before anything else happens.
2. **Disclosure (mandatory)** — `disclosure_text` then `recording_notice` are emitted as the first two agent turns, verbatim. Not skippable.
3. **Loop** — per turn: `STTAdapter.transcribe()` → append to transcript → `LLMProvider.chat()` → `TTSAdapter.speak()`. In **simulate mode** STT is replaced by stdin and TTS by stdout printing, so the entire loop runs with zero keys.
4. **Outcome classification** — rule-based keyword pass over the transcript (`do not call` / `remove me` → `DO_NOT_CALL`; `later` / `busy` / `callback` → `CALLBACK`; `interested` / `set it up` / `yes` → `INTERESTED`; else `COMPLETED`), then a confirmation pass by the LLM when available.
5. **Ledger write** — append audit line; `do_not_call` outcomes propagate to the contact store suppression list.

Stop conditions: caller says goodbye/stop/hang-up keywords, max turns (default 30), or LLM returns the `END_CALL` sentinel.

## LLM seam (`llm.py`)

One interface:

```python
class LLMProvider(Protocol):
    def chat(self, messages: list[dict]) -> str: ...
```

Implementations, all OpenAI-compatible `/chat/completions`:

| Provider | Env var | Base URL | Notes |
|---|---|---|---|
| ChatGPT | `OPENAI_API_KEY` | `https://api.openai.com/v1` | `gpt-4o-mini` default; any `-completions` model |
| Grok | `XAI_API_KEY` | `https://api.xai/v1` | `grok-2-latest` default |
| OpenRouter | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | any `openrouter/model-id` |
| MockLLM | — | — | scripted responses; used by tests and keyless simulate |

`build_sales_system_prompt(campaign, contact)` produces the human-grade salesperson persona: sub-25-word turns, backchannels, no robotic script-reading, honest objection handling (one soft reframe max), mandatory truthfulness about being an AI when asked, and hard stop on any stop/remove-me signal. This prompt is the quality ceiling — treat it as a first-class artifact.

Provider resolution order in CLI: explicit flag → env keys in the order above → MockLLM fallback with a printed warning.

## Voice seam (`voice.py`)

- `TTSAdapter.speak(text) -> AudioResult` and `STTAdapter.transcribe(audio) -> str` protocols.
- `ElevenLabsTTS`: stub with the real request shape (stream endpoint, `xi-api-key`, voice-id header path) — implemented behind the key check in wave 2.
- `LocalTTSFallback`: documented path for zero-cost dev (e.g., `espeak-ng` / OS `say`) — robotic by definition, simulation-only, never presented as human-grade.
- `LatencyBudget`: `turn_ms=800` total → STT ≤ 150 ms, LLM first-token ≤ 400 ms, TTS first-byte ≤ 250 ms. Adapters must declare measured latency; anything over budget is flagged in the ledger.

## Telephony adapter seam (wave 2 — Twilio)

The next wave adds live calling through a `TelephonyAdapter` protocol. The Twilio contract is specified now so wave-2 code lands without redesign:

- **Inbound:** Twilio `POST /webhook/voice` (TwiML) → `<Stream url="wss://.../media">` forwards 8 kHz μ-law audio to the orchestrator; responses return as TwiML `<Play>` via TTS callback.
- **Outbound (consent-verified only):** REST `POST /Calls` with per-call consent record ID in the `status_callback` metadata; orchestrator refuses the dial without a matching `consent_proof` row.
- **Events:** `status_callback` transitions (`initiated/ringing/answered/completed`) map to ledger `call_start`/`call_end`.
- **Recording:** Twilio dual-channel recording + the spoken recording notice logged together.

Wave 2 scope: streaming STT (Deepgram/Assembly) + streaming TTS (ElevenLabs websocket) to hold the <800 ms budget on live audio, plus DNC-sync cron and CRM webhooks.

## Data & config

- No database required at scaffold time; JSONL ledgers and contact files are the persistence layer. Schema versioning is by ISO date in record fields.
- Configuration is env-var first (provider keys), file second (`campaign.yaml` planned for wave 2).
- Secrets never enter the ledger or logs.

## Testing

`python3 -m pytest -q` — no network, no keys:
- consent wall rejects missing/unparseable proof; ledger appends immutably;
- campaign config refuses empty disclosure;
- simulate mode runs end-to-end on MockLLM with scripted user input, classifies outcomes correctly, and writes the ledger.
