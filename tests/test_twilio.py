from __future__ import annotations

import pytest

from telemarketer.consent import CampaignConfig, Contact, ContactStore
from telemarketer.telephony import CallStatus, TelephonyService
from telemarketer.twilio import (
    TelephonyConfigError,
    TwilioConfig,
    TwilioTelephonyAdapter,
)


def _contact() -> Contact:
    return Contact.from_dict(
        {
            "name": "Jordan Ellis",
            "phone": "+15551234567",
            "consent_proof": "form:wf_1",
            "consent_date": "2026-09-01",
            "source": "web_form",
        }
    )


def _campaign() -> CampaignConfig:
    return CampaignConfig(agent_name="Sam", client_name="Acme Widgets")


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.raised = False

    def raise_for_status(self):
        self.raised = True

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload=None):
        self.payload = payload or {"sid": "CA123", "status": "queued"}
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


def _config():
    return TwilioConfig(
        account_sid="AC" + "1" * 32,
        auth_token="secret-token",
        from_number="+15557654321",
        public_base_url="https://example.test",
    )


def test_twilio_adapter_builds_expected_call_request():
    contact = _contact()
    fake = FakeSession()
    service = TelephonyService(
        ContactStore([contact]),
        TwilioTelephonyAdapter(_config(), session=fake),
    )

    ref = service.dial(contact, _campaign(), correlation_id="corr-123")

    assert ref.provider == "twilio"
    assert ref.provider_call_id == "CA123"
    assert ref.status == CallStatus.QUEUED
    assert len(fake.calls) == 1

    url, kwargs = fake.calls[0]
    assert url.endswith("/Accounts/" + _config().account_sid + "/Calls.json")
    assert kwargs["data"]["To"] == contact.phone
    assert kwargs["data"]["From"] == _config().from_number
    assert kwargs["data"]["Url"] == "https://example.test/webhook/voice?correlation_id=corr-123"
    assert kwargs["data"]["StatusCallback"] == "https://example.test/webhook/status?correlation_id=corr-123"
    assert kwargs["auth"] == (_config().account_sid, _config().auth_token)
    assert kwargs["timeout"] == 15


def test_missing_twilio_config_fails_before_network(monkeypatch):
    for key in (
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM_NUMBER",
        "PUBLIC_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(TelephonyConfigError):
        TwilioConfig.from_env()


def test_public_base_url_must_be_https(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC" + "1" * 32)
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15557654321")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://example.test")

    with pytest.raises(TelephonyConfigError):
        TwilioConfig.from_env()


def test_call_response_requires_sid():
    adapter = TwilioTelephonyAdapter(_config(), session=FakeSession({"status": "queued"}))

    with pytest.raises(RuntimeError):
        adapter.dial(_contact(), _campaign(), correlation_id="corr-1")
