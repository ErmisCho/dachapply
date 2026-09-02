---
id: TASK-215
title: Handle multiline CV replacements without AI or Windows cleanup failures
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-02 08:18'
updated_date: '2026-09-02 08:37'
labels:
  - backend
  - cv
  - performance
  - windows
dependencies: []
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: high
ordinal: 214000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-214 intentionally accepts only single-line OLD:/NEW: pairs, so explicit multiline LaTeX blocks and bounded ellipsis replacements still launch the full model workflow. The reported Salesforce request then displayed WinError 32 even though its TeX and two-page PDF had already been saved, consistent with Windows temporary-directory cleanup encountering a lingering process handle. Extend the conservative exact route to unique multiline blocks and bounded ellipsis, and do not turn successful saved output into failure solely because disposable temp cleanup is locked.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Unique multiline OLD:/NEW: blocks bypass AI and preserve all bytes outside the matched block
- [ ] #2 A line containing only ... in OLD acts as a non-greedy bounded wildcard between exact prefix and suffix, and only one document match is accepted
- [ ] #3 Already-applied multiline or wildcard replacements return current artifacts without model or compiler invocation
- [ ] #4 Ambiguous or unbounded wildcard blocks continue through AI fallback
- [ ] #5 A Windows lock during disposable generation/compile temp cleanup does not convert successfully persisted artifacts into a failed task
- [ ] #6 The supplied Salesforce header and certification request is recognized as already applied, returns immediately, and the existing PDF remains two pages
- [ ] #7 Focused and full regression gates pass without model or Gmail calls
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Generalize exact OLD/NEW parsing to preserve multiline blocks and detect explicit numbered/directive boundaries. 2. Support only bounded, line-only ellipsis wildcards, require one unique source match, and treat exact NEW content as already applied. 3. Ignore only disposable temp cleanup errors after child work completes; preserve all generation/compile/persistence errors. 4. Verify the supplied Salesforce prompt as a zero-work two-page result, run full gates, release, and close.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause confirmed: TASK-214 rejected every multiline block, forcing AI; the reported TeX and two-page PDF had both persisted before WinError 32 surfaced, isolating the visible failure to disposable temp cleanup. Implemented unique multiline OLD/NEW and Replace-from/with blocks, one bounded line-only ellipsis wildcard, already-applied detection, and AI fallback for ambiguous/unbounded inputs. Both generation and compile workspaces now use stdlib cleanup-lock tolerance only at context cleanup. The exact supplied Salesforce request measured 0.67ms in parsing, returned already applied, made 0 model/compiler calls, and the PDF remains 2 pages. Focused backend tests and 206 frontend tests/build passed.

Full verification completed: 1,054 backend tests passed; Django check and migration check passed; 206 frontend tests and production build passed; compileall and diff check passed; npm audit reports 0 vulnerabilities. Automated tests use synthetic blocks and no external model/Gmail transport.
<!-- SECTION:NOTES:END -->
