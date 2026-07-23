---
id: TASK-40.1
title: Edit job and evaluation text from job details
status: Done
assignee:
  - '@pi'
created_date: '2026-07-17 12:29'
updated_date: '2026-07-17 16:25'
labels:
  - frontend
  - backend
dependencies: []
modified_files:
  - frontend/src/App.tsx
  - frontend/src/main.tsx
parent_task_id: TASK-40
priority: medium
ordinal: 41000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owners can correct structured job fields and the latest evaluation's displayed text directly from the job detail page, alongside the existing original-source editor.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Job detail page provides editable company, title, location, URL, salary, and language fields
- [x] #2 Latest evaluation summary, matches, gaps, next action, CV, interview, and risk text are editable
- [x] #3 Saving updates the displayed job and latest evaluation without leaving the page
- [x] #4 Users cannot update evaluations for inaccessible jobs
- [x] #5 Focused API tests and frontend build pass
- [x] #6 Displayed job fields are edited directly where they appear, without a separate collapsed edit form
- [x] #7 Fit score, priority, recommendation, and every evaluation text/list field are editable
- [x] #8 Work mode and status are editable in place
- [x] #9 Inline editors preserve the original detail-card layout and cannot be manually resized
- [x] #10 Evaluation text editors automatically grow to show their complete content without internal scrollbars
- [x] #11 Leaving with unsaved job, evaluation, or source-text edits shows Save all details, Discard changes, and Stay options
- [x] #12 A visible Discard changes button restores the last saved values
- [x] #13 Browser refresh/close warns while detail edits are unsaved
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Track dirty state for inline details and source text, use React Router's native navigation blocker for an in-app three-choice prompt, retain beforeunload for browser exits, and expose save/reset actions from the existing editor.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added a collapsed edit form using the existing job PATCH API and owner-scoped evaluation PATCH. Main matches and gaps use one item per line. Validation: focused API tests passed (2), frontend production build passed, Django check passed, and git diff --check passed. DATABASE_URL was blanked for local Django checks because the repository .env targets PostgreSQL without the optional local driver.

Reopened after clarification: editing must happen directly in the displayed detail cards, and include all job/evaluation values shown there.

Replaced the collapsed duplicate editor and read-only cards with inline controls in the job header and evaluation cards. Added in-place status/work-mode, score/priority/recommendation, and all evaluation list fields. Revalidation: focused API test passed, frontend production build passed, and git diff --check passed.

Reopened to preserve the former card/window dimensions while keeping fields inline.

Restored the compact header/card proportions: primary fields use borderless inline controls, secondary job fields and skill lists are collapsed by default, evaluation textareas use the former compact card heights, and inline textareas cannot be resized. Frontend build and diff check pass.

Reopened from screenshot feedback: card widths/layout should stay fixed, but text fields should grow vertically enough to show their content.

Evaluation textareas now use native content-based sizing: widths/card columns stay unchanged while fields grow vertically to reveal all text and hide internal scrollbars. Frontend build and emitted CSS verification passed.

Reopened to add unsaved-change protection and explicit discard behavior.

Added dirty tracking across inline job/evaluation fields and original source text. Internal navigation is blocked with Save all details, Discard changes, and Stay actions; refresh/close uses the browser's native unsaved-change warning. The visible discard button resets both editor areas. Switched the existing router setup to React Router's data router so native useBlocker can handle back/forward and Link navigation. Frontend production build and diff check pass.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Unsaved edits are now protected: leaving prompts to save, discard, or stay; a page-level Discard changes button restores saved values; refresh/close warns.
<!-- SECTION:FINAL_SUMMARY:END -->
