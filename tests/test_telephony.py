from __future__ import annotations

import pytest

from telemarketer.consent import CampaignConfig, ConsentError, Contact, ContactStore
from telemarketer.telephony import (
    CallRef,
    CallStatus,
    LocalTelephonyAdapter,
    TelephonyService,
    normalize_status,
)


def _contact(phone: str = "+15551234567") -> Contact:
    return Contact.from_dict(
        {
            "name": "Jordan Ellis",
            "phone": phone,
            "consent_proof": "form:wf_1",
            "consent_date": "2026-09-01",
            "source": "web_form",
        }
    )


def _campaign() -> CampaignConfig:
    return CampaignConfig(agent_name="Sam", client_name="Acme Widgets")


def test_local_adapter_dials_without_network_or_credentials():
    contact = _contact()
    service = TelephonyService(ContactStore([contact]), LocalTelephonyAdapter())

    ref = service.dial(contact, _campaign(), correlation_id="corr-1")

    assert ref.provider == "local"
    assert ref.provider_call_id.startswith("local-")
    assert ref.correlation_id == "corr-1"
    assert ref.phone == contact.phone
    assert ref.status == CallStatus.INITIATED
    assert not ref.terminal


class SpyAdapter:
    provider = "spy"

    def __init__(self) -> None:
        self.calls = 0

    def dial(self, contact, campaign, *, correlation_id):
        self.calls += 1
        return CallRef(
            provider=self.provider,
            provider_call_id="spy-1",
            correlation_id=correlation_id,
            phone=contact.phone,
            status=CallStatus.INITIATED,
        )


def test_unknown_contact_blocked_before_provider_request():
    adapter = SpyAdapter()
    service = TelephonyService(ContactStore(), adapter)

    with pytest.raises(ConsentError):
        service.dial(_contact(), _campaign())

    assert adapter.calls == 0


def test_dnc_contact_blocked_before_provider_request():
    contact = _contact()
    store = ContactStore([contact])
    store.suppress(contact.phone)
    adapter = SpyAdapter()
    service = TelephonyService(store, adapter)

    with pytest.raises(ConsentError):
        service.dial(contact, _campaign())

    assert adapter.calls == 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("queued", CallStatus.QUEUED),
        ("ringing", CallStatus.RINGING),
        ("in-progress", CallStatus.ANSWERED),
        ("completed", CallStatus.COMPLETED),
        ("cancelled", CallStatus.CANCELED),
        ("no_answer", CallStatus.NO_ANSWER),
        ("something-new", CallStatus.UNKNOWN),
    ],
)
def test_status_normalization(raw, expected):
    assert normalize_status(raw) == expected
