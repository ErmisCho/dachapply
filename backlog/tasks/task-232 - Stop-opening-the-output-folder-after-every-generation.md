---
id: TASK-232
title: Stop opening the output folder after every generation
status: To Do
assignee: []
created_date: '2026-09-11 11:21'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 231000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-09-11: the CV folder should not open every time a generation or readjustment finishes.

There is already a flag. `CODEX_CV_OPEN_OUTPUT_FOLDER = env_bool("CODEX_CV_OPEN_OUTPUT_FOLDER", DEBUG)` (settings.py:144) is read in two places in cv_generator.py (lines 533 and 661, both guarded by `getattr(os, "startfile", None)` so it is a no-op off Windows). It defaults to `DEBUG`, which means ON for the local runtime - which is why it happens.

So the owner can turn it off today with one line in the repo-root `.env`:

    CODEX_CV_OPEN_OUTPUT_FOLDER=0

What this task is actually for is the DEFAULT. When the flag was written the popup had no other way to reach the files; it now has ArtifactPaths and per-file CopyPath buttons, so a window stealing focus on every run is a worse answer than the one already on screen. Changing a default is a behaviour change for anyone relying on it, so it gets a task rather than a quiet edit.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A completed generation and a completed readjustment both leave focus where it was - verified by running one of each on the owner machine, not by reading the flag
- [ ] #2 Whatever the new default is, the opposite is still reachable by configuration, and the setting is documented where the owner will find it
- [ ] #3 The generated files remain reachable from the popup without the folder opening - the existing artifact paths and copy controls are confirmed to cover it
- [ ] #4 The backend suite stays green and the change is a no-op on non-Windows, as the existing os.startfile guard already is
<!-- AC:END -->
