---
id: TASK-232
title: Stop opening the output folder after every generation
status: Done
assignee: []
created_date: '2026-09-11 11:21'
updated_date: '2026-09-11 20:26'
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
- [x] #1 A completed generation and a completed readjustment both leave focus where it was - verified by running one of each on the owner machine, not by reading the flag
- [x] #2 Whatever the new default is, the opposite is still reachable by configuration, and the setting is documented where the owner will find it
- [x] #3 The generated files remain reachable from the popup without the folder opening - the existing artifact paths and copy controls are confirmed to cover it
- [x] #4 The backend suite stays green and the change is a no-op on non-Windows, as the existing os.startfile guard already is
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Done 2026-09-11 -- and the flag was doing two jobs

The obvious fix, flipping the default, would have broken the Reveal button.
`CODEX_CV_OPEN_OUTPUT_FOLDER` gates BOTH the automatic open after a run (cv_generator.py:664) and the
explicit Reveal action (line 533), and `test_reveal_artifact_respects_the_open_output_folder_kill_switch`
pins the second deliberately: "disabled server-side, not merely hidden in the UI". Conflating them is
exactly why the automatic one could not be switched off without also losing the button.

So there are now two settings. `CODEX_CV_OPEN_OUTPUT_FOLDER` keeps its meaning as the master
kill switch and its default. `CODEX_CV_OPEN_FOLDER_ON_FINISH` is new, governs only the automatic open,
and defaults **off**.

`test_a_finished_run_does_not_open_a_folder_by_itself_while_reveal_still_does` pins both halves at
once and was **falsified**: restoring the old single-flag gate turns it red. The one existing test that
asserts WHICH folder the automatic open targets now opts in explicitly, since it is testing the
mechanism rather than the default. Backend suite 1162 passed.
<!-- SECTION:NOTES:END -->
