---
id: TASK-371
title: Avoid repeated unsuccessful posting fetches for the same job
status: Done
assignee: []
created_date: '2026-11-11 15:24'
updated_date: '2026-11-12 13:44'
labels:
  - pipeline
  - performance
dependencies: []
priority: medium
type: enhancement
ordinal: 371000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Grounded opportunity from Backlog doc-1, Application pipeline efficiency opportunities - 2026-11-11. Historical timings are not a controlled speedup comparison. Preserve TASK-348 all-letter alternatives, TASK-303 model quality/defaults, owner data, cancellation, per-account access and daily budgets. Incomplete postings may be refetched during analysis and again before document generation when usable original text is absent. Measure duplicate requests and avoid repeatedly paying for the same failed retrieval while retaining explicit user control and fresh-posting correctness.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A deterministic failure/retry workload counts actual fetch attempts for repeated analyses and document variants of the same unchanged job; the changed behavior reduces redundant attempts.
- [x] #2 A bounded cooldown or equivalent deduplication never permanently suppresses recovery; an explicit manual Retry/Refresh can request a new fetch.
- [x] #3 A changed URL or accepted/updated posting invalidates obsolete fetch decisions; concurrent requests for one job do not launch redundant equivalent retrievals.
- [x] #4 Existing network/SSRF checks, posting freshness, owner Keep-current/Use-fetched decisions and account isolation remain intact.
- [x] #5 Failures and the next permitted retry remain understandable to the user; regression tests cover repeated failure, recovery and manual bypass without real network calls.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Add a bounded per-job automatic-fetch failure cooldown and single-flight retrieval; share it between analysis and documents, preserve manual refresh and source review, and verify hermetically.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented a 15-minute failure cooldown (maximum 1024 decisions) and single-flight automatic retrieval keyed by job/account/URL/current and pending text. Shared by analysis and document generation; explicit blocked-job Retry and manual Refresh bypass cooldown. Failure messages include next automatic retry time. Keep-current/Use-fetched and network guards unchanged. Limitation: coordination is process-local; separate backend processes may still retrieve concurrently.
AC1: test_analysis_and_document_variants_share_failure counts one attempt across three analysis/document pairs. AC2/3/5: test_failure_workload_expiry_manual_and_invalidation covers six-to-one attempts, expiry, manual bypass, URL/text/account invalidation and recovery. test_equivalent_concurrent_requests_share_retrieval covers concurrent calls. AC4: existing posting-fetch security/review tests retained, not executable here.
Validation: cd backend; uv run pytest -q --tb=line -p no:cacheprovider <focused files> initially blocked by uv cache permissions. With UV_CACHE_DIR in system temp and --no-sync, focused files jobradar/tests/test_posting_fetch_cooldown.py jobradar/tests/test_posting_fetch.py jobradar/tests/test_link_only_prep.py jobradar/tests/test_api.py: 0 passed, 353 setup errors (system temp directory access denied). Retry with --basetemp in system temp: same setup block and teardown access failure. Full suite once: cd backend; uv run --no-sync pytest -q --tb=line -p no:cacheprovider: 0 passed, 1 collection error (missing dj_database_url). Frontend: cd frontend; npx tsc --noEmit: blocked ENOTCACHED/missing dependencies; npm test: 0 passed, vitest unavailable. Standalone direct invocation of the first two new hermetic tests with Django settings_test and pytest.MonkeyPatch: 2 passed, 0 failed. git diff --check passed. No AC boxes/status changed; no commits/pushes. uv created an ignored .venv during validation; cleanup was blocked by automatic policy review.
2026-11-13 (coordinator): verified red/green; coordinator fixed Codex version: manual Refresh suffix, automatic retries and scheduled refresh bypassing the cooldown (regression tests added). PR 404.
<!-- SECTION:NOTES:END -->
