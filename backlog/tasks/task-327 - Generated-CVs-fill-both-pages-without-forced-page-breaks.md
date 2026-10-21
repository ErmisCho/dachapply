---
id: TASK-327
title: Generated CVs fill both pages without forced page breaks
status: To Do
assignee: []
created_date: '2026-10-21 09:34'
labels:
  - backend
dependencies: []
priority: high
ordinal: 327000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-21: generated CVs leave large gaps. Measured on the Comprehentia CV (job 1895): the base CV v1.5 has 29 bullets and fills both pages; the generated one has 16 bullets and a \newpage before Huawei that the base does not have, so page 1 ends early and page 2 ends early. All 16 generated CVs in C:\latex\CVs contain one forced \newpage; neither base v1.5 does. Owner chose: fill both pages.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The generation prompt tells the model to use the two pages fully: keep the base CV's experience bullets unless clearly irrelevant, and prefer keeping more relevant base content to leaving empty space, never exceeding two pages
- [ ] #2 A forced page break (\newpage, \clearpage, \pagebreak) the base CV does not contain is removed from the generated CV before compiling; orphaned employer headings stay prevented by the template's \Needspace
- [ ] #3 Adjust/readjustment prompts never add forced page breaks either
- [ ] #4 The 2-page limit check and repair loop are unchanged
- [ ] #5 Live: one newly generated CV has no forced break and its pages have no large empty area
<!-- AC:END -->
