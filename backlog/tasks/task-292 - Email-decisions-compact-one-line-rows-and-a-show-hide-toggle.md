---
id: TASK-292
title: 'Email decisions: compact one-line rows and a show/hide toggle'
status: To Do
assignee: []
created_date: '2026-10-14 09:01'
labels: []
dependencies: []
ordinal: 293000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-14): Email decisions panels should be small with a concise one-line overview per decision, and the whole Email decisions section needs a toggle to hide/show it for now.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each email decision renders as one line (company, role, sender, what is suggested) and expands to the full card on click
- [ ] #2 A toggle hides/shows the Email decisions section; the choice survives a reload
- [ ] #3 Verified in the browser at desktop and phone width; vitest and tsc pass
<!-- AC:END -->
