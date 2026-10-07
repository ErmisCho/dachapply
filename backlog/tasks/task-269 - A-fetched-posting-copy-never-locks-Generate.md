---
id: TASK-269
title: A fetched posting copy never locks Generate
status: Done
assignee: []
created_date: '2026-10-07 09:00'
labels:
  - backend
  - ui
dependencies: []
priority: high
ordinal: 266000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-10-07 with screenshot: on a job page (Accenture) the Generate CV button is greyed out with no explanation. The screenshot shows "Refetch posting text", which PostingSource only renders when a freshly fetched posting copy (pending_source_text) is waiting; CvGenerator disables Generate on `!!pendingText`, and the Keep current / Use fetched choice sits below the visible area.

Why it now happens on every imported job: since TASK-260 the accepted text is a structured ChatGPT extract, which never equals the scraped website text. `_stage_source_fetch` stages a pending copy whenever the two differ, and the automatic posting refresh (`refresh_due_job_sources`, daily/weekly) re-stages it on every run, even after the owner chose Keep current.

Owner decision 2026-10-07 ("Don't lock (Recommended)"): Generate always uses the saved (accepted) text. A newer website copy is shown as a note the owner can review but never blocks generation. A website copy the owner already dismissed is not staged again until the website text actually changes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 With a pending fetched copy on the job, the CV generator's Generate button is enabled (all other conditions met) and a run uses the accepted text, not the pending one
- [x] #2 While a pending copy exists, a visible note next to Generate says a newer posting text was fetched and lets the owner jump to or open the Keep current / Use fetched review; no generate action anywhere is disabled solely because a pending copy exists (CV generator, bulk generator, job-page calibration prompt)
- [x] #3 After Keep current, the next automatic refresh that fetches the same website text does not stage it again; a website text that differs from the dismissed one is staged
- [x] #4 Use fetched and manual Fetch/Refetch keep working as before
- [x] #5 Backend tests cover re-staging suppression (same text not restaged, changed text restaged); frontend test pins that pendingText is not a Generate disable condition; full backend suite, vitest and tsc green
- [x] #6 Verified in a browser on a job with a pending copy: Generate is clickable and the note is visible
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Two locks existed: the frontend disabled Generate on `!!pendingText`, and the backend `generate_cv_documents` returned 409 "Review the freshly fetched posting text before generating." Both removed. Generation reads `job.source_text` (accepted text) only; a test asserts the prompt contains the accepted text and not the pending copy.
- Note under Generate: "A newer posting text was fetched. Generate uses the saved job text." with a "Review it" button that scrolls to and focuses the Freshly fetched textarea. The bulk row button reads "Source text · newer copy". The job-page calibration prompt is blocked only when a copy is pending and the textarea has unsaved edits, and no longer silently dismisses the copy. "Save original text" is unchanged (it saves rather than generates).
- Re-staging: new `JobLead.dismissed_source_hash` (migration 0056, AddField only). The source-text PATCH records the sha256 of the normalized pending copy it clears. The automatic refresh skips a fetched text with that hash (state `dismissed`). A changed website text is staged. A manual Fetch/Refetch still always stages a differing copy.
- Verified: headless Chrome at 1366x768 on a scratch server built from the branch, with a pending copy on the job. Generate `disabled:false`, and elementFromPoint at its centre returns Generate. The note is visible. A real click on "Review it" focused "Freshly fetched job text", fully in view (304-464 of 768).
- Tests: test_posting_fetch.py 27 passed (rerun by the coordinator), vitest 340 passed, tsc clean; the agent's full backend run was 1298 passed. Mutation checks: disabling the suppression failed the restage test, and re-adding `!!pendingText` failed 2 vitest tests.
<!-- SECTION:NOTES:END -->
