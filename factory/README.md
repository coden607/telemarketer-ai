# Software factory

This repository uses a guarded issue-to-PR factory.

## Autonomy
Current target: Level 3 moving toward Level 4 after repeated clean validator runs.

## Order of work
1. Fix PR review comments.
2. Validate PRs marked `needs-review`.
3. Build highest-priority `accepted` issue without an open PR.
4. Triage new issues against `mission.md`.

## Builder context
- GLOBAL_RULES.md
- FACTORY_RULES.md
- mission.md
- issue/spec

## Validator context
- GLOBAL_RULES.md
- mission.md
- PR diff
- factory/HOLDOUTS.md

## Escalation
Two failures on the same blocker -> label `blocked` and stop.
