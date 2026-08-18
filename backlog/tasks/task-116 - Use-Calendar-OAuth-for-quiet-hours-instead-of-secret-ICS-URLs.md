---
id: TASK-116
title: Use Calendar OAuth for quiet hours instead of secret ICS URLs
status: To Do
assignee: []
labels:
  - mailbox
  - backend
  - frontend
  - security
  - simplification
dependencies:
  - TASK-115
priority: medium
ordinal: 116000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Quiet-hours calendars are configured today by pasting each calendar's **private "secret address" ICS
URL** into the app. TASK-115 shipped the platform half of that: a per-user field, masked on read,
with a merge that stops a masked value overwriting the real one on save.

All of that machinery exists for one reason — the stored value is a secret. Replace the secret and it
all becomes unnecessary.

`backend/config/settings.py` records the original decision as *"No OAuth, no Calendar API — a plain
HTTPS GET the calendar-quiet-hours check fails open on."* That was correct when written: the mailbox
check had no OAuth at all, it was IMAP app-password only. **TASK-109 changed that on 2026-08-17** —
the owner declined 2-Step Verification, so a Gmail-API OAuth client, a stored refresh token and a
consent flow were built. The premise the ICS design rested on is gone; the design outlived it.

Adding `https://www.googleapis.com/auth/calendar.readonly` to the existing OAuth client gives a
strictly better shape:

- **No secret is stored anywhere.** Calendar IDs are not secrets; the refresh token already exists.
- **`freeBusy.query` is the exact primitive** — one call answers "is the owner busy right now" across
  every selected calendar, instead of fetching and parsing several ICS files.
- **`calendarList.list` means picking calendars by name** in the UI, instead of hunting for secret
  addresses in Google Calendar settings.
- **Revocation is real**: one click in the Google account. Rotating a leaked ICS address means
  regenerating it in Calendar, which is strictly worse.

On the grant: `calendar.readonly` is broader than nothing, but an ICS secret URL *also* confers full
read access to that calendar — to anyone holding it, with no authentication and no audit trail. This
narrows exposure rather than widening it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The OAuth consent requests `calendar.readonly` alongside the existing Gmail scope, and the setup command tells the owner plainly that re-consenting is required because the scope changed
- [ ] #2 The owner selects which calendars count toward quiet hours **by name**, from the calendars the token can see — no URL is ever typed or pasted
- [ ] #3 Busy-ness is determined by a single `freeBusy.query` across the selected calendars, not by fetching and parsing ICS files
- [ ] #4 Fail-open is preserved exactly as TASK-109 AC7 requires: any failure reaching Google — expired token, revoked scope, network, API error — lets the mail run proceed, verified by test
- [ ] #5 A failure is no longer silent: when the calendar check cannot run, the run records it where the owner can see it, rather than only logging (carried over from TASK-115 AC4, which is the reason that task exists)
- [ ] #6 The stored-ICS-URL path is REMOVED, not left alongside: the profile field, the masking, the masked-round-trip merge and the ICS parser all go, and `GMAIL_CALENDAR_ICS_URL` is deleted from `settings.py`. Two configuration paths for one setting is the failure mode this task exists to end
- [ ] #7 No secret is stored in the database by the new path — verified by inspecting what the profile row and the API response actually contain, not by reading the serializer
- [ ] #8 Backend tests cover calendar selection, the any-calendar-busy rule, and every fail-open branch; no test contacts a real Google endpoint
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Filed 2026-08-18 after the owner asked the obvious question — *"can't this happen by just logging in to
my Google Calendar and authorising the app, like Gmail?"* — which it can, and which is better than
what had just been built. Recording that plainly: TASK-115's platform half shipped in PR #43 and is
deployed, and this task deletes most of it. The masking, the merge and the parser were competent
answers to a question that should not have been asked.

The scope constant is a single string (`GMAIL_OAUTH_SCOPE`, `services/mailbox.py:192`) threaded into
`oauth_authorization_url`, so requesting a second scope is a one-line change plus a re-consent. Google
returns a new refresh token only when `prompt=consent` is sent, which the existing URL already does.

AC6 is the one most likely to be quietly skipped, because deleting working code feels like a loss.
It is not: TASK-115 shipped a masked field the owner may have already filled in, and leaving it in
place next to a calendar picker is how someone configures quiet hours in the wrong one of two places
and cannot work out why nothing happens. Delete it, and drop the column in the same migration.

Sequencing note: the reading half of TASK-115 (ACs 2/3/4/9 — the mailbox.py side) should NOT be built
first. It would implement ICS fetching that this task immediately removes. Go straight to OAuth.
<!-- SECTION:NOTES:END -->
