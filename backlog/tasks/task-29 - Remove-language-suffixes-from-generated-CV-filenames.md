---
id: TASK-29
title: Remove language suffixes from generated CV filenames
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:41'
updated_date: '2026-07-16 14:49'
labels:
  - backend
  - ux
dependencies:
  - TASK-28
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/tests/test_api.py
priority: low
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Generated CV filenames remain target-specific but do not end with EN, DE, English, German, or another language marker.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Generated CV filenames contain candidate, company, and role identifiers without a language suffix
- [x] #2 Letter filenames also avoid automatic language suffixes
- [x] #3 Collision handling still preserves prior files
- [x] #4 Tests verify English and German filename output
- [x] #5 Generated filenames never include gender markers such as gn or gn*
- [x] #6 Generated filenames use readable title casing and preserve TUV as one uppercase brand token
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Build readable candidate-company-role filenames in the shared target helper, stripping language/gender suffixes, title-casing words, and preserving the TUV brand token in uppercase. Keep collision numbering.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Removed language markers from the shared CV and letter target-name helper. Existing collision-safe persistence remains unchanged. Validation passed: English/German naming regression test, collision/persistence generation test, Django check, and git diff check.

Follow-up: strip gn/gn* gender markers from the shared target filename and clean existing generated TÜV files.

The shared target-name helper now strips trailing gn/gn* and slash-style gender markers before slugging CV and letter filenames. Renamed the four existing TÜV Machine Learning Engineer CV TeX/PDF versions to remove gn while preserving version numbers and verified file types. Two focused tests, Django check, and whitespace check passed.

Follow-up: filename casing should be Chorinopoulos-Ermis-CV-TUV-Austria-Machine-Learning-Engineer, including normalization of TÜV/T�V to TUV.

Generated target names now title-case company/role words and normalize TÜV or corrupted T�V to the single uppercase token TUV. The existing TÜV CV pair was case-renamed to Chorinopoulos-Ermis-CV-TUV-Austria-Machine-Learning-Engineer.tex/.pdf. Restart lookup retains lowercase legacy fallback. Three focused tests, Django check, and whitespace check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Generated filenames are readable title case, omit language/gender markers, and preserve TUV as an uppercase brand token; existing TÜV files were renamed.
<!-- SECTION:FINAL_SUMMARY:END -->
