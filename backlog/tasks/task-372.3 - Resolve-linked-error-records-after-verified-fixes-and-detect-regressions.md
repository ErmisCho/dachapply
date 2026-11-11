---
id: TASK-372.3
title: Resolve linked error records after verified fixes and detect regressions
status: To Do
assignee: []
created_date: '2026-11-11 15:26'
labels:
  - observability
  - backlog
  - reliability
dependencies:
  - TASK-372.2
parent_task_id: TASK-372
priority: high
type: feature
ordinal: 375000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the resolution part of TASK-372. Done means a bug fix is verified under the existing task-completion policy, not merely that an agent said it was fixed. Mark only the linked occurrence records resolved, retain their history, and exclude them from future error analysis. Preserve detection of genuinely new failures after the fix.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Verified completion of a linked Backlog bug records its fix/verification reference and marks the associated occurrence IDs resolved/done without deleting the evidence or unrelated occurrences.
- [ ] #2 A subsequent triage run, application restart and replay/rotation of the same old source records perform zero new analysis or task creation for those resolved occurrence IDs.
- [ ] #3 New occurrences are never swallowed by a blanket resolved-signature filter; distinguish replayed historical evidence, an unfixed old runtime/build, and a new post-fix regression using available version/time boundaries.
- [ ] #4 A genuine post-fix recurrence produces a new linked regression incident/task or explicitly reopens the matching bug, according to one documented policy; it does not repeatedly reopen on each replay.
- [ ] #5 Concurrent error arrival during closure cannot mark later unrelated/new occurrences done, and failed task-status synchronization is retryable without duplicate records or lost evidence.
- [ ] #6 An end-to-end lifecycle test covers failure -> grouped task -> verified fix/Done -> linked logs resolved -> old records skipped -> new regression captured, including interrupted synchronization.
<!-- AC:END -->
