---
id: TASK-60
title: Cache CV packages and remove the 93% compile stall
status: Done
assignee:
  - '@pi'
created_date: '2026-08-13 09:37'
updated_date: '2026-08-13 09:54'
labels:
  - bug
  - cv-generation
  - performance
dependencies: []
modified_files:
  - backend/config/settings.py
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/views.py
  - backend/jobradar/urls.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: high
ordinal: 61000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Generation still stalls indefinitely near 93% because the Windows latexmk/Perl wrapper can remain alive before launching pdflatex. Add the requested saved-work optimizations: reuse unchanged completed packages, use a compact saved evidence snapshot, and compile saved TeX without another model call. Replace the unreliable wrapper path so PDF production completes promptly.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 An unchanged job/template/evidence/model request reuses its saved package without starting a model subprocess
- [x] #2 Routine generation uses a materially smaller saved canonical evidence snapshot while preserving the full evidence source for maintenance
- [x] #3 Existing generated TeX can be recompiled into PDFs without invoking the model
- [x] #4 PDF compilation no longer depends on the hanging latexmk/Perl wrapper and remains cancellable
- [x] #5 Focused backend tests, full backend suite, frontend production build, and a live two-job run pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Replace latexmk with two direct cancellable pdflatex passes and validate the live 93% stall disappears. 2. Save an automatically compacted canonical evidence snapshot and use it for routine prompts. 3. Hash all effective inputs and reuse a valid saved package on exact cache hits. 4. Add a compile-only async endpoint and controls for rebuilding PDFs from latest TeX. 5. Add focused regressions, run full checks, restart localhost, and verify two jobs live.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented all three requested optimizations. Routine evidence is automatically reduced from 105,835 to 33,737 characters (68%) and saved at C:\latex\.dachapply-cache\candidate-evidence-compact.md while the full source remains untouched. Exact effective-input hashes cache ZIPs plus artifact metadata and invalidate when job/evaluation/profile/templates/settings or saved TeX change. Added owner-only async recompile-latest flow and single/batch controls. Replaced the observed hanging latexmk/Perl wrapper with two serialized non-interactive pdflatex passes. Live measurements: existing CV+letter recompiled in 3.55s; two uncached complete jobs reached Ready in 77.87s; exact repeat hit disk cache and both reached Ready in 1.25s. Validation: 5 focused tests and full suite (130 tests), frontend build, Django check, migration check, and diff check passed.

Final local checks: health endpoint reports 200/database ok, the new recompile route is active (owner protection returns 403 unauthenticated), the built bundle contains single and batch Recompile saved PDFs controls, and no Codex/pdflatex/latexmk generation processes remain. The Django autoreloader loaded the new backend at 11:46.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added a persistent exact-input package cache, an automatically maintained compact evidence snapshot, and owner-only async PDF recompilation from saved TeX. Removed the live 93% stall by replacing latexmk/Perl with direct non-interactive pdflatex passes. Live two-job generation took 77.87s uncached and 1.25s cached; recompilation took 3.55s. All 130 backend tests and frontend/Django/migration checks pass.
<!-- SECTION:FINAL_SUMMARY:END -->
