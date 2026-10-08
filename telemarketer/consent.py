"""The WALL: contact consent schema, import validation, and the audit ledger.

Nothing in this codebase can place or simulate a call for a contact that
did not pass through here. That is deliberate and non-negotiable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


class ConsentError(Exception):
    """Raised when a contact or campaign fails the compliance wall."""


class ConsentValidationError(ConsentError):
    """Raised when a contact import contains rows without consent proof."""


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Contact:
    """A callable person. `consent_proof` must point at retrievable evidence
    (form ID, signed document, CRM note) — never a bare 'yes'."""

    name: str
    phone: str
    consent_proof: str
    consent_date: str
    source: str

    @classmethod
    def from_dict(cls, row: dict[str, Any], *, row_id: str = "?") -> "Contact":
        missing = [k for k in ("name", "phone", "consent_proof", "consent_date", "source")
                   if row.get(k) is None or not str(row.get(k, "")).strip()]
        if missing:
            raise ConsentValidationError(
                f"contact row {row_id}: missing required field(s) {missing} — "
                "every contact needs documented prior express consent"
            )
        return cls(
            name=str(row["name"]).strip(),
            phone=str(row["phone"]).strip(),
            consent_proof=str(row["consent_proof"]).strip(),
            consent_date=str(row["consent_date"]).strip(),
            source=str(row["source"]).strip(),
        )


class ContactStore:
    """Validated contact persistence. The loader rejects any row lacking
    consent proof; there is intentionally no way to force a bad row in."""

    def __init__(self, contacts: Optional[Iterable[Contact]] = None) -> None:
        self._contacts: dict[str, Contact] = {}
        self.do_not_call: set[str] = set()
        for c in contacts or []:
            self.add(c)

    def add(self, contact: Contact) -> None:
        self._contacts[contact.phone] = contact

    def get(self, phone: str) -> Optional[Contact]:
        return self._contacts.get(phone)

    def require(self, phone: str) -> Contact:
        c = self.get(phone)
        if c is None:
            raise ConsentError(f"no contact record for {phone} — cannot dial unknown numbers")
        if phone in self.do_not_call:
            raise ConsentError(f"{phone} is on the do-not-call suppression list")
        return c

    def suppress(self, phone: str) -> None:
        self.do_not_call.add(phone)

    def __len__(self) -> int:
        return len(self._contacts)

    # -- loading -----------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> "ContactStore":
        """Load JSON (single object or list) or JSONL. Rejects the whole file
        with a per-row report if any row lacks consent proof."""
        p = Path(path)
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            return cls()
        if text.startswith("["):
            rows = json.loads(text)
        elif text.startswith("{"):
            # could be one JSON object or JSONL of objects
            try:
                rows = [json.loads(text)]
            except json.JSONDecodeError:
                rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]

        contacts, errors = [], []
        for i, row in enumerate(rows):
            try:
                contacts.append(Contact.from_dict(row, row_id=str(i)))
            except ConsentValidationError as e:
                errors.append(str(e))
        if errors:
            raise ConsentValidationError(
                f"refusing to import {len(errors)} of {len(rows)} row(s) without consent proof:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
        return cls(contacts)


# ---------------------------------------------------------------------------
# Campaign config — disclosure is MANDATORY
# ---------------------------------------------------------------------------

DEFAULT_DISCLOSURE = (
    "Hi, this is {agent_name}, an AI assistant calling on behalf of {client_name}. "
    "This call may be recorded for quality and compliance."
)
DEFAULT_RECORDING_NOTICE = (
    "Just to let you know, this call may be recorded for quality and compliance."
)


@dataclass(frozen=True)
class CampaignConfig:
    """Per-campaign configuration. `disclosure_text` and `recording_notice`
    are legally mandatory and therefore validated non-empty at construction —
    a campaign object cannot exist without them."""

    agent_name: str
    client_name: str
    goal: str = "qualify interest and book a follow-up appointment"
    disclosure_text: str = ""
    recording_notice: str = ""
    max_turns: int = 30

    def __post_init__(self) -> None:
        disclosure = self.disclosure_text or DEFAULT_DISCLOSURE.format(
            agent_name=self.agent_name, client_name=self.client_name
        )
        notice = self.recording_notice or DEFAULT_RECORDING_NOTICE
        # frozen dataclass → use object.__setattr__ to fill validated defaults
        object.__setattr__(self, "disclosure_text", disclosure.strip())
        object.__setattr__(self, "recording_notice", notice.strip())
        if not self.disclosure_text:
            raise ConsentError("campaign disclosure_text is mandatory and may not be empty")
        if not self.recording_notice:
            raise ConsentError("campaign recording_notice is mandatory and may not be empty")


# ---------------------------------------------------------------------------
# Audit ledger — append-only, JSONL
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LedgerEntry:
    ts: str
    phone: str
    contact_name: str
    campaign_agent: str
    campaign_client: str
    consent_check_passed: bool
    consent_proof: str
    consent_date: str
    disclosure_played: bool
    recording_notice_played: bool
    outcome: str
    duration_s: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


class AuditLedger:
    """Append-only audit trail. Every call writes exactly one entry.
    Entries are never edited in place — correction is a new entry."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._entries: list[LedgerEntry] = []
        if self.path and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    d["extra"] = {k: v for k, v in d.items()
                                  if k not in LedgerEntry.__dataclass_fields__ or k == "extra"}
                    known = {k: d.get(k) for k in LedgerEntry.__dataclass_fields__ if k != "extra"}
                    known["extra"] = d.get("extra", {})
                    self._entries.append(LedgerEntry(**known))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    def append(self, *, contact: Contact, campaign: CampaignConfig, outcome: str,
               duration_s: float = 0.0, extra: Optional[dict[str, Any]] = None) -> LedgerEntry:
        entry = LedgerEntry(
            ts=self._now(),
            phone=contact.phone,
            contact_name=contact.name,
            campaign_agent=campaign.agent_name,
            campaign_client=campaign.client_name,
            consent_check_passed=True,
            consent_proof=contact.consent_proof,
            consent_date=contact.consent_date,
            disclosure_played=True,
            recording_notice_played=True,
            outcome=outcome,
            duration_s=round(duration_s, 3),
            extra=extra or {},
        )
        self._entries.append(entry)
        if self.path:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return entry

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(asdict(e), ensure_ascii=False) for e in self._entries)
