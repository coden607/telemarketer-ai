# COMPLIANCE.md — The Guardrail Doc

This document is the operating law of this codebase. It is written to be read by engineers, operators, and counsel. Where code and convenience disagree, **this document and the law win**.

## 1. The hard line

**Unsolicited AI-voice outbound dialing is out of scope. Structurally. Permanently.**

The following are established law / binding rules (as of the last review date in §8):

- **FCC Declaratory Ruling (Feb 2024):** AI-generated or AI-cloned voices in robocalls are "artificial" under the TCPA. Using them without the called party's **prior express consent** is **illegal nationwide**, effective immediately. See FCC 24-17.
- **TCPA (47 U.S.C. §227):** restricts calls using an artificial or prerecorded voice to lines without prior express consent, with statutory damages of $500–$1,500 **per call**.
- **State mini-TCPAs** (e.g., **New York**, Florida, Oklahoma, Maryland, and others) layer on stricter consent, disclosure, timing, and registration requirements — and private rights of action.
- **Call-recording laws** (two-party/all-party consent states such as California, Illinois, Florida, Pennsylvania, Washington, and others) require disclosure that the call is being recorded.

This codebase therefore **enforces, in code**:

| Rule | Enforcement |
|---|---|
| No consent proof → no contact | `consent.py` import validator **rejects** any row missing `consent_proof`; there is no code path that bypasses it. |
| AI disclosure on every call | `call.py` refuses to start a call unless the campaign config carries a non-empty `disclosure_text`. The disclosure is spoken first, before any sales content. |
| Recording notice on every call | Same mechanism for `recording_notice`; logged per call. |
| Per-call audit ledger | `AuditLedger` appends `{consent_check, disclosure_played, recording_notice, outcome, timestamp}` per call to JSONL. |
| Truthful AI identity | The system prompt requires the agent to state it is an AI if asked, and the disclosure already states it proactively. |

## 2. What IS in scope (legal operating modes)

1. **Inbound calls.** A customer calls you. AI answers and qualifies/books. No prior consent needed for the *answer* (recording disclosure still required; inbound AI disclosure best practice and required by the disclosure config in this system).
2. **Outbound to prior-express-consent contacts.** The contact gave express consent to be called — web form, signed agreement, prior business relationship where lawfully applicable — and that proof is stored in `consent_proof` + `consent_date` + `source`.
3. **Manual click-to-call with AI assist.** A human operator initiates each dial manually (human in the loop on the *decision to call*), with AI handling the conversation. DNC-list scrubbing and calling-window rules still apply.
4. **Text/simulated mode.** No telephony at all. Unlimited, zero legal surface area beyond data handling.

## 3. What is NOT in scope (do not build, do not ship)

- Cold AI-voice robocalls of any kind.
- Purchased lead lists without documented consent for **AI-voiced** calls (a "lead" is not consent).
- Consent "borrowed" from a third party without a documented chain.
- Any feature that truncates, speeds up, buries, or makes skippable the AI disclosure.
- Auto-dialing / predictive dialing of AI voices. The architecture's dial path requires per-contact consent records.

## 4. Consent proof standard

A valid contact record requires ALL of:

```json
{
  "name": "Jane Doe",
  "phone": "+15551234567",
  "consent_proof": "web-form-id:abc123 | signed-agreement.pdf | crm:note-id",
  "consent_date": "2026-09-01",
  "source": "website_checkout_optin"
}
```

`consent_proof` must be a pointer to retrievable evidence (form ID, document, CRM note), not a bare "yes". The ledger joins each call to this evidence.

## 5. State-by-state notes (mini-TCPA stub)

> ⚠️ **Not legal advice. Counsel must review before any live dialing. This table is a working stub — expand it per state before operating there.**

| State | Extra requirements beyond federal | Status |
|---|---|---|
| New York | Strict consent standard for telemarketing; heightened damages; specific calling-window and ID requirements. | **Stub — counsel review required before any NY dialing.** |
| Florida | Mini-TCPA: no autodialer w/o prior express written consent; strict windows; private right of action. | Stub |
| Oklahoma | Prior express written consent for telemarketing with automated tech; registration requirements. | Stub |
| Maryland | Expanded robocall restrictions incl. AI voices; do-not-call registry rules. | Stub |
| California | Two-party recording consent (apply recording notice + get acknowledgment); CCPA for contact data. | Stub |
| All others | Federal TCPA + FCC AI-voice ruling baseline; honor National DNC Registry for telemarketing. | Stub |

**Universal rules regardless of state:** honor DNC registries and personal opt-outs forever (write `do_not_call` outcomes back to the contact store), respect calling windows (8am–9pm local, stricter where state law says so), transmit accurate caller ID, and keep the ledger for at least the statute-of-limitations period (TCPA: 4 years).

## 6. Audit ledger — what we keep

Every call writes one JSONL line:

```json
{
  "ts": "2026-10-08T19:20:00+08:00",
  "phone": "+15551234567",
  "contact": "Jane Doe",
  "campaign": "q4-appointment-setting",
  "consent_check": {"passed": true, "proof": "web-form-id:abc123", "consent_date": "2026-09-01"},
  "disclosure_played": true,
  "recording_notice": true,
  "outcome": "interested",
  "duration_s": 94
}
```

Append-only. Never edited. Exported for counsel on request.

## 7. Operator runbook (summary)

1. Import contacts → validator rejects anything without `consent_proof`. Fix upstream; never patch the row to force it through.
2. Configure campaign → `disclosure_text` and `recording_notice` are mandatory and spoken verbatim at call start.
3. Run calls (simulated, inbound, or consent-verified outbound).
4. After every batch: `python -m telemarketer.cli audit` → confirm every line shows `disclosure_played: true`, `recording_notice: true`, `consent_check.passed: true`.
5. Any `do_not_call` outcome → suppress that number across all campaigns, permanently.

## 8. Review

- Last reviewed: **2026-10-08** (scaffold).
- Next scheduled review: before wave-2 live telephony ships, and every 90 days after.
- Owner: repo maintainer + counsel. Changes to `consent.py` enforcement or this doc require review.
