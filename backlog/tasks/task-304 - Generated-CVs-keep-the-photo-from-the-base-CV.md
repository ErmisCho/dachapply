---
id: TASK-304
title: Generated CVs keep the photo from the base CV
status: In Progress
assignee: []
created_date: '2026-10-16 14:06'
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
- [ ] #1 Generation fails validation (with a specific reason passed to the repair attempt) when the base CV has a photo and the generated CV does not
- [ ] #2 Readjustments keep the photo the same way
- [ ] #3 Tests cover dropped photo -> repaired, and a base CV without photo is not affected
<!-- AC:END -->
