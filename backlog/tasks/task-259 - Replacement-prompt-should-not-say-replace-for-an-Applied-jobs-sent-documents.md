---
id: TASK-259
title: Replacement prompt should not say replace for an Applied job's sent documents
status: Done
assignee: []
created_date: '2026-10-01 20:44'
updated_date: '2026-10-01 21:26'
labels:
  - backend
  - ux
dependencies: []
priority: low
ordinal: 257000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-256. Generating for a job whose existing files are the read-only documents of an Applied job returns 409 'Generated files already exist for this job. Confirm replacement before generating.' Since TASK-256, confirming writes new suffixed files and never replaces the sent ones, so the prompt misdescribes what happens.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 When a job's existing files are its sent (Applied, read-only) documents, the 409 and the confirmation the user sees say new copies will be created and the sent documents kept, not that they will be replaced
- [x] #2 For a non-Applied job with ordinary generated files the existing replacement wording and behaviour are unchanged
- [x] #3 The API response tells the client which case applies with a field, not by parsing the message text
- [x] #4 Backend test covers both cases; frontend test or typecheck covers the client handling, and the built bundle renders on localhost
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Backend (`backend/jobradar/views.py` `generate_cv_documents`): the existing-files 409 now carries `sent_documents`. It is true only when every selected existing file is a sent document (`_sent_paths`/`_is_sent` imported read-only from cv_generator; cv_generator.py not edited). A selection mixing a sent file with an ordinary one keeps the replacement wording, because the ordinary file really is replaced.
- Sent: `These are the documents this job was sent with. Generating creates new copies and keeps the sent documents unchanged.` with `existing_files: true, sent_documents: true`.
- Otherwise: the same detail as before, plus `sent_documents: false`.

Client (`frontend/src/App.tsx` single-job `generate`, `frontend/src/cvModel.ts` `replacementPrompt`): the request goes out unconfirmed first. On a 409 with `existing_files` it confirms with `replacementPrompt(e)`, which branches on `e.sent_documents` and never reads `detail`. Declining sends nothing more and restores the previous task state; accepting resends with `replace_existing: true`. Non-Applied confirm text is unchanged: `Generated files already exist for this job. Recreate them with the selected settings?`. Sent confirm text: `These are the documents this job was sent with. Generate new copies with the selected settings? The sent documents stay unchanged.`

Tests: two backend tests in test_api.py that use real generated files (ordinary files, and the same files after the job is marked Applied) and assert the full 409 body and that confirming starts the task. Both FAIL with the views.py change reverted. Two frontend tests in cvPopup.test.tsx replace the old pre-confirm assertion; each FAILs when its fix is reverted. Gates: backend `1251 passed`; frontend `tsc --noEmit` clean, `308 passed`.

Not verified: AC4's localhost render. The agent had no browser, so the coordinator must check it.

Bulk generator (the second `generate` in App.tsx, line 657): same pattern. Each job is sent unconfirmed. A job whose 409 has `existing_files` gets its own confirm, `<company> — <title>: ` + `replacementPrompt(e)`, so sent and ordinary jobs are worded separately. Declining restores that row. The old shared client-side pre-check ("Recreate them" for one or more selected jobs) is removed; it could not tell sent documents apart. A cvPopup test covers this path and FAILs with only the bulk `generate` reverted.

Removed dead code: `replacementDecision` and `hasSelectedGeneratedFiles` (cvModel.ts) had no callers left. Their cvSelection tests were deleted; the letter-type separation those tests exercised is now asserted on `selectedGeneratedArtifacts` directly. Frontend gates after this: `tsc --noEmit` clean, `308 passed`.

Coordinator 2026-10-01: merged as #202 (c9b65b2), deploy green, production /api/health/ 200, production bundle index-BjuIhHEU.js contains the new sent-documents wording. Localhost runtime moved to c9b65b2, served bundle hash equals frontend/dist/index.html, board rendered (root mounted, title 'Board — DACHApply').
<!-- SECTION:NOTES:END -->
