---
id: TASK-42
title: Select one unanalyzed job for prompt generation
status: Done
assignee:
  - '@pi'
created_date: '2026-07-21 11:29'
updated_date: '2026-07-21 11:41'
labels: []
dependencies: []
modified_files:
  - frontend/src/App.tsx
ordinal: 43000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the dashboard hero, hovering or focusing the Analyze N new jobs button lets the user choose one new job without an evaluation for prompt generation. Clicking the main button continues to analyze all new unanalyzed jobs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Hovering or focusing the hero Analyze N new jobs button lists new jobs without evaluations
- [x] #2 Choosing a listed job generates a prompt for only that job
- [x] #3 Clicking the main hero button still analyzes all new unanalyzed jobs
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Keep the fetched new unanalyzed jobs, not only their count.
2. Add the single-job hover/focus menu to the hero Analyze N new jobs button.
3. Revert the menu added to the selected-jobs bulk action and build the frontend.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The screenshot clarified that the target is the dashboard hero Analyze N new jobs button. Dashboard loading now retains the new unanalyzed job rows as well as deriving their count. Hovering or focusing the hero action shows a scrollable list; choosing a row reuses openPrompt with that single ID. Clicking the main button keeps the existing analyze-all behavior. The earlier menu on Analyze selected jobs was removed.

Validation: cd frontend && npm run build; git diff --check; focused source assertions passed.

Follow-up: changed chooser labels from company/title to job ID and URL. Frontend build and diff check passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @pi
created: 2026-07-21 11:35
---
User clarified that the single-job choice belongs on the dashboard Analyze N jobs action, after multi-selecting rows, rather than on the standalone /prompts page.
---

author: @pi
created: 2026-07-21 11:38
---
Screenshot clarified that the target is the hero Analyze N new jobs button, not the selected-jobs bulk action.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added the single-job chooser to Analyze N new jobs; entries are identified by job ID and URL, while the main button still analyzes all.
<!-- SECTION:FINAL_SUMMARY:END -->
