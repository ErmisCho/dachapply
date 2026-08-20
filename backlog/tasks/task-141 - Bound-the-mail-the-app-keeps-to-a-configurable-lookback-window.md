---
id: TASK-141
title: Bound the mail the app keeps to a configurable lookback window
status: Done
assignee: []
labels:
  - backend
  - frontend
  - mailbox
priority: high
ordinal: 141000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner instruction 2026-08-19: *"Let's put a time range of 6 months for the time we are checking for
emails (that should also be configurable from a menu)."*

TASK-136 widened the fetch from the inbox to all mail and the log went 653 to 940 messages, reaching
back to 2023-06-26. There is no upper bound on that number today: `fetch_new` resumes from
`MAX(internal_date_ms)` with no floor, and `backfill_historical_mail` takes a floor only as a
command-line argument nobody sees. The owner has no control over any of it from the app.

Six months is the owner's number. It needs to be a stored setting with a default of 6, editable from
the settings page like every other mailbox control (`mailbox_check_enabled`, `_cadence_minutes`,
`_window_start/_end`, `_calendar_ics_urls` are all already there and already have UI).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A stored per-profile setting `mailbox_lookback_months` exists, default 6, with a migration — matching how every other mailbox setting on `UserProfile` is already stored
- [x] #2 The setting is editable from the app's settings page, in the same place as the other mailbox controls, not only via the API or the admin — the owner's words were "configurable from a menu"
- [x] #3 A value that would disable the bound is rejected rather than silently accepted: 0 or blank must not mean "unlimited" by accident. State the accepted range and what an out-of-range value does. `mailbox_check_cadence_minutes` already has this exact validation problem solved on the serializer — follow it
- [x] #4 Mail older than the window is not fetched: the Gmail query carries an `after:` derived from the setting, verified by asserting the query string the transport builds, not by reasoning about it
- [x] #5 The resume marker still works with the bound in place: two consecutive runs, the second fetches nothing new (this is TASK-136 AC4 and must not regress — a floor and a resume marker interact, and the interaction is what breaks)
- [x] #6 Changing the setting takes effect on the next run without a restart, verified by test
- [x] #7 Mail already stored that falls outside the window is NOT deleted by this change. Bounding what is fetched and deleting history are different decisions, and the second one is not being asked for here — if anything ages out data it gets its own task and its own argument
- [x] #8 Backend tests cover the default, the boundary, the rejected values and the query; frontend `npx tsc --noEmit` and `npm test` clean; no test contacts a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20 close-out (evidence: backend suite 783 green; browser measurements on the built bundle at localhost:8000; prod-DB reads and app-command runs with the owner's approval; merges #51/#52/#53 live with HTTP 200): All eight ACs are test/code-proven (defaults, validation range, after: query derivation, resume marker, no-restart effect; the setting feeds only fetch_new).

`UserProfile` already carries the pattern for all of this (`models.py:57-98`) including the comment
explaining why `0` is treated as "unset" for the cadence — read it before choosing what `0` means
here, because copying that idiom blindly would make `0` mean "unlimited lookback", which is the exact
thing AC3 forbids.

AC7 is a boundary worth defending. The owner asked to bound *checking*, not to throw away the 940
messages already collected — and TASK-136 fought specifically to recover 138 application
confirmations, some older than six months. Deleting them as a side effect of adding a window would
undo that silently.
<!-- SECTION:NOTES:END -->
