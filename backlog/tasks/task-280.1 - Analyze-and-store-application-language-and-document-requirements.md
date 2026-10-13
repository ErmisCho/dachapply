---
id: TASK-280.1
title: Analyze and store application language and document requirements
status: To Do
assignee: []
created_date: '2026-10-12 15:03'
labels: []
dependencies: []
parent_task_id: TASK-280
priority: high
type: feature
ordinal: 277000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Extend the existing job analysis so its result can drive document preparation without another model call. The result must separate the posting language from any explicit application language, classify letter/message requirements conservatively, and preserve verifiable evidence instead of guessing from keywords.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Analysis records posting language as English, German, mixed, or unclear and separately records an explicitly requested application language when present.
- [ ] #2 Analysis classifies each requested document as required, preferred, optional, explicitly not accepted, not mentioned, or unclear, and identifies cover letter, motivation letter, short application message, or other named document.
- [ ] #3 Every explicit classification includes an exact supporting quote that exists in the stored posting/application text; without such evidence the result is not presented as required or preferred.
- [ ] #4 Explicit application instructions outrank the posting body language, negation such as no cover letter required is handled correctly, and contradictory instructions produce unclear rather than a fabricated answer.
- [ ] #5 The result is stored, editable, visible on the job and board, import/export compatible, and covered by importer/API/frontend tests.
<!-- AC:END -->
