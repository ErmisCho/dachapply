---
id: TASK-300
title: Generated file names drop the company's legal form
status: To Do
assignee: []
created_date: '2026-10-16 06:43'
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
- [ ] #1 File names for CVs, letters and short messages omit legal forms (AG, GmbH, SE, KG, OG, e.U., Inc., Ltd., LLC, S.A., B.V. ...) from the company part
- [ ] #2 Existing files are not renamed
- [ ] #3 Tests cover the common legal forms and a company whose name contains such letters inside a word
<!-- AC:END -->
