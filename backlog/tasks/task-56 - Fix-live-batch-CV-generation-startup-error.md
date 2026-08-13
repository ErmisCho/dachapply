---
id: TASK-56
title: Fix live batch CV generation startup error
status: Done
assignee:
  - '@pi'
created_date: '2026-08-12 17:00'
updated_date: '2026-08-12 17:15'
labels: []
dependencies: []
ordinal: 57000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Starting selected application generation on localhost returns Django's HTML RuntimeError page and leaves each batch row failed. Fix the root backend startup error and keep API failures JSON-safe.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Batch CV generation starts successfully for a valid selected job on the running local app
- [x] #2 Generation startup errors return a concise JSON API error instead of an HTML debug page
- [x] #3 A regression test covers the observed startup failure and relevant backend/frontend checks pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Capture the live traceback and reproduce the failing generation-start request. 2. Fix the shared backend startup path and ensure API-safe errors. 3. Add a focused regression test, run backend/frontend checks, restart localhost, and verify a real request.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Captured the live exception: ThreadPoolExecutor rejected startup with 'cannot schedule new futures after interpreter shutdown' while Django's autoreloader was shutting down an old process. Replaced the process-blocking executor with the existing single-worker semantics on a daemon queue, added concise 503 JSON handling for generation/revision startup failures, and prevented the frontend API client from rendering HTML debug pages. Live verification generated job #539 with gpt-5.6-sol/xhigh/fast through generation, CV compile, letter compile, save, and Ready 100% with a non-empty ZIP/TeX payload and no server traceback. Validation: 3 focused tests passed; full backend suite passed (127 tests); frontend production build passed; makemigrations --check, py_compile, and diff check passed. Localhost was restarted in stable --noreload mode and health remains 200/database ok.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed live batch CV startup by replacing the shutdown-prone thread pool, returning JSON-safe startup errors, and suppressing raw HTML server pages. Verified a real job to Ready and passed all 127 backend tests plus the frontend build.
<!-- SECTION:FINAL_SUMMARY:END -->
