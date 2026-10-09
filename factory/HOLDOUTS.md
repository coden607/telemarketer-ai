# Validator-only holdout scenarios

> Builder sessions must not receive this file.

1. Unknown phone number attempts to dial -> zero provider request is made.
2. DNC-suppressed contact attempts to dial -> zero provider request is made.
3. Missing provider credentials -> fail closed without leaking secret names/values beyond required config keys.
4. Duplicate terminal status callback -> exactly one terminal ledger effect.
5. First spoken content on a live call -> AI disclosure precedes sales content.
6. “Do not call me again” during a live conversation -> call terminates and future dial is blocked.
7. Local/demo provider runs without network access or paid credentials.
8. Provider failure after call creation -> correlated failure state is recorded without fabricating success.
