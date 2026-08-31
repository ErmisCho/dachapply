---
id: TASK-206
title: Stop stale mailbox replies after the conversation has ended
status: In Progress
assignee:
  - '@pi'
created_date: '2026-08-31 08:13'
updated_date: '2026-08-31 08:41'
labels:
  - bug
  - mailbox
  - drafts
dependencies: []
modified_files:
  - backend/jobradar/services/mailbox.py
  - backend/jobradar/serializers.py
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_mailbox.py
  - backend/jobradar/tests/test_mailbox_panel.py
  - frontend/src/App.tsx
  - frontend/src/types/index.ts
  - frontend/src/appPanels.test.tsx
  - frontend/src/followupAction.test.tsx
  - .orchestrator/debug/task-206-2026-08-31-bugfix-1-1.md
  - .orchestrator/debug/task-206-2026-08-31-bugfix-1-2.md
  - .orchestrator/debug/task-206-2026-08-31-bugfix-1-3.md
  - .claude/.asian-dad/task-206-stale-mailbox-reply-rubric.json
  - >-
    backlog/tasks/task-206 -
    Stop-stale-mailbox-replies-after-the-conversation-has-ended.md
priority: high
ordinal: 205000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Email decisions panel can show an old generic 'I remain very interested' Gmail draft beside a later rejection even after the owner has already replied goodbye in that conversation. Use captured thread chronology and outcome context so the panel never presents a stale or contradictory response as the next action, without sending mail, deleting owner data, or contacting Gmail during automated tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A written draft is not presented as actionable when a newer owner-authored message exists in the same captured Gmail thread
- [ ] #2 A written interested/follow-up draft is not presented beside a newer rejection or other terminal conversation outcome
- [ ] #3 Current reply-worthy drafts with no later owner response or terminal outcome remain available
- [ ] #4 Regression tests cover the measured Formunauts-style chronology without contacting Gmail or using owner content
- [ ] #5 Owner scoping, no-send behavior, and existing Gmail deep links remain unchanged
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve the measured chronology/root-cause artifact and sealed evaluator rubric without committing owner message content. 2. Add the narrow terminal-closure classifier signal and a shared newer-owner-reply guard that excludes the app draft's own captured Gmail id. 3. Mark already-persisted action-panel drafts stale through owner-scoped serialization and replace contradictory body/edit/chat controls with a non-destructive notice and Gmail link. 4. Add synthetic backend/frontend regressions for stale, self-captured-draft, terminal, and still-current cases; run full gates, evaluate, merge, verify deployment/runtime, and close.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Read-only, scheduler-disabled production metadata confirmed the owner report without contacting Gmail: a closure was classified recruiter_reply, the genuine owner reply was captured 52 minutes later, and the generic draft was created about 31 hours after that reply. The app draft's own captured message shares its Gmail message id and must not count as owner-send proof. Root cause: .orchestrator/debug/task-206-2026-08-31-bugfix-1-2.md.

Implemented three bounded protections: classify the measured polite closure as rejection; refuse generation when a newer genuine owner reply is already captured or later in the same fetch; serialize/render persisted stale drafts as a non-destructive notice instead of contradictory body/edit/chat controls. The app draft's own captured Gmail message id is excluded from reply proof.

Verification: production-scoped read-only check reports the existing case stale and reclassifies its closure as rejection with 0 writes/Gmail calls; focused backend 7 and frontend 14 passed; full backend 1034 and frontend 197 passed; build, Django/migration/compile checks, npm audit, and no-send/delete scan passed. Asian Dad self-evaluation: PERFECT.
<!-- SECTION:NOTES:END -->
