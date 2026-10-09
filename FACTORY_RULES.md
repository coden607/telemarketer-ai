# FACTORY_RULES.md

## Autonomous-session guardrails
- Never push directly to `main`.
- Never merge your own PR.
- Never force-push.
- Never delete branches, tags, data, secrets, or production resources.
- Never deploy to production.
- Never weaken consent, disclosure, recording notice, DNC, or audit enforcement.
- Never add a bypass flag for the consent wall.
- Never commit credentials or real customer data.
- Stop after 2 failed attempts on the same blocker and mark the issue `blocked`.
- Builder and validator must be separate runs with separate context.
- Builder must not see holdout scenarios.
- Validator must not receive builder reasoning.

## State machine
`accepted -> in-progress -> needs-review -> merged`

Alternate states:
- `rejected`
- `blocked`

The issue label is the canonical state.
