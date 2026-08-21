---
id: TASK-169
title: Make the job-identification window configurable, default 3 months
status: To Do
assignee: []
labels:
  - backend
  - frontend
  - mailbox
  - settings
dependencies:
  - TASK-161
  - TASK-163
priority: high
ordinal: 169000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner instruction, 2026-08-21: *"the attempt to identify job listings out of mails should have a
timeframe that can be set, with the default 3 months."*

There are three different time windows in this system and only two of them exist today. Naming all
three matters, because the obvious move — reusing `mailbox_lookback_months` — would be wrong:

    FETCH      mailbox_lookback_months          UserProfile, default 6, range 1-60, configurable
                                                How far back to READ mail from Gmail. TASK-141.
    DISPLAY    UNMATCHED_RECENCY_WINDOW_DAYS    views.py, hardcoded 90, NOT configurable
                                                How far back to SHOW low-consequence unmatched rows.
                                                TASK-161.
    IDENTIFY   (does not exist)                 <- what this task adds, default 3 months
                                                How far back to ATTEMPT to identify a job for a
                                                message at all.

Today the identification attempt is unbounded: `suggest_job_for_message` runs against every unmatched
row the endpoint returns, including rows over a year old, and the only thing that limits what the
owner sees is the DISPLAY window, which is a hardcoded constant they cannot change.

Measured against production 2026-08-21, the panel holds 321 unmatched rows of which **253 (79%) are
older than 90 days** — historical backfill from `backfill_historical_mail` / `ingest_threads` rather
than live mail. Attempting to identify a job for a two-year-old confirmation is work whose best case
is a suggestion the owner does not want.

Note the default asked for is 3 months, while the DISPLAY constant is already 90 days. They coincide
numerically today, which is exactly why this must be a real setting rather than a rename of the
constant: the owner asked for something they can change, and a constant that happens to equal the
default is not that.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A per-user setting controls how far back the app attempts to identify a job for a message, defaulting to 3 months
- [ ] #2 The setting is editable in the app's mailbox settings alongside the existing lookback/cadence fields, and a changed value takes effect without a restart — verified in a browser by changing it and observing the panel change
- [ ] #3 It is a NEW field, not a reuse of `mailbox_lookback_months`: fetching six months of mail while identifying against three must both be possible, and the task notes state what each window means
- [ ] #4 Validated with an explicit range and an explicit rejection of 0/blank meaning "unlimited", following `validate_mailbox_lookback_months`'s reasoning rather than the `0 means unset` idiom the cadence field uses
- [ ] #5 The hardcoded `UNMATCHED_RECENCY_WINDOW_DAYS` no longer decides what the owner sees; the endpoint reads the setting. If the constant survives at all it is only as the default's source of truth, and the notes say so
- [ ] #6 No identification attempt is made for a message older than the window — verified by measurement, not by reading the code, since the attempt is what costs the work
- [ ] #7 TASK-161's rank-0 exemption still holds: rejections and interview invitations are still never hidden by age, whatever the window is set to. This is the property that made the whole panel usable and it must not regress
- [ ] #8 Measured against production at the default and at one other value: state rows shown, rows parked, rows age-hidden and suggestions produced at each, so the setting is shown to actually do something
- [ ] #9 Backend suite green; frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Field naming should make the three windows distinguishable at a glance in `UserProfile` — a reader
who sees `mailbox_lookback_months` and a second month-valued field next to it must be able to tell
which is fetch and which is identify without opening the serializer.

AC7 is the trap. TASK-161 measured that 15 of the 41 rejections/interview invitations are more than a
year old, so ANY uniform age cutoff hides the exact rows the panel exists to surface. The window must
apply to the same classes the recency window already applies to (rank 1 and 2), never to rank 0.
<!-- SECTION:NOTES:END -->
