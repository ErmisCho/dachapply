---
id: TASK-153
title: Reword the ONTEC-named criteria — those messages carry no invitation
status: To Do
assignee: []
labels:
  - process
  - mailbox
dependencies:
  - TASK-135
  - TASK-150
priority: low
ordinal: 153000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-135 AC1 and TASK-150 AC4 both name the same real messages as their proof: the ONTEC AG
"Einladung zum Kennenlernen" mail. Measured 2026-08-20 by fetching all 7 of those messages from
Gmail directly (`format=full`, walking the MIME tree), they cannot serve as that proof, for two
independent reasons:

1. **None of them carries a calendar part.** Their MIME trees are `text/html`,
   `multipart/alternative` + `text/plain`, and `multipart/mixed` + `image/png`. There is no
   `text/calendar` anywhere in any of the seven, so there is no invitation for the app to parse or
   render — TASK-150's `--calendar-missing` mode correctly stamped three of them
   "checked, none" and the rest carry no body to check.
2. **All seven are unmatched (`matched_job` is NULL).** Even with calendar data they would never
   appear in a job conversation view, which is where both criteria require the block to show.

The criteria's *intent* is sound and is satisfiable: the same session recovered real calendar data
for 14 stored messages, one of which (uid 913-adjacent, "Hays - Austausch Jobmöglichkeit",
`calendar_start` 2026-06-01 11:00 UTC) IS matched to job 34. TW-005 says a criterion no
implementation can satisfy gets reworded through its own filed task, never silently relaxed — that
is this task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 TASK-135 AC1 is reworded to name "one real, job-matched message that carries a `text/calendar` invitation" instead of the ONTEC messages, keeping the what/when/with-whom requirement unchanged
- [ ] #2 TASK-150 AC4 is reworded the same way, keeping "observed in the browser" unchanged
- [ ] #3 Both task files record why the ONTEC messages were disqualified (no calendar part in Gmail; unmatched to any job), so the next reader does not re-litigate it
- [ ] #4 With the new wording, the Hays invitation on job 34 is used as the proof and both criteria are ticked only after it is actually observed rendering in the browser
<!-- AC:END -->
