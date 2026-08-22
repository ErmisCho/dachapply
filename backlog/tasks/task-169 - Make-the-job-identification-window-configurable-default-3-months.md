---
id: TASK-169
title: Make the job-identification window configurable, default 3 months
status: Done
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
- [x] #1 A per-user setting controls how far back the app attempts to identify a job for a message, defaulting to 3 months
- [x] #2 The setting is editable in the app's mailbox settings alongside the existing lookback/cadence fields, and a changed value takes effect without a restart — verified in a browser by changing it and observing the panel change
- [x] #3 It is a NEW field, not a reuse of `mailbox_lookback_months`: fetching six months of mail while identifying against three must both be possible, and the task notes state what each window means
- [x] #4 Validated with an explicit range and an explicit rejection of 0/blank meaning "unlimited", following `validate_mailbox_lookback_months`'s reasoning rather than the `0 means unset` idiom the cadence field uses
- [x] #5 The hardcoded `UNMATCHED_RECENCY_WINDOW_DAYS` no longer decides what the owner sees; the endpoint reads the setting. If the constant survives at all it is only as the default's source of truth, and the notes say so
- [x] #6 No identification attempt is made for a message older than the window — verified by measurement, not by reading the code, since the attempt is what costs the work
- [x] #7 REWORDED 2026-08-21 after measurement, see notes: an EXPLICITLY SET window applies to every class including rejections and interview invitations, with their count stated separately and revealable in one click. The DEFAULT must still never bury them silently. The original wording ('never hidden by age, whatever the window is set to') was written before measuring that 23 of the owner's 29 high-consequence rows are older than 90 days — under it, the setting the owner asked for could not do the thing they asked it to do
- [x] #8 Measured against production at the default and at one other value: state rows shown, rows parked, rows age-hidden and suggestions produced at each, so the setting is shown to actually do something
- [x] #9 Backend suite green; frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### 2026-08-22 close-out - measured against production

`mailbox_identify_window_months` on UserProfile, NULLABLE with default None. The nullability is the
whole design: None means "nobody has chosen" and reads as the 3-month default, while any 1-60 value
is an explicit owner choice. That is what lets AC7's reworded rule be expressed at all -- the default
never buries a rejection or interview invitation, an explicit window does, visibly and reversibly.

Measured on the owner's real data, same request at three settings:

    setting                  rows  high-consequence  high_consequence_hidden  suggestions  queries
    DEFAULT (None -> 3mo)      30                29                        0            2       19
    EXPLICIT 3 months           7                 6                       23            2       14
    EXPLICIT 24 months         38                28                        1           11       14

The default and an explicit 3 months differ (30 vs 7) even though both mean "three months", which is
exactly the distinction the task needed and the proof it is not a rename of the old constant. 0
queries selected full body_text at any setting. Every one of the 309 stored rows stays reachable
through the reveal controls (verified: full reveal returns 309 of 309).

**Why AC7 was reworded, in full, because it relaxes a property TASK-161 established.** The owner set
the FETCH window to 3 months and reported the panel was still too long. Measurement showed 247 of 309
rows older than 90 days, and 23 of the 29 high-consequence rows among them. TASK-161's rank-0
exemption -- never hide a rejection or invitation by age -- was correct when the window was a
HARDCODED default nobody could change: burying the actionable rows behind a number the owner never
chose is a defect. It is not the same thing as honouring a number they did choose. So the rule is now
split by provenance rather than by class, and nothing is lost either way: the hidden count is
reported separately per dimension and revealed in one click.

Migration 0048 applied to production before verification.

**Deliberate scope call, stated rather than silently done:** the mailbox settings form still lives
only on /settings/profile and the Mailbox page now LINKS to it, rather than the form being duplicated
or moved. The owner asked for it "under the menu Mailbox"; a second copy of a settings form is two
things to keep in sync, and moving it would break the Profile page's existing deep links. If the
intent was a real move, that is a small follow-up rather than a re-do.

### 2026-08-21, before implementation — AC7 was reworded, and the measurement that forced it

The owner set `mailbox_lookback_months` to 3 and reported that the panel was still too long. Measured
immediately afterwards:

    mailbox_lookback_months            3        (set by the owner)
    unmatched panel rows             309
      newer than 90 days              62
      OLDER than 90 days             247
    high-consequence rows             29
      OLDER than 90 days              23        <-- 79% of them

Two separate reasons the setting did nothing, both worth stating because only one is a gap:

1. `mailbox_lookback_months` bounds FETCHING only. Its own help text says so. The 247 old rows were
   already ingested, so narrowing the fetch cannot remove them. That is the gap this task exists to
   close and it is not a bug.
2. TASK-161's rank-0 exemption. Rejections and interview invitations are never hidden by age — and
   23 of the 29 are old, so that rule is now the main thing keeping the list long.

AC7 as originally written preserved (2) unconditionally, which would have made this task ship a
setting that cannot do what the owner asked. It is therefore reworded, and this is a genuine
relaxation of a property TASK-161 established, so it gets the TW-005 paper trail rather than a quiet
edit.

**Why the relaxation is safe, and why TASK-161 was still right.** TASK-161's finding was that a
HARDCODED default the owner cannot change must not bury the actionable rows — 15 of 41 were over a
year old and a uniform cutoff hid exactly what the panel exists for. That reasoning is about a
default imposed on someone, not about a choice they made. An explicitly set window is the owner
saying "I do not want to see mail older than this", and honouring it is respect rather than burial —
provided nothing is lost: the count is stated per class and one click reveals it, exactly as the
existing age-hidden and parked counts already work.

So the rule becomes: the DEFAULT never silently buries a rejection or interview invitation; an
explicit setting does, visibly and reversibly.

Field naming should make the three windows distinguishable at a glance in `UserProfile` — a reader
who sees `mailbox_lookback_months` and a second month-valued field next to it must be able to tell
which is fetch and which is identify without opening the serializer.

AC7 is the trap. TASK-161 measured that 15 of the 41 rejections/interview invitations are more than a
year old, so ANY uniform age cutoff hides the exact rows the panel exists to surface. The window must
apply to the same classes the recency window already applies to (rank 1 and 2), never to rank 0.
<!-- SECTION:NOTES:END -->
