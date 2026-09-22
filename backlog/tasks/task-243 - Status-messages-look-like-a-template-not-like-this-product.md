---
id: TASK-243
title: 'Status messages look like a template, not like this product'
status: To Do
assignee: []
created_date: '2026-09-21 16:30'
labels:
  - frontend
  - ux
dependencies: []
priority: medium
type: enhancement
ordinal: 242000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-09-21, looking at the CV generation window with both a success and an info message showing: it 'seems a bit unpolished and AI generated like'.

Measured rather than guessed. index.css:222-230 gives every status message 1rem/1.1rem padding, a 1rem radius, a gradient background and box-shadow 0 10px 30px rgba(15,23,42,.08); index.css:224 makes the icon a 1.55rem FILLED disc in the tone colour with white glyph and its own coloured glow, box-shadow 0 4px 12px var(--status-glow). The compact variant (index.css:223) trims padding and radius but keeps the glowing disc at full size. Two of these stacked is what the screenshot shows.

The app already contains the quieter pattern it should be matching: .field-error-message (index.css:12-13) is flat - no background, no shadow - with a 1.35rem OUTLINED glyph in currentColor. So this is bringing one surface in line with the house style, not inventing a style.

Scope note, because it is bigger than the screenshot: StatusMessage and SuccessMessage are used 54 times across App.tsx. This is a change to a shared visual primitive, not to the CV window alone, which is why AC4 asks for the other call sites to be checked rather than assumed.

Related: TASK-228 already moved this same window toward 'smaller and calmer'; these banners are the part that did not get the message.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The success and info messages in the CV generation window are visually quieter than today: stated before/after numbers for rendered height and for the icon, measured in the browser at the same width, not adjusted by eye
- [ ] #2 The treatment is consistent with what the app already uses for field errors rather than a second visual language - flat or near-flat, an outlined glyph rather than a filled disc with a coloured glow, and no drop shadow that lifts a one-line message off the page
- [ ] #3 Meaning still survives the quieting: success, info and error remain distinguishable without relying on colour alone, and the role=status / role=alert semantics are unchanged
- [ ] #4 Every one of the 54 existing StatusMessage and SuccessMessage call sites still renders correctly - none left with a broken layout, a missing icon, or text that now collides with its container
- [ ] #5 Dark mode is checked as deliberately as light mode, with the same measurements
- [ ] #6 Verified in the served bundle at localhost:8000 after a rebuild, not only in tests
<!-- AC:END -->
