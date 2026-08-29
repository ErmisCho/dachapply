---
id: TASK-198
title: Open the exact Gmail conversation and allow manual mailbox runs
status: In Progress
assignee:
  - '@pi'
created_date: '2026-08-29 16:27'
updated_date: '2026-08-29 19:03'
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
- [ ] #1 Each linked captured message with a persisted Gmail thread identifier opens the actual Gmail conversation, not a search results page
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
<!-- SECTION:NOTES:END -->
