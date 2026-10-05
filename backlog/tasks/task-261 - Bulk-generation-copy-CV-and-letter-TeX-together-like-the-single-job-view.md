---
id: TASK-261
title: 'Bulk generation: copy CV and letter TeX together, like the single-job view'
status: To Do
assignee: []
created_date: '2026-10-05 11:43'
updated_date: '2026-10-05 11:59'
labels: []
dependencies: []
priority: medium
ordinal: 259000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the bulk 'Generate selected applications' panel, each ready job has a copy button, but it calls navigator.clipboard.writeText directly after async work and shows 'Clipboard access was blocked' (owner screenshot 2026-10-05, reebuild GmbH row). The single-job view copies CV + letter TeX (starting with '% Job listing: <url>') reliably via copyToClipboard/server-side copy. Bulk should behave the same.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Clicking a ready bulk row's copy button puts that job's CV TeX and letter TeX on the clipboard, in the same combined format the single-job copy produces (verified by reading the clipboard in the browser on localhost:8000)
- [ ] #2 Bulk copy uses the same copy helper/fallback as the single-job view; no 'Clipboard access was blocked' on a normal click in Chrome
- [ ] #3 A row whose server-side auto-copy succeeded still shows 'Generated TeX files copied automatically.'; a failed copy shows an actionable error instead of silently doing nothing
- [ ] #4 Frontend test covers the bulk copy path producing CV+letter content
- [ ] #5 Owner decision 2026-10-05: a 'Copy all' button copies every ready row's CV+letter TeX together, each job block starting with its '% Job listing: <url>' line and a clear separator between jobs
- [ ] #6 Owner decision 2026-10-05: auto-copy toggle in the bulk panel, default ON, remembered across reloads; when ON, the combined 'Copy all' payload is copied once when the whole batch finishes (not per job, so jobs no longer overwrite each other). Must work on localhost:8000 without an extra click (server-side OS clipboard copy is acceptable since the server is the owner's PC); measured by reading the clipboard after a 2-job batch
- [ ] #7 When the toggle is OFF nothing is auto-copied; per-row and Copy all buttons still work
<!-- AC:END -->
