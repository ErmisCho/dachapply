---
id: TASK-409
title: Copy a letter as plain text
status: Done
assignee: []
created_date: '2026-11-24 12:47'
updated_date: '2026-11-24 12:58'
labels: []
dependencies: []
priority: high
ordinal: 414000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision 2026-11-24: application forms need the letter as plain text. The owner asked for it in the Adjust box (job 2095, 2026-11-23), which cannot work because letters must stay LaTeX. A copy button without AI; the LaTeX letter stays as it is.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Beside Copy TeX, in the generator and each bulk row, Copy text copies the letters and short messages ticked for Copy as plain text: greeting, paragraphs, closing and name; no addresses, date, subject or LaTeX
- [x] #2 CVs ticked for Copy are left out; with no letter or message ticked the button is off and says why
- [x] #3 Umlauts, escaped characters, quotes, dashes, links, bold and lists read correctly; nothing between greeting and closing is lost; checked on every real letter on this PC
- [x] #4 A letter whose greeting or closing is not found is not cut silently: the copy says so
- [x] #5 No file is written and no model is called; the server accepts only the job's own documents
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Checked on all 96 real letters on this PC 2026-11-24: 0 not delimited, 0 leftover LaTeX marks, 0 word differences.

PR #450 (36f35f0), CI green. Codex finding declined: none of the 96 real letters has text after the name, and cutting could lose a postscript. Verified in the owner's signed-in Chrome on localhost, job 2087.
<!-- SECTION:NOTES:END -->
