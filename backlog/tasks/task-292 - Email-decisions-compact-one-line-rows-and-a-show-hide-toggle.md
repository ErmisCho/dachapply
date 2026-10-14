---
id: TASK-292
title: 'Email decisions: compact one-line rows and a show/hide toggle'
status: In Progress
assignee: []
created_date: '2026-10-14 09:01'
updated_date: '2026-10-14 12:48'
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
- [x] #1 Each email decision renders as one line (company, role, sender, what is suggested) and expands to the full card on click
- [x] #2 A toggle hides/shows the Email decisions section; the choice survives a reload
- [ ] #3 Verified in the browser at desktop and phone width; vitest and tsc pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14: #251 + #252 (row contrast fix). Localhost: one-line rows expand to the conversation; Hide survives reload. Open: phone width.
<!-- SECTION:NOTES:END -->
