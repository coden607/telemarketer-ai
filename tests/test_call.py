"""End-to-end simulated calls on MockLLM — no API keys, no network."""

from __future__ import annotations

import json

import pytest

from telemarketer.call import CallOrchestrator, CallOutcome, classify_outcome, Transcript
from telemarketer.consent import (AuditLedger, CampaignConfig, ConsentError,
                                  Contact, ContactStore)
from telemarketer.llm import END_CALL_SENTINEL, MockLLM
from tests.doubles import ScriptedSTT, SilentTTS


def _contact(**over):
    row = {"name": "Jordan Ellis", "phone": "+15551234567",
           "consent_proof": "form:wf_1", "consent_date": "2026-09-01",
           "source": "web_form"}
    row.update(over)
    return Contact.from_dict(row)


def _campaign():
    return CampaignConfig(agent_name="Sam", client_name="Acme Widgets")


def _orch(store, ledger, llm, lines):
    return CallOrchestrator(store, ledger, llm,
                            tts=SilentTTS(), stt=ScriptedSTT(lines))


# ---------------------------------------------------------------------------
# Full simulated calls
# ---------------------------------------------------------------------------

def test_simulate_interested_end_to_end(tmp_path):
    store = ContactStore([_contact()])
    ledger = AuditLedger(tmp_path / "l.jsonl")
    llm = MockLLM([
        "Hi Jordan — quick one: got two minutes?",
        "We help teams cut follow-up time in half. Worth a look?",
        f"Great — I'll send Tuesday 10am. {END_CALL_SENTINEL}",
    ])
    orch = _orch(store, ledger, llm, ["sure, go ahead", "yeah, that sounds good, set it up"])
    outcome = orch.run(_contact(), _campaign())
    assert outcome == CallOutcome.INTERESTED
    assert len(ledger) == 1
    e = ledger.entries[0]
    assert e.disclosure_played and e.recording_notice_played and e.consent_check_passed


def test_disclosure_is_first_thing_spoken(tmp_path):
    store = ContactStore([_contact()])
    ledger = AuditLedger(tmp_path / "l.jsonl")
    tts = SilentTTS()
    llm = MockLLM([f"Bye! {END_CALL_SENTINEL}"])
    orch = CallOrchestrator(store, ledger, llm, tts=tts, stt=ScriptedSTT(["bye"]))
    orch.run(_contact(), _campaign())
    assert "AI assistant" in tts.spoken[0]
    assert "recorded" in tts.spoken[1].lower()


def test_do_not_call_blocks_and_suppresses(tmp_path):
    store = ContactStore([_contact()])
    ledger = AuditLedger(tmp_path / "l.jsonl")
    llm = MockLLM(default="Okay.")
    orch = _orch(store, ledger, llm, ["please do not call me again"])
    outcome = orch.run(_contact(), _campaign())
    assert outcome == CallOutcome.DO_NOT_CALL
    assert "+15551234567" in store.do_not_call
    # and now the wall blocks redial
    with pytest.raises(ConsentError):
        store.require("+15551234567")


def test_callback_outcome(tmp_path):
    store = ContactStore([_contact()])
    ledger = AuditLedger(tmp_path / "l.jsonl")
    llm = MockLLM([f"Sure — I'll call Thursday. {END_CALL_SENTINEL}"])
    orch = _orch(store, ledger, llm, ["not a good time, call me later"])
    assert orch.run(_contact(), _campaign()) == CallOutcome.CALLBACK


def test_unconsented_contact_hard_blocked(tmp_path):
    # the store itself is the wall: a contact without proof can't even be built,
    # and an unknown number can't be dialed
    store = ContactStore()
    ledger = AuditLedger(tmp_path / "l.jsonl")
    llm = MockLLM(default="Hello?")
    orch = _orch(store, ledger, llm, ["hello"])
    with pytest.raises(ConsentError):
        orch.run(_contact(), _campaign())
    assert len(ledger) == 0  # nothing logged: nothing happened


def test_end_call_sentinel_ends_loop(tmp_path):
    store = ContactStore([_contact()])
    ledger = AuditLedger(tmp_path / "l.jsonl")
    llm = MockLLM([f"Perfect, we're set. {END_CALL_SENTINEL}"])
    orch = _orch(store, ledger, llm, ["yes go ahead"])
    outcome = orch.run(_contact(), _campaign())
    assert outcome in (CallOutcome.INTERESTED, CallOutcome.COMPLETED)
    assert len(llm.calls) == 1  # loop stopped at the sentinel


# ---------------------------------------------------------------------------
# Outcome classifier unit checks
# ---------------------------------------------------------------------------

def _transcript_with(human_lines):
    t = Transcript()
    for line in human_lines:
        t.add("human", line)
    return t


def test_classifier_rules():
    assert classify_outcome(_transcript_with(["remove me from your list"])) == CallOutcome.DO_NOT_CALL
    assert classify_outcome(_transcript_with(["busy, call me later"])) == CallOutcome.CALLBACK
    assert classify_outcome(_transcript_with(["sounds good, sign me up"])) == CallOutcome.INTERESTED
    assert classify_outcome(_transcript_with(["okay", "hmm"])) == CallOutcome.COMPLETED
