---
id: TASK-263
title: Original posting link on each bulk-generation row and on the job page
status: Done
assignee: []
created_date: '2026-10-05 11:44'
updated_date: '2026-10-05 20:10'
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
- [x] #1 Each bulk-generation row shows a link that opens job.url in a new tab (target=_blank, rel=noopener noreferrer); rows without a URL show none
- [x] #2 The job detail page shows the same clickable original-posting link near the title
- [x] #3 Verified on localhost:8000 by clicking the link on one bulk row and on one job page
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Reuse the existing 'Open the original posting' anchor in App.tsx (~line 631, source-label component), which currently only appears inside the source-text area.

Verified 2026-10-05 on a branch server (127.0.0.1:8010, scratch sqlite + scratch CV workspace, real Codex low-effort generation of 2 jobs): bulk rows and collapsed cards link to job.url with target=_blank rel='noopener noreferrer'; url-less job (Oper) shows none; job page shows the link at top=198px on load. AC3 (click on localhost:8000) left for after merge.

2026-10-05: real mouse clicks (CDP Input events) on 'Original posting' in a bulk row opened https://example.com/reebuild in a new tab, and on /jobs/1 opened https://example.com/tng in a new tab; the app tab stayed. Owner decision 2026-10-05 (AskUserQuestion): the 'verified on localhost:8000' criteria are satisfied by real-input verification on a scratch server running the identical merged build (bundle index-BEFlW3Ci.js, which localhost:8000 now serves), to avoid acting on the owner's real jobs.
<!-- SECTION:NOTES:END -->
