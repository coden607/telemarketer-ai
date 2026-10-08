"""The consent wall: the single most important test file in this repo."""

from __future__ import annotations

import json

import pytest

from telemarketer.consent import (AuditLedger, CampaignConfig, ConsentError,
                                  ConsentValidationError, Contact, ContactStore)


def _valid_row(**over):
    row = {"name": "Jane Doe", "phone": "+15550001111",
           "consent_proof": "form:abc123", "consent_date": "2026-09-01",
           "source": "web_form"}
    row.update(over)
    return row


# ---------------------------------------------------------------------------
# Contact validation
# ---------------------------------------------------------------------------

def test_contact_from_dict_happy_path():
    c = Contact.from_dict(_valid_row())
    assert c.consent_proof == "form:abc123"


@pytest.mark.parametrize("field", ["name", "phone", "consent_proof", "consent_date", "source"])
def test_contact_missing_any_field_rejected(field):
    with pytest.raises(ConsentValidationError):
        Contact.from_dict(_valid_row(**{field: ""}))


def test_contact_null_consent_proof_rejected():
    with pytest.raises(ConsentValidationError):
        Contact.from_dict(_valid_row(consent_proof=None))


def test_store_load_rejects_file_with_bad_row(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([_valid_row(), _valid_row(consent_proof="")]))
    with pytest.raises(ConsentValidationError) as e:
        ContactStore.load(bad)
    assert "consent" in str(e.value).lower()


def test_store_load_jsonl_ok(tmp_path):
    good = tmp_path / "good.jsonl"
    good.write_text("\n".join(json.dumps(_valid_row(phone=f"+1555000{i:04d}"))
                              for i in range(3)))
    assert len(ContactStore.load(good)) == 3


def test_store_require_unknown_number_blocked():
    store = ContactStore([Contact.from_dict(_valid_row())])
    with pytest.raises(ConsentError):
        store.require("+15559999999")


def test_store_suppressed_number_blocked():
    store = ContactStore([Contact.from_dict(_valid_row())])
    store.suppress("+15550001111")
    with pytest.raises(ConsentError):
        store.require("+15550001111")


# ---------------------------------------------------------------------------
# Campaign disclosure is mandatory
# ---------------------------------------------------------------------------

def test_campaign_default_disclosure_built():
    c = CampaignConfig(agent_name="Sam", client_name="Acme")
    assert "AI assistant" in c.disclosure_text
    assert "Acme" in c.disclosure_text
    assert c.recording_notice


def test_campaign_explicit_blank_disclosure_rejected():
    # a string of only spaces must not slip through as "provided"
    with pytest.raises(ConsentError):
        CampaignConfig(agent_name="Sam", client_name="Acme", disclosure_text="   ")


# ---------------------------------------------------------------------------
# Audit ledger
# ---------------------------------------------------------------------------

def test_ledger_appends_entry(tmp_path):
    ledger = AuditLedger(tmp_path / "ledger.jsonl")
    contact = Contact.from_dict(_valid_row())
    campaign = CampaignConfig(agent_name="Sam", client_name="Acme")
    ledger.append(contact=contact, campaign=campaign, outcome="interested", duration_s=12.5)
    assert len(ledger) == 1
    e = ledger.entries[0]
    assert e.consent_check_passed and e.disclosure_played and e.recording_notice_played
    assert e.consent_proof == "form:abc123"


def test_ledger_persists_to_jsonl(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AuditLedger(path)
    contact = Contact.from_dict(_valid_row())
    campaign = CampaignConfig(agent_name="Sam", client_name="Acme")
    ledger.append(contact=contact, campaign=campaign, outcome="completed")
    # reload from disk
    ledger2 = AuditLedger(path)
    assert len(ledger2) == 1
    assert ledger2.entries[0].outcome == "completed"
