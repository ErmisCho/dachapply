---
id: TASK-266
title: 'Single-job CV popup adapts to window size and zoom, no needless scrollbar'
status: Done
assignee: []
created_date: '2026-10-05 12:30'
updated_date: '2026-10-05 20:10'
labels: []
dependencies: []
priority: medium
ordinal: 264000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner screenshot 2026-10-05: the compact CV generator popup (CvGenerator compact, TASK-216) opened from the board scrolls internally even though the window has room; the accepted-text box also scrolls. Owner: popup should adapt to the window's zoom and size, expand when there is room, look minimal, elegant, practical, intuitive. Owner decision: keep the Applied status toggle but always inline on the action row with Generate, never on a row of its own.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 At 100% and 125% browser zoom on a 1500x870 window, the popup shows its full content without an internal scrollbar when the content fits the viewport (measured: scrollHeight <= clientHeight)
- [x] #2 Popup width and max-height derive from the viewport (e.g. vw/vh or dvh), not fixed px, and it stays fully on-screen at 1024px wide and at 150% zoom (measured getBoundingClientRect inside window)
- [x] #3 Only when content is taller than the viewport does the popup scroll, as a single scroll area (no nested scrollbars on the popup itself)
- [x] #4 Status toggle (Applied) sits on the same row as Generate at all tested sizes; it never wraps onto its own row (measured: same offsetTop)
- [x] #5 Long file paths in Generated files wrap/ellipsize without widening the popup; the accepted job text box grows to the available space instead of a fixed small height
- [x] #6 No horizontal scrollbar in the popup at any tested size; existing cvPopup tests stay green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified 2026-10-05 on a branch server (127.0.0.1:8010, scratch sqlite + scratch CV workspace, real Codex low-effort generation of 2 jobs), viewport 1408x1642 @dpr1.25: popup content-sized, sh=ch (697 before generation, 867 with generated files), sw=cw, Generate/Applied tops 217/221, job-text box grows with content (272/272). AC1-3 at 1500x870 / 150% / 1024px NOT measured: the automated tab is hidden (outerWidth 0) so resizing does not change its viewport; owner to check on localhost:8000 after merge. Bulk dialog also made viewport-relative (owner: 'the pop ups window should adapt') — measured sh=ch.

Grading after #206 found the popup still scrolled once CV+letter existed (1366x768 dialog 808/742 plus textarea 272/94 = nested scroll areas). Fixed in #207: Generated files moved to the empty right column; fitOneScroll lets the textarea grow to its content whenever the dialog must scroll. Measured on merged main (job with CV+letter): 1500x870 no scroll; 1200x696 (125% zoom) and 1024x768 textarea only; 1000x580 (150% zoom of a small screen) dialog only, onScreen=true, no horizontal scroll.
<!-- SECTION:NOTES:END -->
