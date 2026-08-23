---
id: TASK-179
title: interview_at is never written, so upcoming interviews is blind
status: To Do
assignee: []
labels:
  - backend
  - data
  - bug
dependencies: []
priority: high
ordinal: 179000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by coordinator measurement while verifying TASK-170 against production, 2026-08-23. Not a
TASK-170 dependency — filed separately so it is not lost.

`JobLead.interview_at` is populated on **0 of the owner's 82 tracked jobs**. Measured read-only
against production:

    applied_at        23/82 (28%)
    status_date       37/82 (45%)
    last_update_date  49/82 (60%)
    interview_at       0/82 (0%)
    apply_by           1/82 (1%)

The field exists, the model declares it, and TASK-078 ("Track interview dates and surface upcoming
interviews") is marked **Done**. Nine of the owner's jobs are in `interview` status right now and not
one of them carries an interview date.

The visible consequence is on the board: the **Upcoming interviews** panel renders "No interviews
scheduled. Add a date on a job's detail page." permanently, for a user who is actively interviewing.
It cannot ever show anything, because nothing writes the column it reads.

This is the same class of defect as the tasks CLAUDE.md already records: an implementation that
passed its tests and is empty against reality. The tests presumably set `interview_at` directly in a
fixture and then asserted the panel renders it, which never exercised the question of whether any
real code path writes it.

Two candidate causes, both unverified — whoever takes this must measure before fixing:
- no UI path actually persists the field (the detail-page editor may not include it, or may write
  `status_date` instead), or
- the mailbox `interview_invitation` classification never propagates the parsed calendar date onto
  the job, even though `MailboxMessage.calendar_start` IS captured (TASK-135).

The second is the more interesting one: if `calendar_start` is already stored per message and the
job's own `interview_at` stays null, the data to fill it is sitting one join away.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The reason `interview_at` is never written is established by measurement and stated — which code path was expected to write it, and what it does instead
- [ ] #2 An interview date reaches `JobLead.interview_at` through a real user-reachable path, verified end to end rather than by fixture
- [ ] #3 If `MailboxMessage.calendar_start` is the available source, state whether it is used and why or why not; a calendar invitation already parsed is not left unused without a reason
- [ ] #4 Backfill for the owner's existing 9 interview-status jobs is offered as a dry-run-by-default management command, never a migration, so a human inspects what would change before anything is written
- [ ] #5 Measured against production before and after: how many jobs carry `interview_at`, and how many rows the Upcoming interviews panel renders
- [ ] #6 A regression test that fails if the write path is removed — asserting the field is populated by the PATH, not set directly in the fixture
- [ ] #7 Backend suite green; the board's Upcoming interviews panel verified in a browser
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Do not "fix" this by having the panel fall back to `status_date`. That would make the panel look
populated while `interview_at` stays empty, and would hide the defect rather than close it — the
board would then claim an interview is scheduled on a date that is merely when the status last moved.

Check TASK-078's tests first. If they set `interview_at` directly and assert on rendering, they are
the reason this shipped empty, and AC6 exists to stop the same test being written again.
<!-- SECTION:NOTES:END -->
