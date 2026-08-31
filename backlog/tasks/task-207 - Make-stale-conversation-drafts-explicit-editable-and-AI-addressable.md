---
id: TASK-207
title: 'Make stale conversation drafts explicit, editable, and AI-addressable'
status: Done
assignee:
  - '@pi'
created_date: '2026-08-31 09:07'
updated_date: '2026-08-31 14:07'
labels:
  - bug
  - mailbox
  - frontend
dependencies: []
modified_files:
  - backend/jobradar/serializers.py
  - backend/jobradar/services/draft_chat.py
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_draft_chat.py
  - backend/jobradar/tests/test_mailbox_panel.py
  - frontend/src/App.tsx
  - frontend/src/types/index.ts
  - frontend/src/appPanels.test.tsx
  - frontend/src/mailboxCollapse.test.tsx
  - .orchestrator/debug/task-207-2026-08-31-bugfix-1-1.md
  - .orchestrator/debug/task-207-2026-08-31-bugfix-1-2.md
  - .orchestrator/debug/task-207-2026-08-31-bugfix-1-3.md
  - .orchestrator/debug/task-207-2026-08-31-bugfix-2-1.md
  - .orchestrator/debug/task-207-2026-08-31-bugfix-2-2.md
  - .orchestrator/debug/task-207-2026-08-31-bugfix-2-3.md
  - .orchestrator/debug/task-207-2026-08-31-bugfix-3-1.md
  - .orchestrator/debug/task-207-2026-08-31-bugfix-3-2.md
  - .claude/.asian-dad/task-207-stale-draft-controls-rubric.json
  - >-
    backlog/tasks/task-207 -
    Make-stale-conversation-drafts-explicit-editable-and-AI-addressable.md
priority: high
ordinal: 206000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the expanded Email decisions conversation, an app-created Gmail draft currently looks like a sent owner message. Make its unsent draft state and stale conversation context unmistakable while preserving the ability to edit the draft and ask AI for help specifically with that message, without sending, deleting, or silently changing Gmail data.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Expanded conversations clearly distinguish app-created drafts from sent owner messages and label stale conversation-reply context plainly
- [x] #2 A stale draft remains editable through the existing owner-scoped draft editing path
- [x] #3 The owner can ask AI to draft/revise or explain the specific stale draft message, with that message identified in the AI context
- [x] #4 Normal captured sent messages and current non-stale drafts keep their existing behavior
- [x] #5 Synthetic regressions cover labels, editing, and message-specific AI help without contacting Gmail or using owner content
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve the measured identity/control root cause and sealed evaluator rubric without owner message content. 2. Reuse the persisted Gmail message-id relationship in the owner-scoped job-mailbox response to identify captured app drafts without exposing raw ids or adding per-row queries. 3. Render that exact conversation row as an UNSENT DRAFT and, when applicable, a STALE CONVERSATION REPLY, while keeping the shared edit and AI controls attached to it and avoiding duplicate controls. 4. Extend the existing exact-draft AI chat with explicit Draft/rewrite and Explain/understand modes; explanations never become accept buttons or Gmail writes. 5. Add synthetic backend/frontend regressions, run full gates, evaluate, merge, verify released runtime/deployment, and close.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause documented in .orchestrator/debug/task-207-2026-08-31-bugfix-1-1.md. Read-only released-runtime measurement: the draft Gmail message id matches exactly one captured sent_by_owner row, but that row has no draft relation; the serializer drops this identity, and the stale UI returns before edit/chat. Measurement made 0 writes and 0 Gmail calls.

Implemented exact captured-draft identity through the job-mailbox serializer, explicit UNSENT DRAFT / STALE CONVERSATION REPLY presentation, inline edit controls, and separate Draft/rewrite versus Explain/understand AI modes. Understanding results are never offered as replacement text and never write Gmail. Verification: 1040 backend tests, 198 frontend tests, production build, Django/migration/compile checks, npm audit (0 vulnerabilities), no-send/delete scan, synthetic browser interaction, and read-only measured-case serialization all passed. Asian Dad self-evaluation: PERFECT.

PR #109 squash-merged as 5f8055f. Main run 33400177245 passed tests, image deployment, and public Azure verification. The synchronized released runtime serves the same SHA with API/web HTTP 200. Final released-code measured-case check remained read-only with zero Gmail calls.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Made captured Gmail drafts unmistakably unsent and stale in the exact conversation row, retained owner-scoped editing, and added exact-draft AI modes for rewriting or understanding without treating explanations as replacement text. Synthetic browser/API checks, 1040 backend tests, 198 frontend tests, build/audit/safety gates, measured released data, CI, runtime parity, and Azure deployment passed.
<!-- SECTION:FINAL_SUMMARY:END -->
