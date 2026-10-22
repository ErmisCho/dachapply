---
id: TASK-333
title: Exact OLD/NEW blocks stop at instruction headings
status: Done
assignee: []
created_date: '2026-10-21 15:35'
updated_date: '2026-10-22 13:26'
labels:
  - backend
dependencies: []
priority: high
ordinal: 333000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-21: a Sportradar Adjust with 10 OLD/NEW blocks failed 'LaTeX could not compile the CV: LaTeX Error: Missing \begin{document} (line 61)'; 'make sure this error doesn't happen again'. Cause (from the owner's pasted instructions): cv_generator.exact_revision_plan ends a NEW block only at OLD:/FROM:, a numbered line, or keep/do not/submit/constraint. The heading 'CHANGE 2 — Restore normal project heading font size' after the first NEW block was therefore part of it and was spliced into the CV preamble (line 61 starts with 'C'); 'FILE 2: ...' and 'FINAL VALIDATION:' likewise, the last one into the letter body where it would compile as visible junk.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A NEW block ends at a heading line after a blank line: CHANGE/FILE/STEP/EDIT/FINAL/VALIDATION/NOTE lines, or a short line ending with ':' that has no LaTeX characters
- [x] #2 Blank lines inside a NEW block (e.g. between two LaTeX items) and prose paragraphs of letter text are kept
- [x] #3 The owner's 10-block Sportradar instruction (structure reproduced in a test) yields 10 clean pairs with no heading text
- [x] #4 Applied to the real Sportradar files, the edits compile: CV 2 pages, letter 1 page
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #333. Owner instruction on the real Sportradar files: old parser leaked 8 heading lines into the CV and 3 into the letter; fixed parser none; then applied live via revise-latest at 18:19: all 10 edits, CV 2 pages, letter 1 page.
<!-- SECTION:NOTES:END -->
