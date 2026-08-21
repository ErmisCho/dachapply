---
id: TASK-166
title: Create a job lead from an unmatched message
status: To Do
assignee: []
labels:
  - backend
  - frontend
  - mailbox
dependencies:
  - TASK-163
priority: medium
ordinal: 166000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split out of TASK-163 AC6 on 2026-08-21, deliberately and with the owner informed, so that the
suggestion-and-park work could ship without waiting on a larger feature.

Measured against production 2026-08-21: of the 321 rows in the unmatched panel, **204 (64%) name no
tracked company at all**, and of TASK-161's 41 high-consequence rows, **30 relate to no tracked job**.
These are rejections, interview invitations and confirmations for applications that were never
entered on the board — sent through ATS hosts (join.com 24, ashbyhq.com 17, msg.join.com 17), job
boards, or employer domains the owner never saved a listing from.

TASK-163 parks those rows behind a count and a reveal, which stops them drowning the panel. But
parking is not an answer to what they are: the owner applied for these jobs. The only honest action
for "a rejection for a job you never tracked" is to create the job it refers to, in the state the
message implies, rather than attaching it to an unrelated tracked job or discarding real history.

This is the one route by which the board could become a record of every application rather than only
of the ones remembered at the time. It is also the point at which the app stops being a tracker the
owner feeds and starts being one that catches what they missed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An unmatched message that names no tracked job offers "create a job from this" as an action, and taking it produces a JobLead attached to that message in one step
- [ ] #2 The created lead is pre-filled from what the message actually contains — at minimum company and title where they are derivable — and every field the message does not support is left empty rather than guessed
- [ ] #3 The created lead's status reflects the message's classification, and its dates come from the MESSAGE's own received date, not today's — the same rule `build_suggestions` already applies for `application_confirmed`, since these messages are frequently months old
- [ ] #4 Creation is never automatic; it is an explicit owner action per message, and re-taking it on the same message does not create a duplicate lead
- [ ] #5 Measured against production data: of the 204 currently-unidentifiable rows, state how many produce a usable company and title, and inspect a stated sample by hand to say how many are right
- [ ] #6 A lead created this way is distinguishable from one the owner entered, so the board can be audited later without guessing at provenance
- [ ] #7 Backend suite green; frontend typecheck and tests green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Do not start this before TASK-163 has shipped and the owner has used the parked view — the 204 is
today's number against today's classifier, and TASK-162 (non-job mail landing in job classifications)
will change what is in that bucket. Building extraction against a population that is about to shift
would mean measuring AC5 twice.
<!-- SECTION:NOTES:END -->
