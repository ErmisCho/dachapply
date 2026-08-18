---
id: TASK-115
title: Support several calendars in the quiet-hours check
status: To Do
assignee: []
created_date: '2026-08-18 11:30'
labels:
  - mailbox
  - backend
  - usability
dependencies: []
priority: medium
ordinal: 115000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`GMAIL_CALENDAR_ICS_URL` holds exactly one URL: `settings.py` reads it with a bare `os.getenv`, and
`calendar_busy_now()` passes it straight to `_fetch_ics()`. Anyone with more than one calendar that
matters — work, personal, a shared team calendar — cannot express that.

Found 2026-08-18 the way these things are always found: the owner had several calendars worth
respecting, wrote them as a list, and the value became

    GMAIL_CALENDAR_ICS_URL=[<url>, <url>, <url>

**That fails silently, and the fail-open design is why.** The whole bracketed string is passed as one
URL, `_fetch_ics` raises, `calendar_busy_now` catches it and returns `False` so mail checking is never
blocked by a broken calendar (TASK-109 AC7, deliberately). Correct behaviour in isolation — but it
means a misconfigured calendar produces no error, no warning, and no fired quiet hour. The owner sees
a working mailbox check and reasonably concludes quiet hours are on.

So this is two things: a missing feature, and a configuration mistake that the system cannot report.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `GMAIL_CALENDAR_ICS_URL` accepts several URLs, separated by commas and/or newlines, and a single bare URL keeps working exactly as before
- [ ] #2 The parser tolerates the `[a, b, c]` list-literal form and surrounding quotes, rather than treating it as one URL — that shape is what someone naturally writes, and getting it wrong currently fails open and silent
- [ ] #3 The run is treated as busy if ANY configured calendar reports a busy event at that moment
- [ ] #4 One unreachable or unparseable calendar does not prevent the others from being checked, and total failure still fails open (the run proceeds) — verified by a test with one good and one broken URL
- [ ] #5 A configured-but-unusable value is no longer silent: when every configured URL fails, the run records it where the owner can see it (`MailboxRun.error` or an equivalent surfaced field), rather than only logging
- [ ] #6 Backend tests cover multi-URL parsing, the any-calendar-busy rule, and the partial-failure case; no test fetches a real calendar
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Deliberately deferred on 2026-08-18 rather than done immediately: `mailbox.py` had 154 uncommitted
lines from a parallel session working on TASK-114, and editing a file another session is mid-change in
means either sweeping their work into this commit or leaving loose edits in their tree. None of their
diff touched the calendar functions, so there is no logical conflict — only a commit-hygiene one.
Pick this up once `mailbox.py` is clean.

AC5 is the part that matters most and is easy to drop. AC7 of TASK-109 requires fail-open, and
fail-open plus silence is what let a broken value look like a working one. Failing open and *saying
so* is not a contradiction of that AC; failing open silently is what made this task necessary.

The interim workaround, in use since 2026-08-18: one bare URL, no brackets, no quotes, no commas.
<!-- SECTION:NOTES:END -->
