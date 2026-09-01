---
id: TASK-212
title: Open the CV generator popup within five seconds
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-01 21:37'
updated_date: '2026-09-01 21:43'
labels:
  - backend
  - cv
  - performance
dependencies: []
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/tests/test_api.py
priority: high
ordinal: 211000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Generate CV and Motivation Letter popup can remain partially loaded for more than 20 seconds because optional local-model CLI discovery allows sequential 10-second and 15-second waits. Keep installed local providers when they respond, but bound optional probing so the full popup is usable within five seconds.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The CV generation preview completes within five seconds when both optional local-model probes hang
- [ ] #2 Responsive Ollama and LM Studio models remain available
- [ ] #3 Cloud model options and CV generation validation retain their current behavior
- [ ] #4 A focused regression proves the timeout budget without invoking a real model
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reduce each optional Ollama/LM Studio discovery timeout to two seconds, preserving responsive provider results and the existing shared cache. 2. Add one focused mocked regression proving the total sequential timeout budget is at most four seconds without starting a model. 3. Run focused/full gates, measure the released popup boundary, then release and close the task.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Measured the released preview at 0.468s while responsive, but the code allowed sequential optional waits of 10s and 15s, matching the reported >20s intermittent load. Capped each optional probe at 2s (4s total worst-case) without changing cloud discovery, responsive local providers, or shared caching. Focused tests: 3 passed. Separately verified the existing Salesforce CV already contains both exact requested edits, excludes the forbidden experience claims from document content, and renders as exactly 2 A4 pages; no AI rerun or external application submission was performed.
<!-- SECTION:NOTES:END -->
