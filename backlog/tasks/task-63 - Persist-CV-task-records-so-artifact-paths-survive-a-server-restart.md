---
id: TASK-63
title: Persist CV task records so artifact paths survive a server restart
status: Done
assignee:
  - '@claude'
created_date: '2026-08-13 21:44'
updated_date: '2026-08-14 16:05'
labels:
  - enhancement
  - cv-generation
dependencies: []
priority: medium
ordinal: 68000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
cv_tasks.py:14 holds _tasks={} in process memory, so every generation task record - including the artifacts dict with the CV and letter TeX/PDF paths - is lost when Django restarts. TASK-61.4 AC6 requires paths to remain available after a server restart when the saved artifacts still exist on disk, and that criterion cannot be met while task state is in-memory only. The files themselves survive, and latest_generated_sources() in cv_generator.py already reconstructs source paths by globbing the workspace, so one option is rehydrating from disk on demand rather than persisting full task records. Surfaced while closing TASK-61.4.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Artifact paths for a completed generation remain visible in the UI after a Django restart, provided the files still exist on disk
- [x] #2 The chosen approach is documented as either persisted task records or on-demand rehydration from the workspace
- [x] #3 TASK-61.4 AC6 can be checked off
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Chose ON-DEMAND REHYDRATION over persisting task records. Task state stays in memory (cv_tasks._tasks is unchanged); only the artifact paths are recovered, and they are recovered from the files themselves, so there is no second copy of the truth to keep in sync and nothing to migrate or expire.

latest_generated_artifacts(job, cv_key) in cv_generator.py reuses the existing latest_generated_sources() mtime glob for the TeX files and attaches the sibling .pdf per artifact only when that file actually exists - a missing PDF is omitted rather than reported as a path that would 404. generation_preview() returns it as 'artifacts'. The client renders one ArtifactPaths component fed task?.artifacts||preview?.artifacts, so paths come from the live task while polling and from the disk-backed preview afterwards, including on a fresh page load after a restart.

Rejected: persisting task records (a DB table or JSON sidecar) - it would need schema, cleanup and staleness handling to deliver strictly less than reading the workspace, since a persisted path can outlive the file it points at.

Tests: test_latest_generated_artifacts_survive_a_restart_by_reading_the_workspace, test_latest_generated_artifacts_is_empty_when_nothing_was_generated. Both use a tmp_path workspace, never the real one.
<!-- SECTION:NOTES:END -->
