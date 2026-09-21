---
id: TASK-242
title: Production-readiness section 1 documents mail variables production ignores
status: Done
assignee:
  - '@pi'
created_date: '2026-09-21 12:22'
updated_date: '2026-09-21 12:23'
labels:
  - docs
  - backend
dependencies: []
priority: medium
type: bug
ordinal: 241000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-09-21 while recovering from the TASK-239 outage.

config/settings.py:540-577 selects a mail configuration by EMAIL_PROVIDER. Production sets EMAIL_PROVIDER=brevo, so it takes the branch at :551 and reads BREVO_EMAIL_HOST, BREVO_EMAIL_PORT, BREVO_EMAIL_USE_TLS, BREVO_EMAIL_HOST_USER, BREVO_EMAIL_HOST_PASSWORD and BREVO_DEFAULT_FROM_EMAIL.

docs/production-readiness.md section 1 lists the generic block instead - EMAIL_BACKEND, EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL - which is the :569 else branch. On this deployment every one of those is ignored. An operator following the checklist to diagnose why password-reset mail is failing would change values that have no effect, which is worse than no documentation.

Measured on the live container app during the outage recovery: it carries DEFAULT_FROM_EMAIL=noreply@localhost and EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend, both dead under the brevo branch. Dead, but not harmless: if EMAIL_PROVIDER were ever unset or changed, that console backend would become live and print password-reset links into the container log instead of sending them.

Section 5 (the recovery runbook, added by TASK-239) already lists the BREVO_* names correctly, so the two halves of the same document currently disagree.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The required-environment section states which EMAIL_PROVIDER branch a deployment is on and lists the variables THAT branch reads, so an operator cannot set a variable the running configuration ignores
- [x] #2 The brevo branch is described as what this production actually runs, with its own variable names, rather than as an aside
- [x] #3 Each claim in the section is traceable to a line in config/settings.py rather than to habit - checked by reading the file, since the section has already drifted once
- [x] #4 The dead EMAIL_BACKEND=console value sitting on the container app is recorded with what it would do if EMAIL_PROVIDER ever changed, so removing it is a decision someone makes deliberately
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Fixed 2026-09-21, and one claim in this task's own description was overstated

Section 1 now leads with EMAIL_PROVIDER: a table of the four branches, what selects each, and the
variables that branch reads, followed by a plain statement that this production runs the Brevo
branch. The generic EMAIL_* block is no longer presented as the required configuration; it is listed
as one branch among four, which is what settings.py:569 makes it.

**Correction to the description above.** It said the stray EMAIL_BACKEND=console on the container app
would become live 'if EMAIL_PROVIDER were ever unset or changed'. That is too strong, and the code
says so: EMAIL_PROVIDER=console is refused outright when DEBUG=False (settings.py:541-542), and
unsetting EMAIL_PROVIDER yields 'auto', which still selects Brevo while the trio is complete
(:532, :551). The console backend can only become live through the generic branch, which requires the
Brevo trio to be incomplete AT THE SAME TIME. Still worth removing, and the doc now states the
narrower condition rather than the scarier one.

## Every citation checked against the file, not from memory

    :527 EMAIL_PROVIDER=os.getenv('EMAIL_PROVIDER', 'auto')          OK
    :532 _brevo_configured=bool(login and key and from)              OK
    :541 if not DEBUG: raise (console refused in production)          OK
    :551 elif EMAIL_PROVIDER == 'brevo' or (auto and configured)      OK
    :560 elif EMAIL_PROVIDER in ('local','local-smtp') or (auto ...)  OK
    :569 else:  (the generic EMAIL_* block)                           OK
    :579-582 raise unless from-address and host are non-empty         OK

AC5's floor -- the document must stop contradicting itself -- checked by extracting the BREVO_* names
from section 1 and section 5 and comparing: every name section 5 uses now appears in section 1.
AC6's floor: git status shows one markdown file changed and the new task file. No code, no config, no
live resource touched.
<!-- SECTION:NOTES:END -->
