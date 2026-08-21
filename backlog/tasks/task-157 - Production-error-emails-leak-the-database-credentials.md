---
id: TASK-157
title: Production error emails leak the database credentials
status: Done
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
- [x] #1 A custom `DEFAULT_EXCEPTION_REPORTER_FILTER` masks `DATABASE_URL`, and the masking is driven by an explicit list of extra names rather than by hoping the default regex covers them
- [x] #2 Every other setting whose VALUE is a secret but whose NAME dodges the default regex is enumerated and masked too — audit the settings module rather than fixing only the one that was caught; name in the notes each setting checked and why it is or is not sensitive
- [x] #3 Proven by test: rendering the exception report with a populated `DATABASE_URL` produces no substring of that value anywhere in the output, asserted against the real reporter (not by inspecting the filter's config)
- [x] #4 The request-data half is checked in the same pass: `HTTP_AUTHORIZATION` and `HTTP_COOKIE` were already masked in the observed email, but confirm by test rather than by that one sample
- [x] #5 Verified in production after deploy: trigger one more harmless 500 the same way, and confirm from the delivered email that the connection string is masked and the traceback is still useful
- [x] #6 The exposed Neon credential is rotated (owner action, Neon console) and the new value set on the Container App; recorded here once done
- [x] #7 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-21, AC6 closed. The exposed Neon credential is rotated and every path is verified.

What was done, in order:

  1. Owner reset the `neondb_owner` password in the Neon console (project dachapply-production,
     branch production, AWS Europe Central 1).
  2. The new pooled connection string went into the local .env.
  3. The Container App secret `database-url` was set from that file and revision dachapply--0000098
     was restarted. Note the revision number: the task originally recorded 0000094, but PRs #67 and
     #68 deployed in the meantime, so `az containerapp revision restart --revision dachapply--0000094`
     fails with "deactivated or does not exist". Always look the active revision up rather than
     reusing a number from an earlier note.

Verified, not assumed:

  new credential works    connect as neondb_owner, read 13 rows from jobradar_mailboxrun -- the same
                          count recorded after the TASK-160 cleanup, so no data moved in the rotation
  stored secret is right  151 chars, byte-identical to the .env value, starts postgresql://, uses the
                          -pooler host, carries sslmode
  live site               GET /api/health/ -> 200 {"status":"ok","database":"ok"}
                          GET /            -> 200
                          GET /api/mailbox-health/ -> 200 {"status":"ok"}  (TASK-160 watchdog, which
                          reads the database, so it is a second independent proof of the credential)
  OLD PASSWORD IS DEAD    reconnecting with the leaked password against the same host is refused:
                          "password authentication failed". This is the criterion that actually
                          matters and it is measured, not inferred from the console showing a reset.

Two failure modes worth recording, because both produced a *silently wrong* secret rather than an
error, and the app only reported them as a generic 500:

  - The az commands were run in cmd.exe, not PowerShell. In cmd, single quotes are not quote
    characters, `<` is a redirect operator, and `&`/`?` inside a Neon connection string split the
    command. The first attempt stored the literal placeholder text (18 chars); the second stored the
    literal string `$conn` (5 chars), because cmd does not expand PowerShell variables and Read-Host
    does not exist there.
  - Neither attempt failed loudly. `az containerapp secret set` accepts any string, so the only
    symptom was the site continuing to 500 with "password authentication failed for user
    'neondb_owner'" -- indistinguishable from "the rotation broke the app".

The diagnostic that resolved it, and the one to reuse: never print the secret, print its SHAPE.
Length, does it start with postgresql://, does it contain -pooler, does it contain sslmode, does it
still contain the old password. A length of 18 or 5 identifies the mistake immediately without ever
putting the value on screen. The fix was to read the value out of the .env file and pass it to az
from there, so it never crosses a shell quoting boundary at all.

Remaining hygiene, deliberately NOT claimed by this task: the old password still appears in this
session's transcript and in the delivered error email that started all of this. It is now inert --
Neon rejects it -- which is the whole point of rotating rather than redacting. TASK-69 tracks the
separate git-history exposure.

2026-08-20 close-out. Fixed in PR #60 (merge 29e1ce0), deployed, and PROVEN in production by
raising a second harmless 500 the same way and comparing the two delivered emails side by side:

    setting                            21:28 (rev ...0089)      22:12 (rev ...0090)
    DATABASE_URL                       full connection string   ********************
    EMAIL_HOST_USER                    visible                  ********************
    GMAIL_IMAP_USER                    visible                  ********************
    GMAIL_CALENDAR_ICS_URL             visible                  ********************
    MAILBOX_DO_NOT_DISCLOSE            visible                  ********************
    MAILBOX_SALARY_FLOOR_EUR           visible                  ********************
    DEFAULT_EXCEPTION_REPORTER_FILTER  Django's default         config.error_filters.DachApply...

AC5's second half holds too - the alert stayed useful: the 22:12 email still carries the full
traceback, "Exception Value: Field 'id' expected a number but got 'still-not-a-number'", and
"Raised during: jobradar.views.generate_prompt". AC4 confirmed in both emails: HTTP_AUTHORIZATION,
HTTP_COOKIE and X_CSRFTOKEN were masked before and after.

Worth recording for whoever reads this next: the leak was found by DOING the verification rather
than by reading the code. TASK-88 AC2 sat unchecked for days as "wait for a real 500"; one
deliberate, harmless 500 both closed it and exposed an active credential leak in the same email.

AC6 (rotating the exposed credential) is the owner's, in the Neon console plus the Container App's
DATABASE_URL and the local .env - the owner stated on 2026-08-20 they would rotate immediately.
Left unchecked here until they confirm it is done, rather than assumed.

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
