---
id: TASK-168
title: Job mail lands in the wrong job class
status: To Do
assignee: []
labels:
  - backend
  - mailbox
  - classification
dependencies:
  - TASK-162
priority: medium
ordinal: 168000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-21 while hand-inspecting all 59 production messages for TASK-162's before-baseline.
Filed separately because it is a DIFFERENT defect with the same consequence.

TASK-162 is about non-job mail reaching a job classification (a spare-parts support ticket becoming a
`rejection`). This is about genuine job mail reaching the WRONG job classification — which carries
the identical one-click risk, because `record_suggestions` turns `rejection` into
`{'status': 'rejected'}` and `interview_invitation` into an interview status plus a feedback-clock
clear, regardless of whether the message was really either of those things.

Measured examples from the 59 (sender | stored class | what it plainly is):

    notifications@smartrecruiters.com | rejection            | "Thanks for applying at IMS Nanofabrication
                                                             | GmbH" -- an application CONFIRMATION
    recruiting.xapo.com               | interview_invitation | "Thank you, Ermis! Your application has been
                                                             | received" -- also a confirmation
    Philipp.Haubner@bmj.gv.at         | rejection            | "AW: Einladung: Vorstellungsgesprach -
                                                             | Elastic Consulting" -- an interview thread
    Kiraly.Boglarka@pannonjob.hu x3   | rejection            | "RE: Questions" -- no evidence either way;
                                                             | 1,149 days old, recruiter agency

The mechanism is visible in `_classify_heuristic`: the checks run in a fixed order —
offer, then rejection, then interview, then application_confirmed — and the FIRST keyword hit wins.
So a confirmation that happens to contain a rejection-shaped phrase is classified as a rejection and
never reaches the `application_confirmed` branch below it. Order-of-evaluation is doing the work that
evidence should be doing.

Note the direction of the errors matters. "Confirmation misread as rejection" proposes marking a live
application dead. That is worse than the reverse, and worse than TASK-162's non-job false positives,
because the message IS about a job the owner cares about, so the suggestion looks entirely plausible
at the moment of clicking.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The three named messages classify correctly when re-run: the two "thanks for applying"/"application has been received" messages as `application_confirmed`, and the "AW: Einladung Vorstellungsgesprach" thread as `interview_invitation` rather than `rejection`
- [ ] #2 An explicit confirmation phrase wins over an incidental rejection phrase, rather than losing to it purely because the rejection check runs first — state the rule chosen and why it is evidence-based rather than order-based
- [ ] #3 Measured over the full set of stored status-changing messages: state how many change class, and hand-inspect a stated sample to say how many of those changes are right. A change that is merely different is not an improvement
- [ ] #4 No regression: every message that is genuinely a rejection still classifies as `rejection`, counted over the same set — this is the criterion TASK-162's first attempt failed, demoting 26 genuine messages
- [ ] #5 Ambiguous messages (the `RE: Questions` class — no application context either way) land in `uncertain` rather than being forced into a status-changing class
- [ ] #6 Existing rows are re-classified through the same dry-run-by-default management command TASK-162 added, not a migration, and the dry-run output is inspected before anything is written
- [ ] #7 Backend suite green, with a test per named example that fails against the current classifier
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Do not fix this by reordering the checks in `_classify_heuristic`. Reordering moves the failure rather
than removing it: putting `application_confirmed` first would make a genuine rejection that politely
thanks the applicant for applying — which is most of them — classify as a confirmation. The rule needs
to weigh which signal is more specific to the message, not which line runs first.

TASK-162's first attempt is the cautionary tale to read before starting: a guard that looked correct
demoted 26 genuine messages to `not_job_related`, and only a production dry-run caught it. Measure the
whole changed set, not a sample of the ones that look right.
<!-- SECTION:NOTES:END -->
