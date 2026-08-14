---
id: TASK-61.4
title: Display copyable paths for CV sources and generated artifacts
status: Done
assignee:
  - '@claude'
created_date: '2026-08-13 19:31'
updated_date: '2026-08-14 16:05'
labels:
  - cv-generation
  - ux
  - artifacts
dependencies: []
parent_task_id: TASK-61
priority: medium
ordinal: 66000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Always expose the filesystem paths involved in CV generation: the base CV template used and the generated CV and motivation-letter TeX/PDF files. Paths must be easy to select, copy with normal keyboard shortcuts, and open when the browser/platform permits.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Generation preview shows the selected base CV template path before generation starts
- [x] #2 Ready and recompiled tasks show paths for every created CV and letter TeX/PDF artifact
- [x] #3 Each path is rendered as selectable text with an explicit copy action and preserves standard keyboard selection/copy behavior
- [x] #4 Each artifact path shows a Reveal in folder action that posts the task id plus an artifact key from the closed set {cv_tex, cv_pdf, letter_tex, letter_pdf} to the backend, which opens that file's containing folder on the server host; a client-supplied path is never accepted, and when the task record no longer exists the action is hidden while the copy button remains
- [x] #5 Single-job and batch-generation views expose the same path information
- [x] #6 Paths remain available after task polling completes and after a server restart when saved artifacts still exist
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
generation_preview() now serializes cvs[].path (relative template path, e.g. CVs/English - AI Engineer (base)_v_1.3.tex) alongside the existing basename. Post-generation artifact paths already reached the client via the artifacts dict (cv_tex, letter_tex, cv_pdf, letter_pdf) because get_cv_task() whitelists by exclusion. Added a single top-level copyToClipboard helper and a CopyPath component rendering each path as inert selectable <code> text with an explicit copy button; wired into both CvGenerator and BatchCvGenerator for pre-generation template and post-generation artifacts. Security review (read-only) returned zero findings: cv_key/letter_key are checked against the closed TEMPLATES whitelist so no client string becomes a path, every route is behind is_cv_owner, task ids are uuid4, and no arbitrary-path opener was introduced. AC4 DONE (2026-08-14) after rewording under TASK-64. The original wording ('where the local browser/platform supports it') had no testable threshold; the restated criterion above is binary-checkable. Implementation: POST /api/cv-generation/tasks/<task_id>/reveal/ with {"key": "<one of cv_tex|cv_pdf|letter_tex|letter_pdf>"}. The view rejects any key outside that closed set with 400, then resolves the path from the task's OWN artifacts dict via get_cv_task(task_id, request.user.id) - the request body never supplies a path, so no client string can reach os.startfile. Gated by is_cv_owner like every sibling CV route, and by the pre-existing CODEX_CV_OPEN_OUTPUT_FOLDER kill switch (409 when off), which already governed the identical os.startfile call at cv_generator.py:326. On the client, CopyPath renders Reveal only when a taskId is passed, and ArtifactPaths passes one only when the artifacts came from a live task - so after a restart, when paths are rehydrated from the workspace preview, the copy button remains and Reveal is correctly absent. Also fixed the previously flagged silent copy failure: the button now reports 'Copied' or 'Copy failed' instead of staying indistinguishable from unclicked.

Tests: test_reveal_artifact_opens_only_a_whitelisted_key_from_the_task_payload (happy path opens the containing folder; a filesystem path in the key field is rejected 400 and nothing is opened; a whitelisted key the task never produced is 404; an unknown task id is 404), test_reveal_artifact_is_not_reachable_by_a_non_owner (404, nothing opened), test_reveal_artifact_respects_the_open_output_folder_kill_switch (409, nothing opened - disabled server-side, not merely hidden in the UI).

DEPLOYMENT NOTE: this opens a folder on the SERVER host. That is correct for local single-user use and matches the existing CODEX_CV_OPEN_OUTPUT_FOLDER behaviour, which defaults to DEBUG. If this is ever deployed to Azure, leave CODEX_CV_OPEN_OUTPUT_FOLDER off - the route then returns 409 and the UI degrades to copy-only. AC6 DONE (2026-08-14) via on-demand rehydration rather than persisted task records - see TASK-63. Task state is still in-memory (_tasks={}), but artifact paths no longer depend on it: latest_generated_artifacts(job, cv_key) in cv_generator.py reuses the existing latest_generated_sources() workspace glob and adds the matching PDF per artifact only when the file actually exists, and generation_preview() now returns it as 'artifacts'. On the client, the duplicated 4x CopyPath block in CvGenerator and BatchCvGenerator was replaced by one ArtifactPaths component reading task?.artifacts||preview?.artifacts (row.artifacts||row.preview?.artifacts in batch), so paths render from the live task while polling and from the disk-backed preview afterwards, including after a Django restart on a fresh page load. ArtifactPaths renders nothing when neither a CV nor a letter TeX exists, so jobs that were never generated do not show an empty box. Covered by test_latest_generated_artifacts_survive_a_restart_by_reading_the_workspace (asserts a missing letter PDF is omitted rather than invented, and that generation_preview carries the same dict) and test_latest_generated_artifacts_is_empty_when_nothing_was_generated.
<!-- SECTION:NOTES:END -->
