# GLOBAL_RULES.md

## Repository rules
- Never guess paths; inspect the repository first.
- Preserve the consent wall, mandatory AI disclosure, recording notice, DNC suppression, and append-only audit ledger.
- No outbound dial path may accept an unvalidated bare phone number.
- Keep provider-specific code behind adapters.
- Secrets must come from environment variables and must never enter logs, fixtures, commits, or audit records.
- Unit tests must run without network access.
- Keep changes small and ticket-shaped.
- Run validation before proposing completion.

## Validation
Primary gate:
```bash
python3 -m pytest -q
```

Any live-provider feature must also have mocked request/response tests.
