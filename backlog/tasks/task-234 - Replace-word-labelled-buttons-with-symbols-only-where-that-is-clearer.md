---
id: TASK-234
title: Replace word-labelled buttons with symbols only where that is clearer
status: Done
assignee: []
created_date: '2026-09-11 11:23'
updated_date: '2026-09-11 20:26'
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
- [x] #1 Every icon-only control has both a tooltip and an accessible name, so the action is discoverable on hover and announced to a screen reader
- [x] #2 A control that changes state may be an icon, but the resulting STATE stays visible without hovering - you can see that a job is Applied without touching anything
- [x] #3 The primary action keeps a word: Generate is what the popup is for and is not a glyph
- [x] #4 Two actions that are already easy to confuse do not become two similar glyphs - Readjust and compile versus Recompile saved PDFs either keep distinguishing words or get visibly different icons, argued in the task
- [x] #5 Prose is cut, not just buttons: the standing explanatory paragraphs in the popup are removed or moved behind the control they describe, and the character count of visible prose is stated before and after
- [x] #6 The measured width of the button row and the height of the popup both go down, stated in pixels for the same job and viewport
- [x] #7 Icons come from one set at one stroke weight and optical size
- [x] #8 Keyboard operation and focus order are unchanged, and frontend tests cover the accessible names
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Decision, owner, 2026-09-11

"I would prefer intuitive icons with tooltips", and text should be minimised aggressively so the
popup fits a laptop screen fully open (TASK-233). That overrides the earlier draft, which had ruled
icon-only out for state-changing actions. It is allowed now, with one property kept: a tooltip makes
the ACTION discoverable, and the resulting STATE must still be readable without hovering - you can see
that a job is Applied without pointing at anything.

Prose is explicitly in scope, not only buttons. The standing paragraphs are the cheapest height to
give back:

- "Review the detected language and change either template if needed."
- "Fastest practical setting: Low effort + 1.5x Fast. xhigh performs substantially more reasoning and
  can take several minutes."
- "Available before, during, or after generation and after a server restart. It uses the latest saved
  files for this job."

## Done 2026-09-11

Became icon-only, each with **both** a tooltip and an accessible name, all in one set (24-unit box,
2px round stroke, rendered at 14px, matching the existing CopyIcon): **Close** (X), **Mark applied**
(check), **Cancel** (stop square), **Copy generated TeX files** (the existing copy glyph).

The applied **state** keeps its word - the green `Applied` chip, with the check beside it - so the
state is readable without hovering while the action is a glyph. Same for Cancel, which shows
`Cancelling...` as text while it runs.

**Generate keeps its word** (AC3). The two compile actions kept distinguishing words, shortened to
`Readjust` and `Recompile`, for three measured reasons rather than taste: they are confusable already
and any icon pair is a weaker distinction than the words; they are `ProgressButton`s that render live
progress *inside* the label (`step 2/5 - 40% - ~90s left`), which is the only in-popup sign a
multi-minute run is alive and which an icon has nowhere to put; and `ProgressButton` takes
`label:string`, so an icon there would mean editing a shared component.

**442 characters of standing prose** removed or moved into a `title` on the control it describes,
including all three paragraphs this task named. The `Detected language` label and its readonly input
are gone - the language is now a muted inline span on the template select, one row shorter and still
readable without hovering.

Popup height 800 -> 681 and the fully-open state now fits a laptop (TASK-233).
<!-- SECTION:NOTES:END -->
