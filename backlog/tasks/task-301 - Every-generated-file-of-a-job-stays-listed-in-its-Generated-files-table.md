---
id: TASK-301
title: Every generated file of a job stays listed in its Generated files table
status: To Do
assignee: []
created_date: '2026-10-16 06:43'
labels: []
dependencies: []
ordinal: 302000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-16): after the Wienerberger preparation the generated letter (and later the CV) did not show in the job's Generated files table, and the CV that failed in preparation was not visible there either. Files generated for a job, manually or by preparation (TASK-280.2/280.3), must stay visible there.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Files from manual generation, preparation variants, adjustments and short messages all appear in the job's Generated files table, newest first, with type and language
- [ ] #2 Files stay listed after reload and server restart; files deleted on disk show as missing instead of vanishing silently
- [ ] #3 Verified on Wienerberger in the browser; tests cover each source
<!-- AC:END -->
