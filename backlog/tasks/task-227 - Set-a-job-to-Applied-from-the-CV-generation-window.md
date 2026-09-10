---
id: TASK-227
title: Set a job to Applied from the CV generation window
status: In Progress
assignee: []
created_date: '2026-09-10 11:49'
updated_date: '2026-09-10 21:33'
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
- [x] #1 A control in the CV generation window sets the job status to Applied without leaving the window
- [x] #2 The change is persisted, not just optimistic: after a full page reload the job still reads Applied, and applied_at is stamped exactly as the board own status change stamps it
- [x] #3 The control reflects the job current status rather than offering the same action twice - a job already Applied shows that instead of an active Apply button
- [ ] #4 The board row behind the window reflects the new status without a manual refresh
- [ ] #5 Frontend tests cover the control, and it is verified in the served bundle at localhost:8000 after `cd frontend && npm run build` - a passing test alone does not close this
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Branch `task-227-228-cv-window`, shipped with TASK-228 because both edit the same component. Sealed
rubric at `.claude/.asian-dad/task-227-rubric.json` (gitignored, written before implementation).

## What was built

`CvGenerator` (App.tsx:587) is ONE component in two modes -- `compact` (the board popup, App.tsx:533)
and full (the job detail section, App.tsx:639) -- so the control appears on both surfaces from one
change.

The control does **not** introduce a second way to write a status. `feedbackStatusPatch(status, today)`
already existed at App.tsx:267 and is exactly what the board own `bulkApply` builds; the new handler
calls it. That is the whole reason AC2 can be true: if the two paths built their own bodies they would
drift, and one of them would eventually write a job the other would have written differently.

The backend needed no change. `JobLead.save` stamps `applied_at` on the first transition to
`applied` (models.py:274).

## AC1, AC2, AC3 -- verified end to end against the real database

Driven through the app on job 1467, provider path untouched:

    PATCH /api/jobs/1467/ HTTP/1.1  200
    status=applied  applied_at=2026-09-10  status_date=2026-09-10  last_update_date=2026-09-10
    interview_stage=None  interview_total=None

- **AC1** the window stayed open and rendered throughout; nothing navigated.
- **AC2** that is the board body exactly, `applied_at` stamped by the backend, and it still read
  Applied after a **full page reload**.
- **AC3** after the write the button was gone, replaced by a non-interactive "Applied" state, so the
  same write cannot fire twice.

The job was restored to its recorded pre-test state afterwards (`status=new`, all four date fields
`None`) -- it is the owner real data, not a fixture.

## AC4 and AC5 -- NOT checked, and why

- **AC4 (board row updates without a refresh).** The wiring exists: the board passes `onJobUpdated`
  and replaces the row in `jobs` state. It is **not measured**, because the popup only appears when
  exactly one board row is selected and the board selection is a drag-select rig that neither
  synthetic events nor a calibrated real click could drive in this session. The detail-page surface
  was used for everything above instead.
- **AC5 (verified in the served bundle at localhost:8000).** `cd frontend && npm run build` in the
  owner checkout succeeded (`index-B6BgHVW-.js`), but **localhost:8000 does not serve this checkout**
  -- see the note in TASK-228. Frontend tests do pass: 241, up from 237.

Neither is a defect found; both are verification this session could not complete. They close by
loading the board after merge.
<!-- SECTION:NOTES:END -->
