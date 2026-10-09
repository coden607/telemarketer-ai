# Implementation Plan — Live Telephony v1

## Principle
Ship this as small slices. Builder and validator concerns stay separate. No merge or production deployment is implied by this plan.

## Slice 1 — Provider contract
Create:
- `telemarketer/telephony.py`
- `TelephonyAdapter` protocol
- normalized `CallStatus` / `CallRef` models
- zero-cost `LocalTelephonyAdapter`

Tests:
- local adapter lifecycle
- normalized statuses
- no network required

Done when:
- existing orchestrator can reference telephony types without importing Twilio.

## Slice 2 — Twilio REST dial adapter
Implement:
- Twilio outbound REST call creation with `requests`
- env vars: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `PUBLIC_BASE_URL`
- explicit validated `Contact` input
- status callback URL carrying a correlation ID

Tests:
- unconsented number cannot reach adapter
- request shape mocked
- missing config fails closed
- secrets absent from logs/errors

## Slice 3 — HTTP webhook service
Add a minimal HTTP service for:
- `GET /health`
- `POST /webhook/voice`
- `POST /webhook/status`

Requirements:
- provider signature validation
- idempotent callback handling
- normalized event → audit metadata
- no business logic duplicated from `CallOrchestrator`

Tests:
- invalid signature rejected
- duplicate callback does not duplicate terminal outcome
- inbound response always starts disclosure flow

## Slice 4 — Live media/STT/TTS
Add adapters behind existing seams:
- streaming STT provider
- streaming TTS provider
- provider media bridge

Fallback:
- local/demo audio or text path remains available without paid services.

Validation:
- transcript ordering
- DNC interruption
- hangup handling
- latency measurements recorded as metadata

## Slice 5 — Operator CLI
Add:
`python -m telemarketer.cli call --contact <file> --provider twilio`

Behavior:
- validate contact through existing wall
- display destination + provider + consent proof pointer
- require a deliberate operator action per call
- emit call reference, not secrets

Tests:
- blocked contact returns nonzero
- successful mocked dial returns call ref
- DNC contact cannot redial

## Slice 6 — Deployment packaging
Add only what is required to run the webhook service:
- process entry point
- environment template
- health check
- deployment notes

Do not deploy to production in this slice.

## Validation gate
Run:
```bash
python3 -m pytest -q
```

Then verify:
- existing simulation tests still pass
- all new telephony tests pass
- no network required for unit suite
- no secret values appear in fixtures, logs, README, or ledger
- consent/disclosure/DNC tests remain hard failures if bypassed

## Recommended order
1. Provider contract
2. Twilio dial
3. Webhook/status service
4. Operator CLI
5. Live media/STT/TTS
6. Deployment packaging

## Exit criteria
Ready for a live test when:
- a verified test number can be called manually
- webhooks are reachable over HTTPS
- consent proof is linked to the call
- disclosure is first
- DNC suppression works
- one complete call produces one correlated audit trail

Production remains a separate explicit approval boundary.
