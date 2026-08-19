---
id: TASK-146
title: Feedback deadline pane with followed-up and reschedule
status: To Do
assignee: []
labels:
  - backend
  - frontend
  - board
dependencies:
  - TASK-145
priority: high
ordinal: 146000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner instruction 2026-08-19: *"make also a pane that has the company - job positions along with
their feedback that today or from tomorrow feedback expires, and when I click to one of those, I am
directed to the one in the job board listing, but I should also be able to specify that I followed up
or/and rearrange feedback."*

### The data, measured today (2026-08-19)

    jobs with a feedback_due_date:  15
      already expired (< today):     7      (3 of them in an actionable status)
      expires today:                 1
      expires from tomorrow:         7

    actionable rows the pane would show:  1 today + 7 upcoming = 8
    actionable rows the literal wording would HIDE: 3 already expired

    2026-07-27  (-23d)  interview  EBCONT (BMJ)              ElasticSearch Consultant
    2026-08-18   (-1d)  interview  DataScience Service GmbH  Data Engineer
    2026-08-18   (-1d)  interview  AI Search Lab             RAG / Search Engineer
    2026-08-19   (+0d)  interview  Takeda Pharmaceutical     Platform Security & Communication
    2026-08-20   (+1d)  interview  Swiss AI Systems          Applied AI Backend Engineer
    2026-08-21   (+2d)  interview  Dynatrace                 Senior Python Backend Engineer

**Assumption stated rather than silently taken: the pane INCLUDES already-expired feedback**, grouped
and marked as overdue above the rest. Read literally, "today or from tomorrow" excludes the three
overdue rows — including two that expired yesterday — which would make a pane about expiring feedback
hide the most urgent thing in it. This matters more than usual right now because TASK-145 demotes
`stale_rank` out of the board's default ordering at the owner's request, so after that change this
pane is the only place overdue work surfaces at all. If the owner wants overdue excluded, that is a
filter toggle, not a rebuild.

### What already exists and must not be rebuilt

- `FollowUp` model — `job`, `follow_up_date`, `reason`, `completed`, ordered `['completed', 'follow_up_date']`. **4 rows exist, all open.**
- `FollowUpViewSet`, a full `ModelViewSet`, plus `GET/POST /jobs/{id}/followups/`. Marking done and changing a date are already API-complete.
- `JobLead.feedback_due_date` — a separate field from `FollowUp.follow_up_date`, and the one the owner's phrase "feedback expires" refers to.
- A `due_followups` dashboard panel id already exists, and the stats endpoint already computes `jobs_needing_follow_up` as `FollowUp.completed=False, follow_up_date <= today`.
- The dashboard panel system with saved ordering (`initPanelOrder`) that `mailbox_review` was added through.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A dashboard pane lists company, job title and the feedback date for every actionable job whose `feedback_due_date` is today or later, soonest first — 8 such rows exist today and are the fixture to check against
- [ ] #2 Already-expired feedback appears in the same pane, visually separated and marked as overdue, above the rest. The 3 measured overdue rows must be visible, and a job overdue by 23 days must not sort as if it were due soonest
- [ ] #3 The overdue group can be turned off by the owner without code, since the literal request excluded it — state where that control lives
- [ ] #4 Clicking a row navigates to that job in the board listing, and the job is actually located there rather than the board merely being opened — a board with filters or a saved sort applied must still land on the right row
- [ ] #5 "I followed up" is recordable from the pane and is recorded as an auditable fact, not just a date change: it uses the existing `FollowUp` model rather than a second mechanism, and the row it writes says what was followed up on
- [ ] #6 The feedback date is reschedulable from the pane, and rescheduling updates `JobLead.feedback_due_date` — the pane must not silently write to `FollowUp.follow_up_date` instead, since those are different fields with different meanings
- [ ] #7 Both actions update the pane without a full reload, and a failed write reports the failure rather than appearing to succeed
- [ ] #8 Non-actionable jobs (`rejected`, `withdrawn`, `skipped`, `archived`) never appear — consistent with TASK-143, and reusing the same named status set from the model rather than a second literal list
- [ ] #9 The pane does not duplicate or contradict the existing `due_followups` panel and the `jobs_needing_follow_up` stat: state the relationship between them, and if this pane supersedes one, say so rather than shipping two panels that disagree
- [ ] #10 The pane obeys TASK-142's budget: it must not add an unbounded query or a request per row, and the board's DOM node count must stay under the 10,000 that task sets
- [ ] #11 Backend tests cover the date-window query including the overdue boundary and the actionable-status filter; `npx tsc --noEmit` and `npm test` clean; the full backend suite passes unchanged
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC5 and AC6 are the pair most likely to be got wrong, because two similar-sounding date fields exist.
`JobLead.feedback_due_date` is "when I expect to hear back"; `FollowUp.follow_up_date` is "when I
plan to chase". "Rearrange feedback" is the first; "I followed up" is a completed instance of the
second. Writing either one into the other loses the distinction and there is no migration back.

AC9 exists because `due_followups` and `jobs_needing_follow_up` already occupy adjacent ground with a
different definition (`FollowUp.completed=False AND follow_up_date <= today` — open follow-ups, not
expiring feedback). Two panels that look the same and count different things is worse than either one
alone. Decide and write it down.

AC4 is not as trivial as it sounds. The board carries persisted filters (`dachapply_filters`) and,
after TASK-145, a saved sort — so a job can legitimately be filtered out of the very board the pane
links to. Landing on a board that does not contain the row is a dead end; either clear what is
hiding it or open the job directly and say so.
<!-- SECTION:NOTES:END -->
