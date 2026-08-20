---
id: TASK-149
title: backfill_message_bodies counts attachment-only rows as filled, forever
status: To Do
assignee: []
labels:
  - backend
  - mailbox
  - bug
dependencies:
  - TASK-132
  - TASK-135
priority: medium
ordinal: 149000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-20 while closing TASK-132 AC3 against the real mailbox. Six consecutive
`backfill_message_bodies --yes` runs each reported "Attempted 136: 11 filled", and the empty-body
count never moved from 136. The 11 are attachment-only messages: Gmail returns no body and no
calendar data, only an attachment manifest, so `has_content` passes, the row is written (attachments
again), `filled += 1` — and the candidate condition `body_text='' AND calendar_summary=''` still
matches the row, so every future run refetches and "fills" it again.

The code predicted this: the candidate-set comment marks the missing attachments gate as a known
ceiling — "not one of the six measured cases, so left as a known gap … Upgrade path: add that
condition if an attachment-only, body-less, calendar-less message is ever actually seen." Eleven of
them have now been seen. The counter is the real harm: an owner reads "11 filled" as progress; it is
the same 11 rows being rewritten forever, and "repeat until attempted=0" (TASK-132 AC3's stated
close condition) never terminates.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A row whose refetch yields only attachments is written once and then leaves the candidate set — a second run does not attempt it again, asserted by test with a fake transport
- [ ] #2 The run report distinguishes it: such a row is not counted in `filled` on the run that writes it a second time — either it is never re-attempted (preferred) or the report carries an explicit attachment-only count; "filled" may only count rows that leave the candidate set
- [ ] #3 The dry-run report and the --yes report agree on the same row (dry run does not promise a fill that --yes cannot deliver)
- [ ] #4 Verified against the real mailbox: two consecutive --yes runs, the second reports 0 filled and attempts fewer rows than the first (the 11 no longer among them); the before/after numbers recorded here
- [ ] #5 Full backend suite green; no test contacts a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The comment's own upgrade path is the fix: gate the candidate queryset on attachments being empty
(`attachments=[]` exact match works on both Postgres and the sqlite the tests use — assert that in a
test rather than assuming it, since JSONField exact-match variance is the reason the gate was
originally left out). Keep the append-only guarantee: only body/calendar/attachment fields are ever
written.
<!-- SECTION:NOTES:END -->
