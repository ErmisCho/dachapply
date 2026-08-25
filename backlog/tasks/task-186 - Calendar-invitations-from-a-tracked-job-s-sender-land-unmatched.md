---
id: TASK-186
title: Calendar invitations from a tracked job's sender land unmatched
status: Done
assignee: []
labels:
  - backend
  - mailbox
  - matching
dependencies:
  - TASK-182
priority: high
ordinal: 186000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the coordinator on 2026-08-24 while measuring TASK-182, and it cost a real miss: the owner
had an on-site interview **two days away** that the application could not see.

Measured against production:

```
job 535  Formunauts  Senior Back End Developer Python  status=interview  interview_at=None

msg 638  job=535  interview_invitation  recv=2026-08-17  calendar=-
         "Your Application - Invite for 1. Interview"
msg 641  job=-    not_job_related       recv=2026-08-17  calendar=2026-08-19T12:00Z
         "Appointment booked: Formunauts - On Site (Ermis Chorinopoulos) @ Wed 19 Aug"
msg 662  job=-    not_job_related       recv=2026-08-18  calendar=-
         "Interview Slot Tomorrow"
msg 664  job=-    not_job_related       recv=2026-08-18  calendar=2026-08-26T14:00Z
         "Updated invitation: Formunauts - On Site (Ermis Chorinopoulos) @ Wed 26 Aug"
```

All four are from `matthias.gira@formunauts.at`. Message 638 matched job 535 correctly and was
classified correctly. The three that followed — including **both** messages carrying the actual
appointment — matched nothing and were filed `not_job_related`.

So the message that names the interview has no date, and the messages that carry the date are
attached to no job. The board showed `interview_at=None` on a job in `interview` status with an
appointment booked for Wednesday.

**This is a MATCHING defect, not a classification-keyword one, and TASK-182 does not fix it.** TASK-182
reads `calendar_summary` for interview keywords; "Formunauts - On Site" contains none, and adding one
would be the indiscriminate widening the owner explicitly rejected when they chose the conservative
option. Even a perfect classifier cannot help here: an unmatched message has no job whose
`interview_at` it could set.

Coordinator applied a one-row manual fix on 2026-08-24 so the owner would see Wednesday's interview:
`job 535.interview_at = 2026-08-26T14:00Z`, status untouched, before/after printed. That is a
patch on one row, not a fix — the next invitation will land the same way.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A calendar-carrying message from a sender already matched to a job on an earlier message matches that same job, or the reason it must not is stated with the case that would break
- [ ] #2 Measured against production before and after: how many of the 21 calendar-carrying messages change their `matched_job`, named individually — a message attaching to the WRONG job is a failure, not an acceptable cost
- [ ] #3 TASK-170's same-company rule is not regressed: where a company has more than one tracked job, the 90-day attribution cap and process-timing tie-break still decide, and the 8/8-correct, 17/17-refused measurement is repeated
- [ ] #4 An updated/rescheduled invitation supersedes the earlier one rather than creating a second appointment — msgs 641 and 664 are the same meeting moved from 19 Aug to 26 Aug
- [ ] #5 A message matching a job by sender does NOT thereby become status-changing; TASK-163's and TASK-169's guards still hold
- [ ] #6 Verified on the real thing: after the change, job 535 carries its interview date without the manual patch, proven by clearing it first
- [ ] #7 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Sender-domain matching is the obvious mechanism and also the dangerous one: ATS hosts (join.com,
ashbyhq.com, onlyfy.jobs, greenhouse) send for hundreds of employers, so matching on the sender's
domain would attach a Greenhouse rejection for company A to company B's job. Whatever is built must
distinguish "this exact sender address already matched this exact job" from "this domain sends mail
about jobs". Measure it against the 160 unmatched status-changing rows TASK-166 records, not just
against Formunauts.

The safest shape is probably the narrowest one: an exact `sender` address that already has a
confirmed `matched_job` on another message, bounded by the same 90-day window TASK-170 established.
That is a hypothesis, not a decision — measure it.
<!-- SECTION:NOTES:END -->
