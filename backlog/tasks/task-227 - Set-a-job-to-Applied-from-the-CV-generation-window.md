---
id: TASK-227
title: Set a job to Applied from the CV generation window
status: To Do
assignee: []
created_date: '2026-09-10 11:49'
labels:
  - frontend
  - backend
dependencies: []
priority: high
ordinal: 226000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request, 2026-09-10: from the CV generation window, be able to change the status to Applied.

Generating the documents is the moment the application happens, but the window has no way to record it. Its controls today are Provider, Model, Effort, Speed, Detected language, Create CV, Create motivation letter, Adjust latest generated files, Copy generated TeX files, the generation report (Main changes / Changed files / Checks / Not claimed) and Close - the whole popup is App.tsx line 587. Marking the job Applied means leaving the window for the board or the job detail page, which is exactly when it gets forgotten.

The backend already does the right thing once the status is set: JobLead.save (models.py:274) stamps applied_at from status_date or today the first time status becomes `applied`, and `applied` is one of DATED_STATUSES, so it carries a status_date and can go stale. So this is about reaching that from the window, not about new status behaviour.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A control in the CV generation window sets the job status to Applied without leaving the window
- [ ] #2 The change is persisted, not just optimistic: after a full page reload the job still reads Applied, and applied_at is stamped exactly as the board own status change stamps it
- [ ] #3 The control reflects the job current status rather than offering the same action twice - a job already Applied shows that instead of an active Apply button
- [ ] #4 The board row behind the window reflects the new status without a manual refresh
- [ ] #5 Frontend tests cover the control, and it is verified in the served bundle at localhost:8000 after `cd frontend && npm run build` - a passing test alone does not close this
<!-- AC:END -->
