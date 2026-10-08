"""Command line entry points:

    python -m telemarketer.cli simulate --contact examples/contact.json
    python -m telemarketer.cli audit
    python -m telemarketer.cli validate --contacts examples/contact.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .call import CallOrchestrator
from .consent import (AuditLedger, CampaignConfig, ConsentError, Contact,
                      ContactStore)
from .llm import resolve_provider

DEFAULT_LEDGER = Path("audit-ledger.jsonl")


def _load_contact(path: str) -> Contact:
    """Load one contact through the consent wall (rejects missing proof)."""
    store = ContactStore.load(path)
    if len(store) == 0:
        raise ConsentError(f"{path} contains no contacts")
    return next(iter(store._contacts.values()))


def _build_campaign(args) -> CampaignConfig:
    return CampaignConfig(agent_name=args.agent_name, client_name=args.client_name,
                          goal=args.goal)


def cmd_simulate(args) -> int:
    try:
        contact = _load_contact(args.contact)
    except ConsentError as e:
        print(f"COMPLIANCE WALL BLOCKED: {e}", file=sys.stderr)
        return 2

    campaign = _build_campaign(args)
    llm, provider_name = resolve_provider(args.provider)
    print(f"provider: {provider_name} | agent: {campaign.agent_name} on behalf of "
          f"{campaign.client_name}\n")

    store = ContactStore.load(args.contact)
    ledger = AuditLedger(args.ledger)
    orch = CallOrchestrator(store, ledger, llm)
    outcome = orch.run(contact, campaign)
    print(f"\n[outcome] {outcome.value}  (ledger: {len(ledger)} entr{'y' if len(ledger)==1 else 'ies'})")
    return 0


def cmd_audit(args) -> int:
    ledger = AuditLedger(args.ledger)
    if not ledger.entries:
        print(f"ledger empty ({args.ledger})")
        return 0
    for e in ledger.entries:
        flag = "OK " if (e.consent_check_passed and e.disclosure_played
                         and e.recording_notice_played) else "BAD"
        print(f"[{flag}] {e.ts}  {e.contact_name:<20} {e.phone:<16} outcome={e.outcome:<12} "
              f"consent={e.consent_proof} ({e.consent_date})  disclosure={'Y' if e.disclosure_played else 'N'}"
              f"  notice={'Y' if e.recording_notice_played else 'N'}  {e.duration_s:.1f}s")
    return 0


def cmd_validate(args) -> int:
    try:
        store = ContactStore.load(args.contacts)
    except ConsentError as e:
        print(f"COMPLIANCE WALL BLOCKED:\n{e}", file=sys.stderr)
        return 2
    print(f"OK: {len(store)} contact(s) passed the consent wall ({args.contacts})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="telemarketer",
                                description="Voice AI for consented outreach. "
                                            "The compliance wall is mandatory.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="run a full simulated consented call (text mode, no keys)")
    s.add_argument("--contact", required=True, help="path to a JSON contact file (consent-verified)")
    s.add_argument("--agent-name", default="Sam")
    s.add_argument("--client-name", default="Acme Widgets")
    s.add_argument("--goal", default="qualify interest and book a follow-up appointment")
    s.add_argument("--provider", choices=["openai", "xai", "openrouter", "mock"], default=None)
    s.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    s.set_defaults(fn=cmd_simulate)

    a = sub.add_parser("audit", help="print the audit ledger")
    a.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    a.set_defaults(fn=cmd_audit)

    v = sub.add_parser("validate", help="validate a contact file against the consent wall")
    v.add_argument("--contacts", required=True)
    v.set_defaults(fn=cmd_validate)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
