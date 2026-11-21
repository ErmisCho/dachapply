---
id: TASK-403
title: 'Letter defaults: title, date, closing'
status: Done
assignee: []
created_date: '2026-11-21 09:16'
updated_date: '2026-11-21 09:45'
labels: []
dependencies: []
priority: high
ordinal: 404000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner fixes letter title ('Anschreiben'), date (\today) and closing by hand (10 edits). Evidence: audits 2026-11-20 (jobs/6526c3ef/tmp audit-reliability.md, audit-intake.md, audit-quality.md). Owner approved 2026-11-21.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 German letters default to the title 'Anschreiben' and every letter's date line uses \today (template or prompt rule; verified on a generated/compiled letter or template)
- [x] #2 Prompt states one standard closing per language
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #439. Running on localhost 2026-11-21 (runtime 03b8d2d, health 200; code presence checked). Letter templates already use \today; generated literal dates on the date line are restored to \today (tested); greeting rule in prompt.
<!-- SECTION:NOTES:END -->
