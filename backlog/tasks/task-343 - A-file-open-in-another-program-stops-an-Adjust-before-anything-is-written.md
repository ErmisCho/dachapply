---
id: TASK-343
title: A file open in another program stops an Adjust before anything is written
status: Done
assignee: []
created_date: '2026-10-22 16:18'
updated_date: '2026-10-22 16:34'
labels:
  - backend
dependencies: []
priority: high
ordinal: 343000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-22 (screenshot): Zühlke Adjust failed '[WinError 32] The process cannot access the file because it is being used by another process'. Measured: CVs\sent\...Zuhlke...Advanced-Data-Engineer.pdf was open in Foxit PDF Editor (locked). recompile_generated_package's write loop had already copied the edited CV .tex (18:16:23) when the PDF copy failed, so the .tex holds the edits, the PDF is stale and the letter was never written. persist_generated_files (full generation) writes the same way.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Before writing any file, every target .tex/.pdf that exists is checked for write access; if one is locked, nothing is written and the error names the file and says to close it (e.g. in the PDF viewer) and try again
- [x] #2 Applies to Adjust/recompile (recompile_generated_package) and full generation (persist_generated_files)
- [x] #3 Test simulates a locked target and asserts no file changed
- [x] #4 The Zühlke files are brought back to a consistent state (CV PDF rebuilt from the edited .tex, letter edits applied) once Foxit releases the file
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #354. Live: _ensure_writable on the real Foxit-locked Zühlke PDF raised 'Chorinopoulos-Ermis-CV-Zuhlke-...pdf is open in another program (for example a PDF viewer). Close it and try again; nothing was changed.' and both files kept their times. After the owner closed Foxit: CV PDF rebuilt from the edited .tex (18:33:58, 2 pages, Huawei on page 1); the 6 letter blocks from the logged instructions applied without AI (18:34:12, 1 page). 11 CV blocks had already been applied, 0 unmatched.
<!-- SECTION:NOTES:END -->
