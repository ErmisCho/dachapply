---
id: TASK-255
title: Stage and review refreshed job-posting text
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-30 21:58'
updated_date: '2026-10-01 08:05'
labels:
  - frontend
  - backend
  - data
dependencies: []
references:
  - >-
    https://www.glueckimjob.cal-group.at/jobs/1784-data-scientist-ai-engineer-all-genders
  - models
  - views
  - app
  - cv-generator
documentation:
  - docs/specs/2026-09-30-job-posting-text-refresh-design.md
modified_files:
  - docs/specs/2026-09-30-job-posting-text-refresh-design.md
  - backend/jobradar/models.py
  - backend/jobradar/migrations/0053_job_source_refresh.py
  - backend/jobradar/serializers.py
  - backend/jobradar/views.py
  - backend/jobradar/urls.py
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/tests/test_posting_fetch.py
  - frontend/src/types/index.ts
  - frontend/src/App.tsx
  - frontend/src/postingSource.test.tsx
  - frontend/src/cvPopup.test.tsx
  - .orchestrator/debug/01a0edd2-7a80-737c-9bb4-8581c24c7af5-7.md
  - .orchestrator/debug/01a0edd2-7a80-737c-9bb4-8581c24c7af5-8.md
  - .orchestrator/debug/01a0edd2-7a80-737c-9bb4-8581c24c7af5-9.md
  - .orchestrator/debug/01a0edd2-7a80-737c-9bb4-8581c24c7af5-10.md
  - .orchestrator/debug/01a0edd2-7a80-737c-9bb4-8581c24c7af5-11.md
  - .orchestrator/debug/01a0edd2-7a80-737c-9bb4-8581c24c7af5-12.md
priority: high
type: feature
ordinal: 253000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Job records can contain missing, stale, or irrelevant source text even when their listing URL remains readable. Reuse the guarded posting fetcher to stage fresh text for explicit comparison and acceptance, expose fetch/refetch from each job menu, warn without dropping jobs when add-time extraction fails, and check URL-backed jobs when the application opens at a user-configurable cadence. Active or manually corrected text must never be overwritten automatically.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A job-menu Fetch/Refetch action retrieves the listing and stages differing text for review without overwriting active text; failures are reported honestly.
- [x] #2 Adding a URL-backed job always saves it, retains a successful differing fetch as a pending candidate, and on failure shows a per-listing warning with manual text entry.
- [x] #3 The CV and letter workflow shows editable active and pending text side by side, requires Keep current or Use fetched before generation when a candidate exists, and generates only from the accepted active text.
- [x] #4 Profile settings offer Off, Daily, and Weekly app-open checks with Daily as the default; Off performs no automatic URL requests.
- [x] #5 A due app-open check safely examines URL-backed jobs, creates review candidates only for differing readable text, and leaves stored text unchanged on identical results or failure.
- [x] #6 Jobs without a source URL retain manual text entry and never offer or attempt URL fetching.
- [x] #7 The supplied Glueck im Job listing produces vacancy content rather than cookie or navigation-only text, and focused regressions plus full backend/frontend gates pass.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Persist one pending fetched candidate plus fetch/check metadata on each job, and persist the account's Off/Daily/Weekly cadence with Daily as the default.
2. Reuse the guarded posting reader behind shared staging logic for manual refetch, add-time retrieval, and bounded app-open due batches; never mutate accepted text until an explicit source-text PATCH.
3. Extend source APIs and generation preview so candidate review is atomic and generation refuses unresolved candidates.
4. Add one reusable comparison/editor dialog to the selected-job menu, add result cards, job detail, and CV/letter flow; start due batches unobtrusively from the dashboard and expose cadence in Profile settings.
5. Add focused backend and server-rendered frontend regressions, verify the supplied live URL, then run all quality gates and browser measurements.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented one accepted source plus one staged candidate, shared guarded fetch/staging APIs, bounded app-open checks, profile cadence, add-time review cards, selected-job review, and generation gates/editors.

Verification (2026-10-01): 1,243 backend tests and 307 frontend tests passed; TypeScript and production build passed; migrations and git diff checks passed. Authenticated browser verification created both successful and failed URL-backed jobs, showed per-listing failure/manual recovery, measured editable 14,881/14,839-character generation panes with generation disabled until resolution, verified URL-less manual editing with no fetch control, and persisted explicit Keep/Use decisions. The supplied Glueck im Job URL yielded 14,839 characters containing Data Scientist, AI Engineer, Python, and Österreichische Lotterien with zero U+FFFD characters. Asian Dad verdict: PERFECT.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added safe staged job-posting refresh and review across add, dashboard, profile, detail, and CV/letter workflows. Accepted text is never automatically overwritten; differing text must be edited and explicitly kept or used. Verified by full backend/frontend gates, live supplied-URL extraction, authenticated browser flows, direct database inspection, and a PERFECT Asian Dad evaluation.
<!-- SECTION:FINAL_SUMMARY:END -->
