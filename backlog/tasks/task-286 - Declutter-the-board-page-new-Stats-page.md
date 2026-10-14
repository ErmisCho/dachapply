---
id: TASK-286
title: Declutter the board page; new Stats page
status: To Do
assignee: []
created_date: '2026-10-14 07:56'
labels: []
dependencies: []
ordinal: 287000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-14): the board page is cluttered (~2,800 px of panels above the table). Source effectiveness (49 sources with 1-3 applications each) and Funnel stalls add no value. The 90-day funnel and the 'Weeks this month' chart move to a new Stats page. Empty panels and the big hero banner waste space. The Active interviews and Due follow-ups tiles should show briefly which jobs: company, title, stage.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Source effectiveness and Funnel stalls panels are gone from the board and from the Panels menu; any backend stats fields used only by them are removed with their tests
- [ ] #2 A Stats page (nav link 'Stats', route /stats) shows the last-90-days funnel and the 'Weeks this month' chart; the board keeps only the all-time funnel and the workday chart
- [ ] #3 Email decisions and Upcoming interviews panels take no space on the board when they have nothing to show
- [ ] #4 The 'Job command center' banner is a slim bar: title and its existing buttons, no tagline
- [ ] #5 Active interviews and Due follow-ups tiles list each job: company, title and stage (interview round x/y; follow-up: status and due date), each linking to the job
- [ ] #6 A saved panel order or hidden-panel list in localStorage that still names removed panels loads without errors
- [ ] #7 Verified in the browser on localhost with the owner's data, desktop and phone width
- [ ] #8 vitest, tsc and the backend suite pass
<!-- AC:END -->
