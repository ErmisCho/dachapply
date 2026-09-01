---
id: TASK-209
title: Suppress follow-up reminders while an interview is still upcoming
status: Done
assignee:
  - '@pi'
created_date: '2026-08-31 13:50'
updated_date: '2026-09-01 09:18'
labels:
  - backend
  - frontend
  - followups
  - interview
dependencies: []
priority: high
type: bug
ordinal: 208000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A Vienna Insurance Group lead with an interview scheduled for Thursday still appears in Feedback deadlines as if a follow-up date were knowable. An upcoming interview supersedes any earlier feedback/follow-up reminder: hide that reminder until the interview has happened, without deleting or silently rewriting the stored dates.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A lead with a future scheduled interview does not appear in the Feedback deadlines pane or count/digest as due for a superseded follow-up
- [x] #2 Automatic suppression does not rewrite dates; the exact reported VIG deadline is cleared under an exact guard because the owner says it is unknowable, without fabricating an interview time
- [x] #3 Once the interview time has passed, any still-applicable stored reminder becomes eligible again under the normal date rules
- [x] #4 Boundary behavior uses aware configured-timezone timestamps and does not suppress a lead whose interview has no scheduled time
- [x] #5 The lead remains visible in normal job and upcoming-interview surfaces; synthetic regressions cover future, equal/past, null, no-mutation, and measured-case behavior without external calls
- [x] #6 The Feedback deadlines pane has a compact accessible button that independently shows or hides its Today and upcoming deadline rows, keeps overdue visibility unchanged, and remembers the owner's choice
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve read-only measured evidence and the sealed rubric supersession: the reported lead has no structured interview time, so no time will be guessed. 2. Exclude future interview_at jobs at the feedback-due, due-followup stats, digest, and job-detail action boundaries while keeping strict equal/past/null behavior. 3. Add synthetic timezone/boundary/no-mutation/visibility regressions. 4. Under an exact owner-authorized guard, clear only the reported VIG feedback_due_date because the owner says that deadline is not knowable; leave interview_at unset. 5. Run full gates, evaluate, merge, verify deployment/runtime and the measured row, then close.

6. Add a minimal persisted Show/Hide upcoming control to the Feedback deadlines pane and cover its independent filtering behavior in frontend regressions.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause: .orchestrator/debug/task-209-2026-08-31-bugfix-1-1.md. Released read-only measurement found one VIG row, status interview, feedback due 2026-09-09, but interview_at null, no open FollowUp, no matched mailbox message, and no pending interview suggestion; 0 writes/external calls.

User expanded TASK-209 to include a minimal polished show/hide button for the pane's Today and upcoming deadline rows.

Implemented strict future-interview suppression across feedback-due, stats, digest/reconciliation, confirmation, and job-detail actions. Cleared only VIG feedback_due_date under the exact measured guard; left status/interview_at unchanged and made zero Gmail calls. Added the persisted compact Hide/Show upcoming button plus independent group filtering. Focused checks: 23 backend tests and 157 frontend tests; full checks: 1,044 backend and 202 frontend tests, build, Django checks, compileall, npm audit, diff/no-send scan. Browser harness verified the pause notice and zero sent-action buttons.

Browser verification on the real branch Dashboard with synthetic demo data measured 5 rows shown, 1 overdue row retained when upcoming was hidden, and 5 restored; aria-pressed and localStorage changed true→false→true, and a Dashboard remount initialized from stored false. Disclosed self-graded Asian Dad evaluation: PERFECT (6/6).

PR #112 squash-merged as 795996ca7074cd42f81958b48f08a9d6db6d2ce7. Main CI/deployment run 33489845881 passed. Deployed HTTPS browser verification measured 5→1 overdue-only→5 rows; stored false survived an authenticated reload. Dedicated local runtime is clean at the same SHA with API/root/Vite HTTP 200. Released VIG remains interview with feedback_due_date/interview_at null.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @pi
created: 2026-09-01 08:32
---
Scope added at owner request: a compact, persisted upcoming-row toggle in Feedback deadlines.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Paused reminders only while a structured interview timestamp is strictly future across feedback deadlines, stats, digest/reconciliation, confirmation, and job actions. Added a persisted minimal upcoming-row toggle that leaves overdue rows independent. Cleared only the owner's reported invalid VIG deadline without fabricating an interview time. Verified by 1,044 backend tests, 202 frontend tests, focused boundary tests, build/audit/checks, synthetic and deployed browser interactions, guarded production measurement, CI/deployment run 33489845881, and local runtime parity at 795996c; self-graded Asian Dad verdict PERFECT.
<!-- SECTION:FINAL_SUMMARY:END -->
