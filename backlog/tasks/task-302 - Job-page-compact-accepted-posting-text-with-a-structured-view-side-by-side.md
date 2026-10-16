---
id: TASK-302
title: 'Job page: compact accepted posting text with a structured view side by side'
status: To Do
assignee: []
created_date: '2026-10-16 06:44'
labels: []
dependencies: []
ordinal: 303000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-16): the 'Current accepted text' box is too big; a structured version of the posting (responsibilities, requirements, nice to have, benefits, ...) should sit side by side like before. The structured-view code still exists in App.tsx (found 2026-10-16), so check why it no longer shows (data missing for new jobs? layout?) before building anything.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The accepted text box is compact (bounded height, scrolls) on the job page
- [ ] #2 A structured version (responsibilities, requirements, nice to have, other sections present) shows side by side on desktop and stacked on phone
- [ ] #3 Root cause of the missing structured view is stated in the task notes
- [ ] #4 Verified on Wienerberger and one older job in the browser; vitest and tsc pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause (2026-10-16): there was no structured-view component to restore -- App.tsx has no Responsibilities/structured posting renderer (only the evaluation's skill lists), and git history has none either. The "structured version" the owner remembers was the accepted text itself: the TASK-260 ChatGPT extract (Overview / Required experience / Preferred qualifications / Tasks / responsibilities / Pay / Location / Other details) is written to original_source_text only when the job has no meaningful text yet (json_importer.py ~L226, job_replace.py ~L55). Jobs whose posting text was fetched or pasted first (intake fetch, TASK-254 fetch before generation, TASK-255/269 adopt-fetched) keep the raw page text, so the extract is discarded and nothing structured is stored. Fix: the job page derives the sections from headings in the accepted text (appUtils.postingSections, TASK-260 headings plus common EN/DE ones) and shows them beside a height-bounded accepted-text box; text without recognisable headings shows "No structured version yet".
<!-- SECTION:NOTES:END -->
