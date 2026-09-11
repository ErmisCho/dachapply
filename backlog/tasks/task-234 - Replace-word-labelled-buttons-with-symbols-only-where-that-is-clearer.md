---
id: TASK-234
title: Replace word-labelled buttons with symbols only where that is clearer
status: To Do
assignee: []
created_date: '2026-09-11 11:23'
labels:
  - frontend
dependencies:
  - TASK-230
priority: medium
ordinal: 233000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-09-11: find the buttons described with words that could be symbols instead, for a more minimalistic but also more intuitive popup.

Measured inventory first, because the obvious candidates turn out to be done already. In the popup with every section open:

    ALREADY icon-only (40px, label lives in aria-label):
      Copy full path for CV TeX / CV PDF / Letter TeX / Base CV template   4 buttons

    word-labelled, with their rendered widths:
      Generate                    76 px
      Readjust and compile       145 px
      Recompile saved PDFs       149 px
      Copy generated TeX files   163 px
    plus, in the compact popup only: Close, Mark applied, and Cancel generation while a run is active.

So the copy-path controls are not the problem - they are already symbols. The width is in three long labels sitting in one row, 457px of it inside a 608px popup, which is what makes that row read as crowded.

The rule this should follow, because "more minimalistic" and "more intuitive" pull against each other: **an icon alone is safe only where the symbol is universal and the action is recoverable.** Close and copy qualify - everyone knows them and nothing is lost by a misclick. Readjust and compile versus Recompile saved PDFs do NOT: they are already easy to confuse with words, and two similar glyphs would make that worse. Mark applied changes a job status and would be a guess as an icon. Generate is the primary action and should stay a word.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every button that becomes icon-only has an accessible name (aria-label or equivalent) and a tooltip, so the action is discoverable without clicking it
- [ ] #2 No button whose action is destructive, ambiguous, or a state change keeps its meaning only in a glyph - that list includes Mark applied and the two compile actions, and any exception is argued in the task rather than assumed
- [ ] #3 The measured width of the button row goes down, stated in pixels before and after for the same job and viewport
- [ ] #4 Icons come from one set at one stroke weight and optical size - a glyph, an ASCII mark and a pictogram mixed together is what this task exists to remove
- [ ] #5 Keyboard operation and focus order are unchanged, and the icon-only controls are still reachable and announced
- [ ] #6 Frontend tests cover the accessible names, and the result is verified in the served bundle at localhost:8000
<!-- AC:END -->
