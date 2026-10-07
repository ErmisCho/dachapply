---
id: TASK-269
title: Make it obvious that a fetched posting copy must be chosen before Generate
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

Owner changed the decision 2026-10-07 after seeing the first version: "make it obvious that i ned to first decide between versions and then I caan generate". The lock stays; the decision is made obvious at Generate. The dismissed-copy suppression stays so imported jobs do not re-lock daily. AC1-AC3 below were reworded through this decision (rubric supersession recorded).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 With a pending fetched copy, Generate is disabled, and the reason plus inline Keep current / Use fetched buttons are visible directly under Generate, in the same viewport; after a choice Generate enables without a reload
- [x] #2 The disabled Generate names the required step (title + aria-describedby to the step box)
- [x] #3 Bulk generator and backend agree: a job with a pending copy cannot be generated (409 server-side), and the bulk dialog marks which job needs a choice and how many
- [x] #4 After Keep current, the next automatic refresh that fetches the same website text does not stage it again; a differing website text is staged
- [x] #5 Use fetched and manual Fetch/Refetch keep working; a choice made in the CV generator or in the job page's Original job text section updates the other without a reload
- [x] #6 Tests cover the lock, the step box, re-staging suppression; vitest and tsc green; verified in a browser
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Cause: since TASK-260 the accepted text is a ChatGPT extract that never equals the website, so every automatic refresh staged a pending copy. The Keep current / Use fetched choice sat below the fold, with nothing at Generate saying why it was greyed out.
- Step box `#cv-text-choice-<id>` directly under Generate: "Step 1: choose the job text", "The website text changed. Pick which version to use, then Generate unlocks.", inline Keep current / Use fetched (same saveGenerationJob path as PostingSource) and Compare versions (scrolls to and focuses the fetched textarea). Generate has title "Choose a job text version first" and aria-describedby pointing at the box. The backend 409 message is now "Choose which job text to use (Keep current or Use fetched) before generating."
- Bulk: a row with a pending copy shows "Choose job text first" (opens that row's Source text); the batch button title and a status line give the count.
- Sync (found in browser verification): the job page's CvGenerator had no onJobUpdated, so a choice there left the Original job text banner and the calibration lock stale until reload. It now merges the update into the page, and CvGenerator clears its pending copy when the job reports has_pending_source false.
- Re-staging: `JobLead.dismissed_source_hash` (migration 0056, AddField). The source-text PATCH stores the sha256 of the normalized pending copy it resolves; the automatic refresh skips a fetched text with that hash. A manual Fetch always stages a differing copy.
- Verified in headless Chrome, 1366x768, scratch server built from the branch:
  - Before: Generate disabled with the title set, the box visible, Generate top 369 and box bottom 543 in a 768 viewport.
  - Real click on Keep current: Generate enabled and the box gone. The API shows has_pending_source false and the hash stored.
  - Choosing in either section clears the other section's banner and unlocks calibration.
  - Bulk dialog: batch disabled, title "Choose a job text version for 1 job first", 1 row marker, line "1 job needs a job text choice before generating".
- Tests:
  - test_posting_fetch.py: 30 passed (with test_bulk_clipboard).
  - vitest: 340 passed. tsc: clean.
  - Mutation checks: the restage-suppression revert fails 1 test. The UI pins fail when the lock is removed, when Use fetched is miswired, and when the bulk lock or bulk marker is removed.
  - Full local backend: 4 test_api failures. These tests hardcode gpt-5.5, but this machine's ~/.codex/models_cache.json now lists only gpt-5.6-*. They are environmental and not touched by this diff; CI is the gate.
<!-- SECTION:NOTES:END -->
