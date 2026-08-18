---
id: TASK-115
title: Manage several quiet-hours calendars from the platform
status: To Do
assignee: []
created_date: '2026-08-18 11:30'
labels:
  - mailbox
  - backend
  - usability
  - frontend
  - security
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
- [ ] #1 Several quiet-hours calendars are configurable **in the app** (profile/settings page), the same way cadence and calendar-awareness already are (TASK-109 AC8) — not only in a local .env
- [ ] #2 The run is treated as busy if ANY configured calendar reports a busy event at that moment
- [ ] #3 One unreachable or unparseable calendar does not prevent the others being checked, and total failure still fails open (the run proceeds) — verified by a test with one good and one broken URL
- [ ] #4 A configured-but-unusable calendar is no longer silent: when a configured URL fails, the run records it where the owner can see it (`MailboxRun.error` or an equivalent surfaced field), rather than only logging
- [ ] #5 The stored URLs are never returned in full by the API: a GET returns them masked (calendar-owner part visible, the `private-<hash>` secret replaced), while a write accepts the full URL — an ICS private URL grants read access to an entire calendar with no authentication, so it is a secret, unlike every other mailbox setting in this serializer
- [ ] #6 Masking is verified against an actual API response, not by reading the serializer — a GET on the profile endpoint contains no `private-<hash>` substring
- [ ] #7 A `GMAIL_CALENDAR_ICS_URL` in .env still works and still wins over the stored value, matching the existing env-overrides-profile idiom (`_effective_salary_floor_eur`, `_effective_do_not_disclose`)
- [ ] #8 The parser tolerates a pasted `[a, b, c]` list literal and surrounding quotes rather than treating it as one URL — that shape is what someone naturally writes, and getting it wrong currently fails open and silent
- [ ] #9 Backend tests cover multi-calendar parsing, the any-calendar-busy rule, the partial-failure case and the masking; no test fetches a real calendar
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
### 2026-08-18 — scope widened to platform configuration, and a secret enters the settings model

The owner wants all three calendars honoured **and** managed in the app rather than in `.env`. That is
consistent with TASK-109 AC8, which already made cadence and calendar-awareness owner-changeable in
the profile page, and `mailbox_do_not_disclose` is already a profile TextField. The pattern exists.

**What is new is that this is the first secret to enter it.** Every mailbox setting currently in
`CandidateProfileSerializer.fields` — cadence, calendar-aware, salary floor, do-not-disclose — is
non-sensitive, so the serializer was never built to hold something that must not be read back. A
private ICS URL grants read access to an entire calendar to anyone holding it, with no authentication.
Today it lives only in a gitignored `.env` on the owner's machine; moving it into the platform puts it
in the production Neon database and, if the existing pattern were copied verbatim, into every profile
`GET` response — browser memory, dev tools, proxies and logs included.

**Owner decision (2026-08-18): masked read, full write.** A GET returns
`…/ical/you%40gmail.com/private-••••••••/basic.ics` — the calendar-owner part stays visible so the
right entry can be recognised and replaced, while the secret hash never leaves the server after being
saved. AC6 requires that to be verified against a real API response rather than by reading the
serializer, because a masking bug is exactly the kind that looks correct in code review.

Blocked on the same thing as before: `mailbox.py` has uncommitted work from a parallel session. The
model, migration, serializer and frontend do not touch that file, so those parts can start first if
this is picked up before it clears.
<!-- SECTION:NOTES:END -->
