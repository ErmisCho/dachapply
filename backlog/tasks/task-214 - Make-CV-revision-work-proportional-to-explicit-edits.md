---
id: TASK-214
title: Make CV revision work proportional to explicit edits
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-02 07:38'
updated_date: '2026-09-02 08:03'
labels:
  - backend
  - cv
  - performance
dependencies: []
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: high
ordinal: 213000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Specific one-line CV changes currently pay the same full-document model cost as broad semantic revisions, and revision outputs are excluded from the existing package cache. Add a conservative exact OLD:/NEW: edit route that changes only uniquely matched text and compiles without AI, plus content-addressed caching for repeated semantic revisions; ambiguous instructions must keep the existing AI fallback.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 One or more single-line OLD:/NEW: replacements that each match exactly once bypass the model and preserve all other TeX bytes
- [ ] #2 An already-applied exact replacement returns the current artifacts without model or compiler invocation
- [ ] #3 Ambiguous, missing, multiline, or non-replacement instructions continue through the existing AI revision path
- [ ] #4 Correction-image revisions always continue through the AI revision path
- [ ] #5 Identical semantic revisions can reuse a cache keyed by owner, current source bytes, normalized instructions, correction image, job/profile, and model settings
- [ ] #6 Exact replacements compile only selected changed documents and preserve current artifacts if compilation fails
- [ ] #7 Focused tests prove routing, byte preservation, cache invalidation, owner scoping, and no-model behavior
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Parse only single-line OLD:/NEW: pairs; route only when every old value has one unique owner-scoped source match, and treat already-present new values as no-op. 2. Extend the compile task with atomic source-text updates so exact edits bypass AI, compile selected changed documents, and do not touch current artifacts until all checks pass. 3. Enable content-addressed revision package caching with normalized instructions/correction bytes and a post-output alias so exact retries hit; retain the AI path for every ambiguous instruction or image. 4. Add focused parser/routing/atomicity/cache/ownership regressions, run full gates, measure release, and close.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented the layered route. Exact single-line OLD:/NEW: pairs are accepted only when every OLD has one unique owner-scoped match; plain ampersands map safely to LaTeX, CRLF/LF bytes outside replacements are retained, already-applied pairs return the current artifacts, and all ambiguous/multiline/image requests fall back to AI. Exact edits compile atomically and skip unchanged selected documents. Semantic revisions now use the existing content cache with normalized instructions/image bytes and an output-source alias, so exact retries avoid a second model call; owner/source/job/profile/model/image changes invalidate. Added an inline format hint. Verification: 7 focused tests, 28 CV/evidence tests, 1,053 full backend tests, 206 frontend tests/build, Django/migration checks, compileall, diff check, and npm audit 0 passed.
<!-- SECTION:NOTES:END -->
