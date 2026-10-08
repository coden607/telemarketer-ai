# telemarketer-ai

**A voice AI agent for consented outreach** — sales follow-ups, appointment setting, and inbound qualification — built to sound indistinguishably human in *quality* while being structurally incapable of operating in the *illegal* lane.

> **The compliance wall is not a feature. It is the product's identity.**
> This system dials **only** contacts with documented prior express consent. It refuses to import anything else, requires a spoken AI-disclosure on every call, and writes an audit ledger entry for every single interaction. Unsolicited AI-voice robocalling is **out of scope structurally**, not just discouraged.

---

## What it does today (real, working)

- **Simulated consented calls end-to-end**: `python -m telemarketer.cli simulate --contact examples/contact.json` runs the full pipeline — consent verification → mandatory AI disclosure → conversation loop (STT → LLM → TTS) → outcome classification → audit ledger write — in text mode with zero telephony keys and (by default) a built-in `MockLLM`, so it runs **today** with no API keys at all.
- **Pluggable LLM**: one OpenAI-compatible chat interface drives ChatGPT (`OPENAI_API_KEY`), Grok (`XAI_API_KEY`), or any OpenRouter model (`OPENROUTER_API_KEY`) — or all three, swapped by env var.
- **Consent wall**: contact imports without a `consent_proof` field are hard-rejected before any dial path exists.
- **Audit ledger**: every call appends an immutable entry (consent check, disclosure played, recording notice, outcome) to a JSONL ledger.
- **Tested**: `python3 -m pytest -q` — consent wall, ledger append, mandatory disclosure, and end-to-end simulated call, all with no API keys.

## What it deliberately does NOT do

- Cold-call anyone.
- Place an AI-voiced call without prior express written consent on file.
- Skip, truncate, or make optional the AI disclosure.
- Operate in jurisdictions/configurations where the compliance ledger cannot prove consent + disclosure + recording notice.

See [docs/COMPLIANCE.md](docs/COMPLIANCE.md) for the full guardrail doc — what is legal (inbound, prior-express-consent outbound, manual click-to-call with AI assist), what is not (cold AI robocalls under the FCC's 2024 AI-voice ruling + TCPA), and per-state notes.

## Quickstart

```bash
git clone https://github.com/coden607/telemarketer-ai.git
cd telemarketer-ai
pip install -r requirements.txt   # pytest only; runtime is stdlib + lazy requests

# Run a full simulated consented call with the built-in MockLLM (no keys needed):
python3 -m telemarketer.cli simulate --contact examples/contact.json

# Same, but against a real LLM (any one of these):
export OPENAI_API_KEY=sk-...        # ChatGPT
export XAI_API_KEY=xai-...          # Grok
export OPENROUTER_API_KEY=sk-or-... # any OpenRouter model

# Inspect the audit ledger:
python3 -m telemarketer.cli audit

# Validate a contact file against the consent wall:
python3 -m telemarketer.cli validate --contacts examples/contact.json
```

## Architecture

Full details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). The shape:

```
consent.py ── the WALL: contact schema, import validator, audit ledger
call.py    ── orchestrator: consent check → disclosure → STT→LLM→TTS loop → outcome → ledger
llm.py     ── OpenAI-compatible provider seam (ChatGPT / Grok / OpenRouter) + MockLLM
voice.py   ── pluggable TTS/STT adapters (ElevenLabs stubbed, local fallback noted) + latency budget
cli.py     ── simulate / audit / validate entry points
```

**Wave 2 (next)**: live telephony via the `TelephonyAdapter` seam (Twilio webhook contract already specified in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)), streaming STT/TTS for the <800 ms turn budget, and CRM webhooks.

## License

MIT — see [LICENSE](LICENSE). Compliance obligations are architectural, not optional; removing the consent wall violates the license's intended use.
