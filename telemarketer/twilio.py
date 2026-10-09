"""Twilio outbound telephony adapter.

This module only creates calls. Incoming webhook handling and signature
validation land in the next slice. No request is sent until TelephonyService
has already passed the contact through ContactStore.require().
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from .consent import CampaignConfig, Contact
from .telephony import CallRef, CallStatus, normalize_status


class TelephonyConfigError(RuntimeError):
    """Raised when live telephony is not configured safely."""


@dataclass(frozen=True)
class TwilioConfig:
    account_sid: str
    auth_token: str
    from_number: str
    public_base_url: str

    @classmethod
    def from_env(cls) -> "TwilioConfig":
        values = {
            "account_sid": os.environ.get("TWILIO_ACCOUNT_SID", "").strip(),
            "auth_token": os.environ.get("TWILIO_AUTH_TOKEN", "").strip(),
            "from_number": os.environ.get("TWILIO_FROM_NUMBER", "").strip(),
            "public_base_url": os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            env_names = {
                "account_sid": "TWILIO_ACCOUNT_SID",
                "auth_token": "TWILIO_AUTH_TOKEN",
                "from_number": "TWILIO_FROM_NUMBER",
                "public_base_url": "PUBLIC_BASE_URL",
            }
            raise TelephonyConfigError(
                "missing required Twilio configuration: "
                + ", ".join(env_names[name] for name in missing)
            )
        if not values["public_base_url"].startswith("https://"):
            raise TelephonyConfigError("PUBLIC_BASE_URL must use https:// for live Twilio webhooks")
        return cls(**values)


class TwilioTelephonyAdapter:
    provider = "twilio"

    def __init__(self, config: TwilioConfig | None = None, *, session: Any = None) -> None:
        self.config = config or TwilioConfig.from_env()
        self.session = session or requests

    def dial(
        self,
        contact: Contact,
        campaign: CampaignConfig,
        *,
        correlation_id: str,
    ) -> CallRef:
        if not contact.consent_proof.strip():
            raise ValueError("validated consent proof is required before dial")

        endpoint = (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.config.account_sid}/Calls.json"
        )
        voice_url = f"{self.config.public_base_url}/webhook/voice?correlation_id={correlation_id}"
        status_url = f"{self.config.public_base_url}/webhook/status?correlation_id={correlation_id}"

        response = self.session.post(
            endpoint,
            data={
                "To": contact.phone,
                "From": self.config.from_number,
                "Url": voice_url,
                "Method": "POST",
                "StatusCallback": status_url,
                "StatusCallbackMethod": "POST",
                "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
            },
            auth=(self.config.account_sid, self.config.auth_token),
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()

        sid = str(payload.get("sid", "")).strip()
        if not sid:
            raise RuntimeError("Twilio call creation response did not include a call SID")

        status = normalize_status(str(payload.get("status", "initiated")))
        if status == CallStatus.UNKNOWN:
            status = CallStatus.INITIATED

        return CallRef(
            provider=self.provider,
            provider_call_id=sid,
            correlation_id=correlation_id,
            phone=contact.phone,
            status=status,
        )
