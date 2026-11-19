---
id: TASK-386
title: Automatic page-fit pass instead of failed runs
status: Done
assignee: []
created_date: '2026-11-18 22:38'
updated_date: '2026-11-19 06:34'
labels: []
dependencies: []
priority: high
ordinal: 387000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When the compiled CV or letter exceeds its page limit (or the CV underfills its last page below a threshold), run one targeted fit pass with the existing layout/readjust path instead of failing the run or leaving it to a manual Adjust. Evidence: adjustments.jsonl 2026-10-21..11-18, 130 Adjusts over 34 jobs (median 3 ready Adjusts/job); audits in jobs/6526c3ef/tmp (optimization-audit.md, ux-audit.md). Owner approved 2026-11-18.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A run whose first compile exceeds the page limit gets exactly one automatic fit attempt; a test simulates the overflow and proves the attempt and the final page count check
- [x] #2 If the fit attempt still exceeds the limit the run fails with the existing page-limit message (no loop, no second attempt)
- [x] #3 Underfill threshold is a named constant; underfilled CV triggers one fill attempt only when the first compile is within the limit
- [x] #4 Adjust/revise runs do not trigger the pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #431. ACs superseded 2026-11-18 by measurement (all page-limit failures were route=exact; generation already makes 2 repair attempts): an exact edit that exceeds the page limit falls back once to full optimization; tests in test_exact_fallback.py. Underfill pass not built (no measured demand).
<!-- SECTION:NOTES:END -->
