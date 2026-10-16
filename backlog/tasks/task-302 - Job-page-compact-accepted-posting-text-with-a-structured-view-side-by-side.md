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
