---
id: TASK-190
title: Bootcamp and course marketing mail is classified as a job application
status: To Do
assignee: []
labels:
  - backend
  - mailbox
  - classification
dependencies: []
priority: medium
ordinal: 190000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found on 2026-08-25 by the agent implementing TASK-166, which reported it rather than folding an
unrelated fix into its diff, and confirmed by the coordinator against production.

Ironhack is a coding bootcamp. It is not an employer the owner applied to, and its marketing mail is
being read as a hiring process:

```
id 419  Ironhack NoReply <noreply@ironhack.com>
        "Thanks for your interest in Ironhack!"        -> interview_invitation
id 421  Daniel Elias Spagna <hello@calendly.com>
        "Personal Interview with Ironhack ... between" -> interview_invitation  (calendar, TASK-182)
```

Both currently classify as `interview_invitation`, which is a **status-changing** classification. The
consequences are concrete, not theoretical:

- TASK-166's create-a-lead path offers to put "Ironhack" on the board with status `interview`. The
  extraction is correct — the company really is Ironhack — so no amount of extraction work fixes it.
- TASK-179's backfill and the Upcoming-interviews panel will treat a bootcamp admissions call as an
  interview for a job that does not exist.

TASK-169 keeps job-board digests and non-job mail out of status-changing classifications. A bootcamp
selling a course is the same category of thing — a vendor marketing at the owner — and is not
covered.

Note this is **not** a TASK-182 regression: id 421 moved to `interview_invitation` because its
calendar summary genuinely says "Personal Interview with Ironhack", and the coordinator's own
measurement of that change counted it among the five as a correct hit. It is correct that the summary
says interview; it is wrong that the *sender* is a training provider.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Bootcamp, course and training-provider mail does not reach a status-changing classification, with the signal chosen stated and justified against measurement
- [ ] #2 Measured against production before and after: how many of the 1133 messages change classification and to what, named individually — a genuine employer becoming non-job is a FAILURE, not an acceptable cost
- [ ] #3 The two Ironhack messages (419, 421) are checked by name and no longer offer to create an `interview` lead
- [ ] #4 TASK-182's five calendar-named interviews (175, 179, 391, 421, 578) are re-measured; any that change are named with the reason
- [ ] #5 TASK-163's and TASK-169's existing guards still hold, and this rule is added alongside them rather than replacing either
- [ ] #6 The rule cannot be satisfied by a hardcoded sender list of one domain — state how a bootcamp not named Ironhack is caught, or record explicitly that it is a per-sender denylist and why that is enough
- [ ] #7 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The tempting fix — deny `ironhack.com` — passes AC3 and fails the task. The owner receives marketing
from several training providers and job platforms; a list of one is a patch on a symptom.

Read `_guard_status_changing`'s Rule A before adding anything: it already distinguishes job boards and
platform senders from employers, and this is the same shape of problem. Extending that rule is very
likely the right move, and it is measured against production rather than argued.

Do not weaken TASK-182's calendar-summary read to fix 421. The summary is not lying — the meeting
really is called "Personal Interview with Ironhack". The sender's nature is the signal that is
missing, not the meeting's title.
<!-- SECTION:NOTES:END -->
