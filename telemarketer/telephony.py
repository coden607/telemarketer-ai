"""Provider-neutral telephony contract plus zero-cost local adapter.

No outbound call reaches a provider until TelephonyService has re-checked the
contact through ContactStore.require(). Provider adapters receive validated
Contact objects, never arbitrary phone-number strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from uuid import uuid4

from .consent import CampaignConfig, Contact, ContactStore


class CallStatus(str, Enum):
    QUEUED = "queued"
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    BUSY = "busy"
    NO_ANSWER = "no-answer"
    UNKNOWN = "unknown"


_TERMINAL = {
    CallStatus.COMPLETED,
    CallStatus.FAILED,
    CallStatus.CANCELED,
    CallStatus.BUSY,
    CallStatus.NO_ANSWER,
}


def normalize_status(raw: str) -> CallStatus:
    value = (raw or "").strip().lower().replace("_", "-")
    aliases = {
        "in-progress": CallStatus.ANSWERED,
        "answered": CallStatus.ANSWERED,
        "queued": CallStatus.QUEUED,
        "initiated": CallStatus.INITIATED,
        "ringing": CallStatus.RINGING,
        "completed": CallStatus.COMPLETED,
        "failed": CallStatus.FAILED,
        "canceled": CallStatus.CANCELED,
        "cancelled": CallStatus.CANCELED,
        "busy": CallStatus.BUSY,
        "no-answer": CallStatus.NO_ANSWER,
        "noanswer": CallStatus.NO_ANSWER,
    }
    return aliases.get(value, CallStatus.UNKNOWN)


@dataclass(frozen=True)
class CallRef:
    provider: str
    provider_call_id: str
    correlation_id: str
    phone: str
    status: CallStatus

    @property
    def terminal(self) -> bool:
        return self.status in _TERMINAL


class TelephonyAdapter(Protocol):
    provider: str

    def dial(
        self,
        contact: Contact,
        campaign: CampaignConfig,
        *,
        correlation_id: str,
    ) -> CallRef:
        """Create one outbound call for an already validated Contact."""


class LocalTelephonyAdapter:
    """Zero-cost provider for development and tests.

    This adapter performs no network I/O and does not place a real phone call.
    It proves the same provider contract can run without paid services.
    """

    provider = "local"

    def dial(
        self,
        contact: Contact,
        campaign: CampaignConfig,
        *,
        correlation_id: str,
    ) -> CallRef:
        # Contact.from_dict() already guarantees these fields are present.
        # Keep a defensive check so custom Contact construction cannot weaken
        # the provider boundary.
        if not contact.consent_proof.strip():
            raise ValueError("validated consent proof is required before dial")
        return CallRef(
            provider=self.provider,
            provider_call_id=f"local-{uuid4().hex}",
            correlation_id=correlation_id,
            phone=contact.phone,
            status=CallStatus.INITIATED,
        )


class TelephonyService:
    """Compliance boundary in front of every outbound telephony adapter."""

    def __init__(self, store: ContactStore, adapter: TelephonyAdapter) -> None:
        self.store = store
        self.adapter = adapter

    def dial(
        self,
        contact: Contact,
        campaign: CampaignConfig,
        *,
        correlation_id: str | None = None,
    ) -> CallRef:
        # THE WALL: unknown and DNC-suppressed numbers stop here, before the
        # provider adapter is invoked.
        stored = self.store.require(contact.phone)
        cid = correlation_id or uuid4().hex
        return self.adapter.dial(stored, campaign, correlation_id=cid)
