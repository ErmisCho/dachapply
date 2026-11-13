---
id: TASK-372
title: Collect error evidence once and drive unresolved bugs through Backlog
status: Done
assignee: []
created_date: '2026-11-11 15:25'
labels:
  - observability
  - backlog
  - reliability
dependencies: []
priority: high
type: feature
ordinal: 372000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request: all Dachapply logs that end in errors should be collected, serve as evidence for the next bugs to solve in Backlog, and be marked done after a verified fix so the same logs are not analysed again. Extend existing TASK-88 alerting, TASK-289 mailbox failure visibility, TASK-334 private adjustment/LaTeX evidence and TASK-157 redaction; do not replace them with a second logging framework. Scope is Dachapply-owned runtime, worker/provider/compiler/mailbox, browser and CI/deploy failures, not arbitrary machine logs. Use an explicit source coverage matrix and safe adapters where a source is unavailable. Initial work is the smallest durable owner-only inbox, incremental triage and resolution synchronization; no new dashboard, external SaaS or autonomous paid-agent loop is requested. Related evidence remains private; public/shared Backlog gets only safe technical summaries. Capture all error evidence, but distinguish product defects from expected cancellations, quota limits and transient operational incidents. Migrations, CI gates and production changes require the existing owner approval/deploy policy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Dachapply-owned error/failure sources feed a durable, private inbox with stable occurrence identity, timestamp/source, safe technical context and links to any retained local evidence; source coverage and limitations are explicit.
- [x] #2 Incremental triage groups unresolved evidence into actionable Backlog bugs via the Backlog CLI, linking repeated occurrences instead of flooding duplicate tasks or inventing root causes.
- [x] #3 A verified fix and completed linked task mark its related occurrence records resolved/done; subsequent analysis and source replay exclude those resolved occurrences without deleting the audit trail.
- [x] #4 A genuinely new post-fix occurrence is captured as a regression/new incident; old log replay or failures from an unfixed old build are distinguished rather than re-opening fixed work endlessly.
- [x] #5 End-to-end tests cover capture, replay/deduplication, task linkage, verified closure, skipped re-analysis and a real new occurrence; no credentials/private prompts/CV/mail content enters tracked Backlog or public responses.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-13 (coordinator): all subtasks 372.1-372.3 merged and verified.
<!-- SECTION:NOTES:END -->
