---
id: TASK-304
title: Generated CVs keep the photo from the base CV
status: Done
assignee: []
created_date: '2026-10-16 14:06'
updated_date: '2026-10-17 09:35'
labels: []
dependencies: []
ordinal: 305000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-10-16: the GPT-6.1-Sol Wienerberger CV has no \includegraphics (143 KB PDF vs ~1.36 MB for others): the model dropped the photo. The base CV template has one, and nothing checks it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Generation fails validation (with a specific reason passed to the repair attempt) when the base CV has a photo and the generated CV does not
- [x] #2 Readjustments keep the photo the same way
- [x] #3 Tests cover dropped photo -> repaired, and a base CV without photo is not affected
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified 2026-10-16: the photo check runs in generate_cv_package (cv_generator.py:2047), which also handles readjustments. Real CVs generated after #279/#280 (Ratbacher, EY, Sportradar) all keep \includegraphics. Test: test_cv_photo.py.
<!-- SECTION:NOTES:END -->
