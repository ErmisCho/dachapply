---
id: TASK-263
title: Original posting link on each bulk-generation row and on the job page
status: To Do
assignee: []
created_date: '2026-10-05 11:44'
updated_date: '2026-10-05 11:44'
labels: []
dependencies: []
priority: low
ordinal: 261000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the bulk 'Generate selected applications' panel the job title links to the in-app job page only; there is no link to the original posting (job.url). Owner wants the original link clickable for every selected job, and also on the job's own page.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each bulk-generation row shows a link that opens job.url in a new tab (target=_blank, rel=noopener noreferrer); rows without a URL show none
- [ ] #2 The job detail page shows the same clickable original-posting link near the title
- [ ] #3 Verified on localhost:8000 by clicking the link on one bulk row and on one job page
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Reuse the existing 'Open the original posting' anchor in App.tsx (~line 631, source-label component), which currently only appears inside the source-text area.
<!-- SECTION:NOTES:END -->
