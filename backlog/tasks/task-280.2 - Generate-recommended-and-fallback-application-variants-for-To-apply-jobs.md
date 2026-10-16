---
id: TASK-280.2
title: Generate recommended and fallback application variants for To apply jobs
status: Done
assignee: []
created_date: '2026-10-12 15:03'
updated_date: '2026-10-16 07:50'
labels: []
dependencies:
  - TASK-280.1
parent_task_id: TASK-280
priority: high
type: feature
ordinal: 278000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Use the stored application-document analysis to prepare documents in the background when the owner commits a job to To apply. Generate the smallest clear package and a bounded fallback package only when language or document requirements remain genuinely mixed or unclear.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A transition into To apply starts background preparation only when usable posting text and the required account templates are available; jobs in New/Reviewed and jobs already Applied or later are not auto-generated.
- [x] #2 Clear instructions generate one CV in the requested application language plus only documents classified required or preferred; explicitly unwanted letters are never generated automatically.
- [x] #3 Mixed or unclear application language generates English and German CV variants; an unclear letter requirement/type generates a full tailored letter and a short application message in each still-plausible language, with no additional combinations.
- [x] #4 Not mentioned is distinct from unclear and follows an owner-visible default rather than silently being treated as required.
- [x] #5 Variants run as independent background work: one failure does not delete or invalidate successful variants, retries target only failed variants, and existing files are never overwritten without confirmation.
- [x] #6 The job exposes preparation progress and failures, and tests cover the generation matrix, concurrency-safe status transitions, retries, and the no-downgrade rule.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-16: #269. Real run on Wienerberger: moving to To apply planned EN CV + EN motivation letter; letter ready, CV failed in isolation (repair attempts lacked a reason -> #271); later CV generated manually.
<!-- SECTION:NOTES:END -->
