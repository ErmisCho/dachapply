---
id: TASK-372.1
title: Collect durable sanitized Dachapply error occurrences
status: To Do
assignee: []
created_date: '2026-11-11 15:26'
labels:
  - observability
  - security
  - backend
dependencies: []
parent_task_id: TASK-372
priority: high
type: feature
ordinal: 373000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the capture part of TASK-372. Existing errors are split between Django alert/log handlers, task failures, mailbox records, benchmark/adjustment JSONL, failed TeX/log files and bounded runtime execution events. Reuse those signals. Include explicit failed outcomes even when exceptions are caught or a worker returns a failure without logging ERROR. Store private evidence separately from public/shared task summaries; never require publishing raw logs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An explicit tested coverage matrix accounts for backend exceptions/500s, pipeline/document/provider/compile/mailbox failures, browser exceptions and failing CI/deploy runs; unavailable sources report why and how they become available, never silently appear covered.
- [ ] #2 Each captured occurrence has a stable ID, time, source/environment, operation/run/build identity when available, sanitized error type/summary and safe local evidence reference; ordinary successful or warning-only logs do not become errors.
- [ ] #3 Occurrence records and intake progress survive restarts and normal source rotation; replay does not create duplicates, while two genuinely separate identical failures are retained as separate occurrences.
- [ ] #4 Secrets, auth/session data, provider prompts, candidate/CV contents, mail bodies and unsafe filesystem/connection details stay out of safe summaries; retained private evidence is owner-restricted and excluded from git/public exports.
- [ ] #5 Collection has bounded storage/work and documented retention without silently dropping unresolved evidence; a collector failure neither breaks application work nor causes recursive logging storms, and exposes a safe degraded-health signal.
- [ ] #6 Hermetic tests exercise source intake, caught failures, redaction, repeated ingestion, concurrent writes, restart/rotation and collection failure; no production access or real provider failure is needed.
<!-- AC:END -->
