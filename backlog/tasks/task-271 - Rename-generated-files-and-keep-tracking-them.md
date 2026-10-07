---
id: TASK-271
title: Rename generated files and keep tracking them
status: Done
assignee: []
created_date: '2026-10-07 12:00'
labels:
  - backend
  - ui
dependencies: []
priority: medium
ordinal: 268000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-10-07: "make it also possible that I can rename the files generated so that they are tracked afterwards and this new name is preferred for that job listing and used in the generation and adjustment process".

Owner decision on how to rename ("Both (Recommended)"): a rename button next to each generated file in the app, and the app also notices when the owner renames a file in Explorer.

Today a job's files are tracked by path in a hidden sidecar `<workspace>/.dachapply-artifacts/<sha256(user:job)>.json` (TASK-256). A file renamed in Explorer is lost: its sidecar path no longer exists, and the name-based fallbacks don't match the new name. The owner already renamed one real file this way (C:\latex\CVs\...-Accenture-AI-Engineer-For-Generative-AI.pdf beside a .tex with the old name).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 In-app rename: every generated CV and letter in the single-job Generated files panel and in the bulk rows has a rename control. Saving a new name renames the .tex and its .pdf together, in the same folder, and the panel shows the new paths without a reload
- [x] #2 The name is validated server-side. It cannot contain path separators or characters Windows forbids, cannot be empty, and a typed .tex/.pdf extension is accepted and normalized. Renaming onto an existing file is refused with a clear message, and nothing is overwritten or half-renamed (the .tex and .pdf move together or neither moves)
- [x] #3 Explorer rename: when the owner renames a tracked .tex (with or without its .pdf) in Explorer, the next time the job's files are looked up (opening the job or popup) the app finds it by content, updates its tracking, and shows the new name. A renamed .pdf whose .tex kept the old name is matched as well. Another job's files are never adopted
- [x] #4 The new name is preferred for that job:
  - Adjust (readjust) and Recompile keep writing to the renamed files.
  - A new Generate for that job uses the renamed name as its base. The existing replace-or-keep confirmation decides between overwriting and a -2 suffix, as it does today.
  - Copy TeX and the download zip use the new names.
  - The preference survives a server restart.
- [x] #5 Sent documents stay read-only (TASK-256 AC7): renaming a file an Applied job was sent with keeps the sent-document pointer valid (the pointer follows the rename), and generation still never writes into a sent file
- [x] #6 Tests cover in-app rename (both files, validation, collision, atomicity), Explorer-rename detection for .tex and .pdf, non-adoption of another job's file, and the preferred name used by generate, readjust and recompile. Each new test fails when its behaviour is reverted. Full backend suite green in CI, plus vitest and tsc
- [x] #7 Verified in a browser on a scratch copy: an in-app rename updates the panel. A rename done on disk outside the app is picked up after reopening the job, and Recompile writes to the renamed file
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Endpoint `POST /api/jobs/<id>/cv-generation/rename/ {artifact: cv|letter, letter_template, name}`.
  - The file is resolved server-side from the job's tracking; no path is ever taken from the client.
  - Responses: 200 with the new artifacts, 400 for an invalid name, 409 when the target exists.
  - The .tex and .pdf move together, and the first move is rolled back if the second fails.
  - Validation: a typed .tex/.pdf is stripped. Refused: empty names, `<>:"/\|?*`, control characters, a trailing dot, Windows reserved names, and more than 150 characters.
- The sidecar stores `names` (the preferred stems) and `size:sha256` digests. `_retire` carries both, so sent-document pointers follow a rename.
  - Generate uses the preferred stem; the existing replace-or-keep confirmation is unchanged.
  - Readjust and Recompile write to whatever the lookup returns, which is the renamed file.
  - Finished in-memory tasks follow a rename (`rename_task_paths`), so Copy TeX, Download and Reveal keep working.
- Explorer rename: only when a tracked file is missing, the lookup scans CVs/, CVs/sent and output/ for the same digest. It never adopts a file any sidecar or retired entry claims. A .pdf renamed on its own takes its .tex to the same name, and the reverse, because ~8 readers derive the pdf as `tex.with_suffix('.pdf')`. So opening a job can rename that companion file on disk.
- Limitation: files recorded before this change have no digests, so an Explorer rename done before the upgrade is not followed. An in-app rename works for them.
- Coordinator browser verification (headless Chrome, scratch server built from the branch, scratch workspace):
  - In-app rename of the CV by a real click on Save: both files were renamed on disk (`Ermis-CV-TNG-Renamed-Test.tex/.pdf`) and the panel updated without a reload.
  - Renaming the letter onto an existing name showed "…Oper-Ai-Solutions-Engineer.tex already exists in output. Choose another name." The server returned 409 and nothing moved.
  - Explorer: I renamed the letter's .tex and .pdf, and renamed the CV's .pdf only, then reopened the job. The panel showed `Letter-TNG-From-Explorer.*` and `CV-PDF-Only-Rename.*`, and the CV .tex had been renamed to match.
  - Recompile then rewrote both renamed PDFs, with mtimes after the start of the run, and created no -2 files.
  - The bulk dialog shows Rename CV and Rename Letter on each row.
- Tests: test_rename_artifacts.py has 36 tests and renameArtifact.test.tsx has 4. 13 mutation checks each fail at least one test. Agent's full backend run: 1364 passed, plus 4 known local-only model-cache failures. vitest 344 passed, tsc clean.
<!-- SECTION:NOTES:END -->
