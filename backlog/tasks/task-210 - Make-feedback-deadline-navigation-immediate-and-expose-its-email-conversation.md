---
id: TASK-210
title: Make feedback-deadline navigation immediate and expose its email conversation
status: Done
assignee:
  - '@pi'
created_date: '2026-09-01 11:20'
updated_date: '2026-09-01 15:44'
labels:
  - frontend
  - backend
  - performance
  - email
  - followups
dependencies: []
modified_files:
  - backend/jobradar/services/mailbox.py
  - backend/jobradar/tests/test_api.py
  - backend/jobradar/tests/test_mailbox.py
  - backend/jobradar/views.py
  - frontend/src/App.tsx
  - frontend/src/feedbackDueControls.test.tsx
  - frontend/src/types/index.ts
priority: high
type: enhancement
ordinal: 209000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Feedback deadlines company/title control currently clears board filters and refetches the full board before scrolling even when the row is already mounted, making Sponsorhive — CTO take about three seconds. Each deadline row also needs an adjacent email action that opens the relevant matched mail as the existing chat-style thread and keeps reply/decision/Gmail actions available. Measured Sponsorhive job 1079 has zero captured messages, drafts, or suggestions and no stored contact address, so its empty state must be honest rather than inventing a recipient.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Clicking a feedback deadline whose board row is already mounted scrolls to and highlights it immediately without a jobs API refetch; a filtered-out row still falls back to the existing owner-scoped locate behavior
- [x] #2 Every feedback deadline row has a compact accessible email button with a 44px target; opening it lazily performs at most one owner-scoped job-mailbox request and adds no per-row dashboard-load requests
- [x] #3 The opened view reuses the existing per-thread chat-style conversation, showing captured received and owner messages chronologically with existing reply, exact-Gmail, draft, and pending-decision controls
- [x] #4 A job with no captured conversation or contact address, including measured Sponsorhive job 1079, clearly says that no recipient/message is known and never fabricates one; it offers only an honestly labelled Gmail search fallback
- [x] #5 Mailbox and Gmail actions remain owner-scoped, never send mail, and automated tests use synthetic data and fake boundaries only
- [x] #6 Regression evidence covers immediate navigation, fallback navigation, lazy conversation loading, exact conversation rendering, and the measured no-mail empty state; full backend/frontend gates and browser interaction pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve the measured root cause: Sponsorhive job 1079 has no captured message/draft/contact, and the current click always resets filters/refetches the full board. 2. Reuse the mounted board row first and refetch only as a filtered-out fallback, with a unit seam proving request/no-request behavior. 3. Add one adjacent email button that lazily fetches the existing owner-scoped job mailbox once and opens the existing per-thread chat conversation in a modal, including current reply/draft/decision controls. 4. Extend the one Gmail URL builder with an account-scoped company-search fallback for honest zero-message cases; do not invent an address or add sending. 5. Add synthetic backend/frontend regressions, browser timing/request-count checks, full gates and Asian Dad evaluation, then squash-merge and close through the post-merge workflow.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Read-only production measurement: Sponsorhive — CTO is job 1079, status interview, feedback due 2026-08-26; matched messages=0, drafts=0, pending suggestions=0, stored contact emails=0, Gmail calls=0, writes=0. Root navigation path unconditionally calls the full board loader before looking for an already-mounted row.

Implemented mounted-row-first navigation with the existing reset-load fallback; one lazy job-mailbox request powers the reused chat conversation modal. Gmail fallback searches the authenticated user's account by company and explicitly states when no captured conversation or recipient is known. Browser evidence: Sponsorhive target 0.5 ms, 0 jobs requests; email button 44x44, one mailbox request, 0 jobs requests; filtered fallback one reset jobs request; synthetic two-message thread chronological with reply, exact-Gmail, draft, and pending-decision controls. Gates: 1,045 backend tests, 206 frontend tests, focused tests, TypeScript/Vite build, Django checks, migration check, npm audit with 0 vulnerabilities, diff check, and no-send/delete scan passed. Asian Dad verdict: PERFECT (self-graded disclosed). Browser timing/setup failures are preserved in .orchestrator/debug/task-210-*.md and were traced to disposable DB setup, minimized-tab input/polling, and case-sensitive verifier assumptions rather than product defects.

Released through implementation PR #115, squash-merged as 085a6277c74bd6c65642543ab715314b30e77215. Main CI/deployment run 33527072981 passed backend/frontend tests, image build, Azure deploy, and public-app verification on the released SHA. Independent post-deploy probes returned HTTP 200 for both the public root and /api/health/.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Made feedback-deadline navigation immediate when its row is mounted, retained the filtered-row reload fallback, and added a 44px email action that lazily opens the existing owner-scoped chat conversation. Captured threads retain reply/Gmail/draft/decision controls; unknown Sponsorhive mail stays explicit and offers only an authenticated-user Gmail search. Verified by full gates and measured browser request/timing/DOM evidence.
<!-- SECTION:FINAL_SUMMARY:END -->
