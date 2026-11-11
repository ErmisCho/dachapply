---
id: TASK-372.2
title: Turn only unresolved error groups into linked Backlog bugs
status: To Do
assignee: []
created_date: '2026-11-11 15:26'
labels:
  - observability
  - backlog
  - automation
dependencies:
  - TASK-372.1
parent_task_id: TASK-372
priority: high
type: feature
ordinal: 374000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the triage part of TASK-372 after durable error intake exists. A repeatable incremental command/workflow reviews new or changed unresolved groups, creates or updates real Backlog tasks through the CLI, and gives future maintenance sessions an evidence-based next-bug list. Do not launch a new always-running paid-model loop or create one task per log line.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Triage uses only unresolved new/changed occurrences; persisting a cursor/checkpoint and task linkage prevents unchanged evidence from being re-analysed after every session or restart.
- [ ] #2 Equivalent failures are grouped by a stable technical signature with environment/build context; one unresolved group links to at most one active bug task, including retries after a partially failed task-creation attempt.
- [ ] #3 Created bugs contain a sanitized symptom, source/time/affected operation, observed evidence, occurrence count and verification-oriented acceptance criteria; unknown reproduction steps and root causes are labelled unknown rather than fabricated.
- [ ] #4 Expected user cancellations, quota limits and transient operational failures are captured/classified without automatically flooding the product-bug backlog; actionable/retry-exhausted failures have a documented disposition, not silent suppression.
- [ ] #5 A dry-run shows proposed new/updated tasks and classifications; normal operation uses the Backlog CLI and stores private evidence links without copying raw sensitive logs into shared task files.
- [ ] #6 The agreed maintenance/session entrypoint can request the unresolved-only list; tests demonstrate idempotence, grouping, redaction and recovery from CLI failure without paid model calls.
<!-- AC:END -->
