---
id: TASK-161
title: Rank unmatched mail by what attaching can actually do
status: Done
assignee: []
labels:
  - frontend
  - backend
  - mailbox
  - ux
dependencies:
  - TASK-117
  - TASK-142
priority: high
ordinal: 161000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner observation, 2026-08-21: "the unmatched mail jobs seem to be just noise. why have them?"

The panel is load-bearing and the observation is still right. Both halves are measured, not argued.

**Why it must not simply be deleted.** `record_suggestions` only runs for a message that already has
a `matched_job` (`maybe_draft_reply()`'s `if matched is not None` gate). An unmatched interview
invitation therefore produces no suggestion, no card, and nothing in EMAIL DECISIONS — attaching it
is the only route by which it can reach the board. Measured against production 2026-08-21:

    rejections + interview invitations sitting unattached:  41

**Why it reads as noise anyway.** The panel shows every unmatched message that is not
`not_job_related`, ordered by `-uid`, with no ranking (views.py `unmatched`). Measured composition of
those 321 rows against what attaching one could actually achieve, given 91 jobs of which 23 are
unapplied and 15 carry a feedback clock:

    recruiter_reply         143   clears a feedback clock -- only 15 of 91 jobs have one
    application_confirmed   131   marks applied (backdated) -- only 23 of 91 jobs are unapplied
    rejection                24   sets the job to rejected
    interview_invitation     17   sets the job to interview
    uncertain                 6   nothing automatic

So 274 of 321 rows sit in classes that, for most target jobs, can produce no state change at all,
and they are interleaved with the 41 that can. Age makes it worse: **253 of 321 (79%) are older than
90 days** — historical backfill from `backfill_historical_mail` / `ingest_threads`, not live mail.
The panel renders 20 at a time in `-uid` order, so the actionable minority is buried.

This task is the presentation half only. The classifier putting non-job mail into job classes is
TASK-162 and is deliberately kept separate — one changes ordering, the other changes what a message
IS, and conflating them would make either impossible to verify.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The unmatched list is ordered by what attaching could accomplish, not by `uid`: rejection and interview_invitation rank above application_confirmed and recruiter_reply, which rank above uncertain; ties inside a rank break by most-recent-first
- [x] #2 The ordering is computed in the database, not by sorting the serialized list in Python or in the browser — verified by reading the SQL/queryset, since the endpoint already had to fix exactly this class of "the rows were already off the wire" defect in TASK-142
- [x] #3 Every one of the 41 currently-unattached rejections and interview invitations appears in the first page the panel renders, without scrolling past a single lower-rank row — measured against production data, stating the number found
- [x] #4 Low-consequence messages (application_confirmed, recruiter_reply, uncertain) older than a configurable recency window are not shown by default, and the count that is being hidden is stated in the UI rather than silently dropped; the owner can reveal them without leaving the page. Rejections and interview invitations are NEVER hidden by age — see the note below for the measurement that forced this wording
- [x] #5 The default window is justified by the data rather than picked round: state the measured age distribution and why the chosen cutoff falls where it does
- [x] #6 The endpoint's existing performance properties are preserved — no full `body_text` off the wire, no N+1 on `draft` — verified by query count and payload size against production, not by reading the code (TASK-142 shipped a fix that looked right and was still 320 queries)
- [x] #7 Attaching still works unchanged from the ranked list, verified by actually attaching one message in a browser and seeing the job's status change
- [x] #8 Backend suite green; frontend typecheck and tests green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### 2026-08-21 close-out - verified against production, not argued from the code

    AC1  ordering        41 high-consequence rows at positions 0-40, first low-consequence at 41.
                         Within rank 0, received_at strictly descending (2026-08-17 -> 2023-06-29).
    AC2  in the database Case/When annotation + order_by('rank', ...) on the queryset; the frontend
                         renders the API order verbatim and never sorts.
    AC3  first page      41 of 41 rendered with NO click; no lower-rank row precedes any of them.
                         "Showing 41 of 97", "Show more (56 remaining)" -- arithmetic correct.
    AC4  recency         default 97 rows + "224 older low-priority messages hidden"; 97+224 = 321 =
                         the full panel. Clicking "Show older mail" -> "Showing 20 of 321", hidden
                         line gone, still on the board page (no navigation).
    AC5  justification   full cumulative age distribution recorded above; 90d chosen where the
                         distribution actually breaks (68 inside / 253 outside).
    AC6  performance     16 queries, 157,867-byte payload, 0 queries selecting full body_text, 1
                         mailboxdraft query (an N+1 would be ~1 per row -- TASK-142 measured 320).
    AC7  attach          verified in a browser end to end on a SYNTHETIC job + message created for
                         the purpose with the owner's approval, then deleted:
                             attach   -> matched_job set, pending status_change {'status':'rejected'}
                             confirm  -> job status applied -> REJECTED, suggestion confirmed
                             cleanup  -> messages 1020 -> 1019, panel back to 321, 0 ZZ-AC7 rows left
    AC8  suites          backend 824 passed; frontend tsc clean, 109 tests passed.

#### Two fixes the coordinator made on top of the implementation

**1. `nulls_last` on the date tiebreak.** The implementing agent flagged, honestly and correctly,
that `order_by('rank', '-received_at', '-uid')` leaves NULL `received_at` sorting NULLS FIRST on
Postgres -- so a dateless row would rank as the NEWEST in its bucket -- while sqlite (the hermetic
test DB) sorts nulls last, making the divergence invisible to a green suite. Measured: 0 of the 321
current rows have a null received_at, so it was latent rather than live. Fixed anyway with
`F('received_at').desc(nulls_last=True)`, the idiom views.py:815 already uses. A defect the test
suite structurally cannot catch is worth one expression.

**2. The panel's own 20-row cap defeated AC3.** Ranking put all 41 actionable rows first, and the
panel then rendered 20 of them -- so 21 still sat behind a "Show more" click, which is the exact
burial this task exists to end. The cap is now a floor: never fewer rows than there are
high-consequence ones (`Math.max(unmatchedShown, unmatchedHighConsequenceCount)`), with "Show more"
unchanged for the remainder. Without this, AC3 would have been SPEC-GAP at grading rather than PASS.

#### Rig lessons, recorded because both cost real time and both LOOKED like product bugs

- **A lazily-rendered `<select>` reads as an empty dropdown.** The attach control renders its 78
  options only `onFocus` (`{optionsOpen && jobs.map(...)}`), so a script that inspects it without
  focusing sees exactly one option. This was briefly mistaken for a broken attach feature, and even
  "confirmed" against production -- where the same lazy rendering produced the same empty read. Two
  agreeing measurements of the same wrong method are not corroboration. Dispatch `focusin` (React
  listens for that, not `focus`) and read the options in a SEPARATE call, because React's re-render
  is async and a same-tick read still shows the old DOM.
- **A `--noreload` runserver kept serving a deleted bundle.** After `npm run build` produced a new
  hash, the page went blank: the running server answered with an index.html referencing the previous
  bundle, which no longer existed. Restarting appeared not to help because the old process survived
  and still held the port, so the new server never bound. Check what is actually listening on the
  port before concluding the code is broken -- the served asset hash is the fastest tell.

### 2026-08-21, before implementation — AC4 was reworded, and the measurement that forced it

AC3 and AC4 as originally filed **contradict each other**, and only measuring the age distribution of
the high-signal rows showed it. The actionable mail is OLD:

    cutoff  30d -> shows  34 of 321 rows, HIDES 38 of the 41 high-signal
    cutoff  90d -> shows  68 of 321 rows, HIDES 29 of the 41
    cutoff 365d -> shows 197 of 321 rows, HIDES 15 of the 41

15 of the 41 rejections/interview invitations are more than a year old. So ANY uniform recency filter
hides the very rows the panel exists to surface — AC4 as written would have broken AC3 outright.

AC4 is therefore reworded to apply the recency window **only to the low-consequence classes**
(application_confirmed, recruiter_reply, uncertain), never to rejection or interview_invitation.
Recording this explicitly because it makes AC4 strictly *weaker* — fewer messages get hidden than the
original wording demanded — and TW-005 requires a paper trail for weakening, not just for tightening.
The intent behind both ACs is preserved: cut the historical bulk, do not bury the actionable.

Full age distribution of the 321 (cumulative), which AC5 asks to be stated:

    <=7d     9 |  <=14d  17 |  <=30d  35 |  <=60d  55 |  <=90d  68
    <=180d 105 | <=365d 198 |  >365d 321

**Why the cutoff lands at 90 days.** 68 rows fall inside 90 days and 253 outside it — that boundary
is where live mail flow ends and the `backfill_historical_mail` / `ingest_threads` import begins, so
it separates "mail that arrived while using the app" from "mail imported in bulk". It is also the
horizon past which the two low-consequence classes stop being decisions: an application_confirmed
older than 90 days on a still-unapplied job is a data-repair chore, not something to action today.

Applied to the low-consequence classes only, a 90-day window hides 224 of the 280 low-signal rows and
none of the 41 high-signal ones, so the panel opens at **97 rows instead of 321** with every
actionable message present and ranked first.

**Sighted while measuring, and left for TASK-162:** the three oldest "rejections" are all
`RE: Questions` from June/July 2023, 1,149 days old. Those are near-certainly misclassified rather
than genuine rejections, which is exactly the false-positive class TASK-162 exists for. They are
counted in the 41 here because this task ranks what the classifier says, and correcting what it says
is deliberately the other task's job.
<!-- SECTION:NOTES:END -->
