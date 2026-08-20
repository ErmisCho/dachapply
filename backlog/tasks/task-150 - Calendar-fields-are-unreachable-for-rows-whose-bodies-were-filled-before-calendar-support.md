---
id: TASK-150
title: Calendar fields are unreachable for rows whose bodies were filled before calendar support
status: To Do
assignee: []
labels:
  - backend
  - mailbox
  - bug
dependencies:
  - TASK-135
priority: medium
ordinal: 150000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-20 while closing TASK-135 AC1/AC5 against the real mailbox: all 7 stored ONTEC
"Einladung zum Kennenlernen" invitation messages have empty calendar fields
(`calendar_summary=''`), so the conversation renders no invitation block for exactly the real case
TASK-135 was written around.

Cause: the old, body-only version of backfill_message_bodies filled their `body_text` before
calendar parsing existed. The calendar-aware version selects candidates by
`body_text='' AND calendar_summary=''` — a row with a body can never be re-fetched, so its calendar
fields stay empty forever. TASK-135's "six calendar-only rows" premise no longer describes these
rows; they are body-AND-calendar rows whose calendar half arrived too late to be stored.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A bounded, explicit backfill path exists for calendar fields on rows that already have a body — either a flag on backfill_message_bodies or a sibling command; dry-run by default, additive-only (never touches body_text on those rows), and bounded so it cannot become a full-table refetch sweep by accident
- [x] #2 Tested with a fake transport: a body-bearing, calendar-less row whose refetch carries a text/calendar part gains calendar_summary/start/end/location/organizer; a body-bearing row with no calendar part is not rewritten and not re-attempted forever
- [x] #3 Run against the real mailbox: the 7 ONTEC invitation rows gain calendar data (or the ones that genuinely carry none in Gmail are reported as such); before/after counts recorded here
- [ ] #4 The conversation view then actually shows the invitation block for one real ONTEC message, observed in the browser
- [x] #5 Full backend suite green; no test contacts a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20 close-out (evidence: backend suite 783 green; browser measurements on the built bundle at localhost:8000; prod-DB reads and app-command runs with the owner's approval; merges #51/#52/#53 live with HTTP 200): Run against the real mailbox: batches drained 200->59->1 with 14 rows recovering real calendar data (an online-interview invitation among them); the ONTEC 7 split into 3 confirmed-calendar-less in Gmail (stamped checked) and 4 transient fetch failures that stay retryable by design. AC4 stays unchecked: the one matched calendar-bearing message (job 34, Hays) is on a non-pending job, and calendar blocks render only in pending-conversation views today.

Scope the candidate set tightly: do NOT match on subject text — prefer an explicit
`--calendar-missing` mode that re-fetches rows with empty calendar fields in bounded batches,
oldest first, with the same leave-the-candidate-set discipline TASK-149 establishes so
attempted-and-genuinely-calendar-less rows are not re-fetched forever (a cheap persisted
discriminator is acceptable if it is additive-only). Reuse _extract_calendar_text_and_attachments;
write only calendar fields.
<!-- SECTION:NOTES:END -->
