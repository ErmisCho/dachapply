---
id: TASK-342
title: Generated CVs keep the base CV's layout macros so nothing overlaps
status: To Do
assignee: []
created_date: '2026-10-22 14:15'
labels:
  - backend
dependencies: []
priority: high
ordinal: 342000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-10-22 while verifying TASK-327 on a fresh Comprehentia CV (job 1895): 2 pages, 29 bullets, no forced breaks, but in Selected Projects the first bullet overlaps the project heading's underline. Base v1.5 defines \resumeProjectHeading with \vspace{-7pt} after the tabular and \resumeItemListStart as a plain itemize (default topsep compensates); the model rewrote \resumeItemListStart with topsep=4pt, itemsep=2pt, so the heading and first bullet collide. This is the 'overlapping' the owner reported on 2026-10-21.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A full generation (not an Adjust) replaces every layout macro the base CV defines (\newcommand{\resume...} definitions) with the base definition when the model changed it
- [ ] #2 Adjust/revision runs keep the owner's own macro edits (e.g. \resumeItem -> \normalsize)
- [ ] #3 Regenerated Comprehentia CV: no overlap between project headings and bullets (rendered and inspected), 2 pages
- [ ] #4 Tests cover macro restore with nested braces and the revision exemption
<!-- AC:END -->
