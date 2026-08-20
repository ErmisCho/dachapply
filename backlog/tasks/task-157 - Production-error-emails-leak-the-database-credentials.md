---
id: TASK-157
title: Production error emails leak the database credentials
status: To Do
assignee: []
labels:
  - security
  - backend
  - ops
dependencies:
  - TASK-88
priority: high
ordinal: 157000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-20 the moment TASK-88 AC2 was finally proven: the alert email works, and its contents
are unsafe.

Django's `AdminEmailHandler` attaches a full settings dump. `SafeExceptionReporterFilter` masks a
setting only when its NAME matches `API|TOKEN|KEY|SECRET|PASS|SIGNATURE`. So the email correctly
masked `SECRET_KEY`, `EMAIL_HOST_PASSWORD`, `GMAIL_OAUTH_CLIENT_SECRET` and even
`DATABASES['default']['PASSWORD']` — and printed **`DATABASE_URL` in full**, because that name
matches none of those patterns. The value is the complete Neon connection string: username,
password, host, database.

Confirmed by reading the actual delivered email for the 2026-08-20 21:28 (Europe/Vienna) alert.

Blast radius for that one message: the credential now exists in the owner's Gmail mailbox, in
Brevo's outbound mail logs and any retention behind them, and in transit across both. It recurs on
**every** production 500 — the more the alerting works, the more often the credential is mailed.
Related but distinct from TASK-69, which is about a leak already in git history; this one is an
ongoing source.

Two things are needed and they are independent: rotating the exposed credential (owner, Neon
console) and stopping the next email from carrying it (code).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A custom `DEFAULT_EXCEPTION_REPORTER_FILTER` masks `DATABASE_URL`, and the masking is driven by an explicit list of extra names rather than by hoping the default regex covers them
- [ ] #2 Every other setting whose VALUE is a secret but whose NAME dodges the default regex is enumerated and masked too — audit the settings module rather than fixing only the one that was caught; name in the notes each setting checked and why it is or is not sensitive
- [ ] #3 Proven by test: rendering the exception report with a populated `DATABASE_URL` produces no substring of that value anywhere in the output, asserted against the real reporter (not by inspecting the filter's config)
- [ ] #4 The request-data half is checked in the same pass: `HTTP_AUTHORIZATION` and `HTTP_COOKIE` were already masked in the observed email, but confirm by test rather than by that one sample
- [ ] #5 Verified in production after deploy: trigger one more harmless 500 the same way, and confirm from the delivered email that the connection string is masked and the traceback is still useful
- [ ] #6 The exposed Neon credential is rotated (owner action, Neon console) and the new value set on the Container App; recorded here once done
- [ ] #7 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The fix is small and lives in `backend/config/`: subclass `SafeExceptionReporterFilter`, extend
`hidden_settings` with a compiled pattern that also covers `DATABASE_URL` (and anything AC2 turns
up), and point `DEFAULT_EXCEPTION_REPORTER_FILTER` at it.

Do not solve this by turning the settings dump off wholesale — the traceback and the settings
context are what made the TASK-88 alert worth having, and AC5 deliberately requires the report to
stay useful after the fix.

Note for whoever does AC6: rotation is not optional just because the mailbox is the owner's own. The
credential travelled through a third-party mail provider, and the standard for a leaked database
password is rotate-then-verify, not judge-the-likelihood.
<!-- SECTION:NOTES:END -->
