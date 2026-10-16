---
id: TASK-300
title: Generated file names drop the company's legal form
status: Done
assignee: []
created_date: '2026-10-16 06:43'
updated_date: '2026-10-16 07:50'
labels: []
dependencies: []
ordinal: 301000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-16): the Wienerberger letter was named ...-Wienerberger-Ag-AI-Solutions-Engineer.tex; 'AG' (and GmbH, SE, Inc. etc.) should not end up in file names, and capitalisation must not turn AG into Ag.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 File names for CVs, letters and short messages omit legal forms (AG, GmbH, SE, KG, OG, e.U., Inc., Ltd., LLC, S.A., B.V. ...) from the company part
- [x] #2 Existing files are not renamed
- [x] #3 Tests cover the common legal forms and a company whose name contains such letters inside a word
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-16: #275. 21 company cases tested; existing files keep their names and are still found.
<!-- SECTION:NOTES:END -->
