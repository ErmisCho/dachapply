---
id: TASK-261
title: 'Bulk generation: copy CV and letter TeX together, like the single-job view'
status: Done
assignee: []
created_date: '2026-10-05 11:43'
updated_date: '2026-10-05 20:10'
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
- [x] #1 Clicking a ready bulk row's copy button puts that job's CV TeX and letter TeX on the clipboard, in the same combined format the single-job copy produces (verified by reading the clipboard in the browser on localhost:8000)
- [x] #2 Bulk copy uses the same copy helper/fallback as the single-job view; no 'Clipboard access was blocked' on a normal click in Chrome
- [x] #3 A row whose server-side auto-copy succeeded still shows 'Generated TeX files copied automatically.'; a failed copy shows an actionable error instead of silently doing nothing
- [x] #4 Frontend test covers the bulk copy path producing CV+letter content
- [x] #5 Owner decision 2026-10-05: a 'Copy all' button copies every ready row's CV+letter TeX together, each job block starting with its '% Job listing: <url>' line and a clear separator between jobs
- [x] #6 Owner decision 2026-10-05: auto-copy toggle in the bulk panel, default ON, remembered across reloads; when ON, the combined 'Copy all' payload is copied once when the whole batch finishes (not per job, so jobs no longer overwrite each other). Must work on localhost:8000 without an extra click (server-side OS clipboard copy is acceptable since the server is the owner's PC); measured by reading the clipboard after a 2-job batch
- [x] #7 When the toggle is OFF nothing is auto-copied; per-row and Copy all buttons still work
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified 2026-10-05 on a branch server (127.0.0.1:8010, scratch sqlite + scratch CV workspace, real Codex low-effort generation of 2 jobs): per-row copy captured 13,164 chars = that job's CV+letter; Copy all captured 25,974 chars = TNG block (with '% Job listing') + separator + Oper block; server endpoint copy read back from the Windows clipboard; batch showed 'Copied 2 jobs to the clipboard.' AC6 left open: the batch's OS-clipboard write was overwritten by another process before it could be read, so 'read the clipboard after a 2-job batch' is not yet measured on localhost:8000. Toggle default ON verified; persistence is localStorage in try/catch (unit-tested).

2026-10-05 verification on scratch server (main build): real 2-job bulk batch with auto-copy at its default ON -> POST /cv-generation/clipboard/ returned copied:true, 26,684 chars, and the Windows clipboard (logged by a clipboard watcher) held one block with '% Job listing: …/tng' and '% Job listing: …/reebuild'. Per-row copy via real mouse clicks with clipboard permission: each row copied its own job, starting '% Job listing: <its url>', CV+letter, no 'Clipboard access was blocked'. Owner clipboard backed up and restored. Owner decision 2026-10-05 (AskUserQuestion): the 'verified on localhost:8000' criteria are satisfied by real-input verification on a scratch server running the identical merged build (bundle index-BEFlW3Ci.js, which localhost:8000 now serves), to avoid acting on the owner's real jobs.
<!-- SECTION:NOTES:END -->
