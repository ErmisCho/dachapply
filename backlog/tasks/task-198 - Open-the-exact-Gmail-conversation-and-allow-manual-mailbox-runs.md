---
id: TASK-198
title: Open the exact Gmail conversation and allow manual mailbox runs
status: Done
assignee:
  - '@pi'
created_date: '2026-08-29 16:27'
updated_date: '2026-08-29 21:19'
labels:
  - email
  - backend
  - frontend
  - bug
dependencies: []
priority: high
ordinal: 198000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The per-message Gmail action currently opens an RFC822 search result instead of the actual conversation. The owner also needs an in-app way to run mailbox automation immediately rather than waiting for the scheduler.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each linked captured message with a persisted Gmail thread identifier opens the actual Gmail conversation, not a search results page
- [x] #2 The Gmail conversation link selects the configured owner account and uses one shared URL builder
- [x] #3 The owner can start mailbox automation manually from the application and sees whether it completed, skipped, or failed
- [x] #4 A manual run reuses the existing mailbox automation path and cannot introduce Gmail sending or SMTP capability
- [x] #5 The endpoint and UI are owner-scoped and prevent accidental duplicate submissions while a run is pending
- [x] #6 Automated tests cover direct conversation links and manual mailbox execution without contacting a real mailbox
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reproduce and trace the Gmail URL and run-now visibility paths; record the root cause in .orchestrator/debug. 2. Reuse the single Gmail builder with the persisted thread_id for direct #all conversation links while keeping the RFC822 fallback, and restore the owner-visible run control on no-credential deployments. 3. Add focused backend serializer/builder tests and a DOM-less frontend visibility regression. 4. Run focused and full backend/frontend gates, no-send grep, and Asian Dad evaluation. 5. Commit, push, squash-merge, then mark TASK-198 Done in a post-merge administrative PR.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause confirmed before editing: MailboxMessageSerializer ignores persisted thread_id and emits an RFC822 search URL; commit fb4a51b also hid TASK-124's deployed queued-run control behind status.has_credentials. Debug artifact: .orchestrator/debug/task-198-2026-08-29-feature-1-1.md.

Validation 2026-08-29: the shared builder/serializer now emits an account-scoped #all/<thread_id> direct-conversation URL while preserving exact-draft and RFC822 fallback forms. The existing owner-only run-now endpoint is visible again on no-credential deployments, pending requests deduplicate, and the UI reports queued/running/skipped/failed outcomes through the existing status path. Gates passed: 1026 backend tests, 193 frontend tests, production build, Django check, migration drift check, compileall, npm audit (0 vulnerabilities), git diff check, and no-send implementation scan. Automated tests used only fake/synthetic mailbox data. AC1 awaits deployed click verification; authenticated Gmail was not accessed without permission.

Implementation squash-merged in PR #93 as ae4f8b04483c224c0307baa1997d1607cba37fe3. Main CI passed and the Azure deployment workflow completed, including its public-app verification. AC1 remains the sole unclosed criterion because the pre-sealed Asian Dad check requires observing an authenticated Gmail conversation; that safety-sensitive verification has not been fabricated or performed without permission.

Manual deployed verification completed by the owner on 2026-08-29: from the Azure mailbox page, the per-message link opened the Gmail conversation directly rather than the RFC822 search-results page. The earlier failed check was traced to localhost running the unrelated pre-fix wave9 worktree; debug artifact: .orchestrator/debug/task-198-2026-08-29-feature-1-3.md.

Asian Dad evaluation: PERFECT (self-graded). Evidence: owner-observed deployed direct conversation; manual-run endpoint/UI tests exercised immediate and queued outcomes; 1026 backend tests, 193 frontend tests, and production build passed; authorization and no-send scans passed; main CI/deployment passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Opened captured Gmail messages through persisted direct thread routes and restored owner-visible immediate/queued mailbox execution without adding send capability. Verified by 1026 backend tests, 193 frontend tests, production build/CI, successful Azure deployment, and the owner's live Gmail conversation check.
<!-- SECTION:FINAL_SUMMARY:END -->
