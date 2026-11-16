---
id: TASK-379
title: 'Prepared documents: choose to prepare just the CV or just the letter'
status: Done
assignee: []
created_date: '2026-11-16 13:24'
updated_date: '2026-11-16 16:16'
labels:
  - frontend
  - backend
dependencies: []
priority: medium
ordinal: 381000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-11-16 (Mavie Med Holding, Data Platform and AI Manager): 'I should be able to generate and adjust just cv or just letter if I choose to.' The Prepared documents panel prepares whatever plan_variants derives from the posting (often a CV only) and offers no way to ask for a letter, or for only one document. Adjust is already per document. The other document's files stay unchanged (owner choice).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 With nothing prepared, the panel offers Prepare CV only and Prepare letter only; each queues only that document's variants (all planned languages), and the server rejects any other documents value with 400
- [x] #2 When a job has no letter variant (e.g. the posting did not ask for one), Prepare letter queues a full letter in the planned languages; likewise Prepare CV when there is no CV variant
- [x] #3 Preparing one document never changes, requeues or deletes the other document's variants or files (ready, queued or running)
- [x] #4 An explicit document request is not blocked by FILES_EXIST (that guard is for automatic drafts only); the automatic path keeps it
- [x] #5 A queued or running variant can be cancelled from the Prepared documents panel without leaving the job page
- [x] #6 Backend tests cover CV-only, letter-only, adding a letter to a CV-only job, and the other document untouched, each red on origin/main and green on the fix; tsc and frontend tests pass; the built bundle on localhost renders the new buttons
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Backend: plan_variants/_gate/prepare take only='cv'|'letter'; POST application-prep/retry/ {only}. An asked letter is a full letter even when the posting wants none; only variants not queued/running/ready (live status) are queued; FILES_EXIST applies to automatic drafts only. The choice is stored as prep.only while the requirements analysis runs (retry_due re-enters prepare without it) and cleared once variants queue. Frontend: Prepare CV / Prepare letter buttons (prepOnly) and a Cancel on queued/running variants (queue/action cancel). Codex review found the two analysis/dead-worker gaps; both fixed with red/green tests. Known limit: a plain Prepare now while a stored choice is pending uses that choice.

Verified on localhost 2026-11-16 (7640567, logged in): job 2063 shows per-document Adjust toggles; choosing one shows "Adjust only this", both shows "Adjust these 2" and the shared box; job 1897 (CV only, status new) shows Prepare letter; the panel shows the new letter rule. No generation was started for the check.
<!-- SECTION:NOTES:END -->
