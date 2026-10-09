# mission.md

## Mission
Ship a reliable, low-cost voice AI agent for consented outreach and inbound qualification.

## Current priority
Live telephony v1:
1. provider-neutral telephony contract
2. zero-cost local/demo adapter
3. Twilio outbound adapter
4. webhook/status service
5. operator click-to-call CLI
6. live STT/TTS media bridge
7. deployment packaging

## Goals
- Preserve compliance gates as load-bearing architecture.
- Keep telephony, LLM, STT, and TTS providers swappable.
- Make local/demo development work without paid services.
- Keep unit validation offline and deterministic.
- Produce correlated audit evidence for every completed call.

## Non-goals
- Cold AI robocalling.
- Predictive dialing.
- Purchased lead-list dialing without documented consent.
- Any consent/disclosure bypass.
- Autonomous production deployment.
- Auto-merge before the factory proves stable.
