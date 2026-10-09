# PRD — Live Telephony v1

## Goal
Turn `telemarketer-ai` from text simulation into a live phone agent while preserving the existing consent wall, mandatory AI disclosure, recording notice, DNC suppression, and audit ledger.

## Scope
### In scope
- Twilio as the first live telephony provider.
- Provider abstraction so another carrier can be added without changing the call orchestrator.
- Inbound voice webhook.
- Outbound click-to-call for consent-verified contacts only.
- Status callbacks and per-call audit correlation.
- Live STT/TTS adapter seam.
- Local/demo mode that requires no paid telephony.
- Environment-driven configuration.
- Automated tests for all hard compliance gates.

### Out of scope for v1
- Predictive dialing.
- Cold-call list import.
- Bulk autodial campaigns.
- Bypassing disclosure, consent proof, DNC, or recording notice.
- Autonomous production deployment.
- CRM write-back beyond a generic webhook contract.

## Users
- Operator: manually initiates a call to a consent-verified contact.
- Contact: receives or places a call and speaks with the AI assistant.
- Maintainer: configures carrier/STT/TTS/LLM providers and reviews audit records.

## Core flows
### Outbound
1. Operator selects a consent-verified contact.
2. App re-checks `ContactStore.require(phone)`.
3. Telephony adapter creates the call.
4. On answer, AI disclosure and recording notice are spoken first.
5. Conversation runs STT → LLM → TTS.
6. Status and outcome are written to the append-only ledger.
7. DNC language immediately suppresses future calls.

### Inbound
1. Carrier posts to `/webhook/voice`.
2. App returns provider-specific call-control instructions.
3. Media is bridged to the conversation runtime.
4. Disclosure/recording notice is spoken before the substantive conversation.
5. Call result is logged.

### Free/local demo
1. Run the same orchestration using local stdin/stdout or loopback audio.
2. No carrier account is required.
3. Same consent/disclosure/outcome tests must pass.

## Functional requirements
- `TelephonyAdapter` protocol with at least:
  - `dial(...)`
  - `build_inbound_response(...)`
  - status event normalization
- `TwilioTelephonyAdapter` implementation.
- No outbound dial path can accept a bare phone number; it must receive a validated contact or consent record ID.
- Webhook signature validation when provider credentials are configured.
- Idempotent status callback handling.
- Provider call SID/reference stored in ledger metadata.
- Configurable public base URL for webhooks.
- CLI command for one manual consented call.
- Health endpoint suitable for deployment probes.
- Local/demo provider available with zero paid services.

## Non-functional requirements
- Secrets never written to logs or the audit ledger.
- Unit tests run without network access.
- Live-provider code must be isolated behind adapters.
- Graceful failure if a carrier/STT/TTS key is missing.
- Duplicate status callbacks must not create duplicate terminal ledger entries.
- Keep the existing sub-800 ms voice-turn target as an optimization target; correctness and disclosure gates take precedence.

## Acceptance criteria
- A consented test contact can be manually dialed through the carrier adapter.
- An unconsented or DNC-suppressed contact is blocked before any provider API request.
- First spoken content contains the AI disclosure and recording notice.
- Status callbacks map into normalized internal states.
- Call completion writes one correlated audit record.
- Saying “do not call” suppresses the contact.
- Local/demo mode works with no carrier credentials.
- Existing tests remain green and new live-telephony tests cover consent blocking, webhook validation, idempotency, disclosure order, and provider failure handling.

## Provider strategy
Use a narrow provider interface. Twilio is the initial implementation because the repository architecture already specifies its webhook/media model. Keep carrier-specific code out of `call.py` so a second provider can be added later without rewriting conversation logic.

## Release boundary
v1 is complete when live calling works in a test environment with validated consent and audit evidence. Production promotion is a separate approval step.
