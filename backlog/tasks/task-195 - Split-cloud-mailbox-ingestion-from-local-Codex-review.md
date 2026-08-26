---
id: TASK-195
title: Split cloud mailbox ingestion from local Codex review
status: Done
assignee:
  - '@pi'
created_date: '2026-08-26 05:44'
updated_date: '2026-08-26 11:00'
labels:
  - mailbox
  - backend
  - frontend
  - ops
  - ai
dependencies:
  - TASK-194
references:
  - backend/jobradar/services/mailbox.py
  - backend/jobradar/services/draft_chat.py
  - .github/workflows
modified_files:
  - .github/workflows/mailbox-check.yml
  - backend/jobradar/services/mailbox.py
  - backend/jobradar/services/mailbox_ai.py
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_mailbox_ai.py
  - frontend/src/App.tsx
  - docs/email-setup.md
  - backend/jobradar/models.py
priority: high
ordinal: 195000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Run the reliable, non-LLM Gmail ingestion stage in the cloud while keeping subscription-backed Codex processing on the owner's local machine. The cloud stage fetches and deterministically classifies mail into the shared database every hour even when the PC is off. The local Mailbox page explicitly processes stored heuristic-uncertain messages with the installed Codex CLI when the owner chooses; model output is guarded and may improve the stored classification but never directly changes a job, sends mail, or writes a Gmail draft. The prior local Windows ingestion scheduler is removed so cloud and local cannot fetch the same mailbox concurrently.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A scheduled cloud workflow runs check_mailbox hourly against the shared database with Gmail OAuth secrets and no LLM configuration, and can also be dispatched manually
- [x] #2 The local owner can see the count of heuristic-uncertain messages and process a bounded batch with an available Codex subscription model from the Mailbox page
- [x] #3 Codex results use a strict structured schema and the existing status-changing guard; failures leave every message unchanged and are reported clearly
- [x] #4 Successful local review marks each processed message with the Codex evaluator and updates only its classification; it never changes a job, creates a suggestion/draft, or contacts Gmail
- [x] #5 The local AI endpoint is unavailable to non-owners, remote callers, non-local deployments, and machines without Codex
- [x] #6 The obsolete local Windows Gmail-ingestion scheduler and its UI are removed so only the cloud workflow fetches on schedule
- [x] #7 Documentation names required cloud secrets and the local/cloud responsibility split; tests mock all Gmail, Codex, and OS calls
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Remove TASK-194's local Windows Gmail scheduler endpoint, installer, tests, and Profile control so there is no second mailbox fetcher. 2. Add an hourly/manual GitHub Actions workflow that writes the OAuth token from repository secrets and runs check_mailbox --force with LLM_PROVIDER=heuristic against the shared database; document and configure the secrets without exposing values. 3. Add a small local Codex structured-output runner and a loopback/owner-only MailboxRun action that batches at most 10 stored heuristic-uncertain messages, applies the existing status-changing guard, and atomically updates only classification/evaluator after the whole model result validates. 4. Add a Mailbox-page pending count/action with clear results and no automatic model execution. 5. Add focused mocked tests, run full backend/frontend checks, and manually dispatch the cloud workflow.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Live validation: GitHub Actions run 32937108851 completed successfully on main (11 fetched; deterministic heuristic mode; no LLM). Repository DATABASE_URL and Gmail OAuth secrets were refreshed from working local secure sources without printing values. A synthetic one-message call through the installed Codex CLI returned application_confirmed. Local scheduled task query confirms DACHApply Mailbox Check is not installed.

Quality gates: backend 1003 passed; frontend 183 passed; frontend production build passed; git diff --check passed. The first manual cloud run exposed an invalid job-level runner.temp expression, fixed in ebd8064; the next exposed a stale DATABASE_URL secret, which was rotated before the successful run.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Moved deterministic Gmail ingestion to a live hourly/manual GitHub Actions workflow and added explicit, bounded local Codex reclassification for heuristic-uncertain messages. The endpoint is owner/loopback/DEBUG/Codex gated, validates strict structured output, applies existing classification guards, and atomically updates only classification/evaluator. Removed the competing local scheduler path, documented the secret/responsibility split, and verified full backend/frontend suites plus a successful cloud dispatch.
<!-- SECTION:FINAL_SUMMARY:END -->
