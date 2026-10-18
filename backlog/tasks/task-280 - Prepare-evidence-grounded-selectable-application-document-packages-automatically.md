---
id: TASK-280
title: >-
  Prepare evidence-grounded, selectable application document packages
  automatically
status: Done
assignee: []
created_date: '2026-10-12 15:03'
updated_date: '2026-10-18 09:00'
labels: []
dependencies: []
priority: high
type: feature
ordinal: 276000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reduce the time from choosing a job to submitting its application. During the existing job analysis, determine the posting/application language and whether a cover letter, motivation letter, or short application message is required, preferred, optional, explicitly unwanted, not mentioned, or genuinely unclear. For jobs the owner moves to To apply, prepare the recommended documents automatically and create a bounded English/German fallback set when the evidence remains mixed or unclear. Generated variants remain drafts: the owner previews them, chooses what to keep, adjusts documents independently, and selects the final application package before the job is treated as ready to submit. This never submits an application.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each analyzed job shows an evidence-grounded posting/application language and document recommendation, including the exact source text that supports explicit requirements or a clear indication that the posting provides no evidence.
- [ ] #2 A To apply job automatically receives the smallest appropriate document package; genuinely mixed or unclear requirements produce the agreed bounded English/German CV, full-letter, and short-message fallbacks rather than an unbounded set of combinations.
- [ ] #3 The owner can preview every variant, keep or discard it, adjust it independently, and select one final application package without an automatic overwrite or deletion of another variant.
- [ ] #4 Ready to submit distinguishes a user-selected final package from merely generated drafts; Applied and later/closed statuses are never downgraded.
- [ ] #5 Failures are isolated to the affected variant, existing manual generation remains usable, and automated tests cover clear, absent, contradictory, mixed, and unclear posting instructions.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
All subtasks done; end-to-end verified on PORR 1544 (2026-10-18).
<!-- SECTION:NOTES:END -->
