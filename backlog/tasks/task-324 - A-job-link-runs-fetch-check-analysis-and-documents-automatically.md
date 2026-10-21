---
id: TASK-324
title: 'A job link runs fetch, check, analysis and documents automatically'
status: In Progress
assignee: []
created_date: '2026-10-21 06:59'
updated_date: '2026-10-21 09:03'
labels:
  - backend frontend
dependencies: []
priority: high
ordinal: 324000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-21: one pipeline from link to documents. Adding a job (single add or the bulk links add) fetches the posting, checks completeness, analyses fit with the automatic-path model (cv_default_choice) and saves the evaluation at once (a new job has nothing to overwrite); the existing TASK-312 hook then queues documents for apply/maybe. Unreadable or incomplete postings keep today's paste/Continue anyway hold (owner chose: keep pasting). A per-account daily limit (default 50, editable on the Profile page, 0 = off) caps automatic runs; jobs over it wait in the Queue with Retry. Needs a UserProfile column (migration 0060), so it merges only right before the owner's Azure deploy. Pipeline stage is stored in the job's preparation sidecar as prep['pipeline']={'stage': fetching|analysing|skipped|limit|failed, 'at': ISO, 'recommendation', 'fit_score', 'error'} for TASK-325.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Adding a job with a link (single add and bulk links add) by an account that can generate starts fetch -> completeness check -> fit analysis in the background; the request returns without waiting
- [x] #2 The fit analysis uses cv_default_choice and is saved immediately (commit) for a job with no earlier evaluation; re-analysing a job that already has one is unchanged (preview first)
- [x] #3 An apply/maybe result queues documents through the existing TASK-312 hook; a skip result queues nothing and records stage skipped with the score
- [x] #4 A posting that cannot be read or is incomplete is analysed from what exists and held exactly as today (paste or Continue anyway)
- [x] #5 UserProfile.auto_pipeline_daily_limit (migration 0060, default 50) is editable on the Profile page; 0 turns automatic runs off; the count is jobs auto-started today for that account
- [x] #6 A job over the limit records stage limit and shows in the Queue as blocked with a reason naming the limit; Retry runs it now
- [x] #7 Model failures record stage failed with the reason; a usage limit retries after the reset (TASK-317)
- [x] #8 Merged only when the owner is ready to deploy to Azure right after (localhost shares the Neon DB)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged in #315 and deployed (Azure run 39563038852, migration 0060). Targeted tests: 140 + 301 passed; vitest 26; tsc clean. Localhost relaunched; Profile shows the daily limit field at 50; Queue loads. Open: one real link end to end on localhost (the owner picks the link).
<!-- SECTION:NOTES:END -->
