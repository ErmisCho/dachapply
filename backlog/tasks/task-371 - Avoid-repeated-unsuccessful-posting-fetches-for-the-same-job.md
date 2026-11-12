---
id: TASK-371
title: Avoid repeated unsuccessful posting fetches for the same job
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-11 15:24'
updated_date: '2026-11-12 09:35'
labels:
  - pipeline
  - performance
dependencies: []
modified_files:
  - backend/jobradar/tests/test_posting_fetch_cooldown.py
  - backend/jobradar/services/posting_fetch.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/services/application_prep.py
  - backend/jobradar/tests/test_api.py
  - docs/posting-fetch-retries.md
  - backend/jobradar/tests/conftest.py
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
- [ ] #1 A deterministic failure/retry workload counts actual fetch attempts for repeated analyses and document variants of the same unchanged job; the changed behavior reduces redundant attempts.
- [ ] #2 A bounded cooldown or equivalent deduplication never permanently suppresses recovery; an explicit manual Retry/Refresh can request a new fetch.
- [ ] #3 A changed URL or accepted/updated posting invalidates obsolete fetch decisions; concurrent requests for one job do not launch redundant equivalent retrievals.
- [ ] #4 Existing network/SSRF checks, posting freshness, owner Keep-current/Use-fetched decisions and account isolation remain intact.
- [ ] #5 Failures and the next permitted retry remain understandable to the user; regression tests cover repeated failure, recovery and manual bypass without real network calls.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Centralize automatic missing-posting fetches in posting_fetch, reuse the existing cache for a ten-minute failure cooldown keyed by account/job/URL/accepted text, and coalesce in-flight equivalent requests. Manual Retry/Refresh bypasses negative caching. Preserve guarded fetch and accepted/pending-text safety; prove fetch counts, expiry, invalidation and concurrent deduplication with hermetic tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Automatic analysis and CV workers share only the retrieval decision, preserving the CV worker caller-thread compare-and-swap and its existing owner-edit regression. The ten-minute cache is bounded at 256 entries and process-local; restarting clears the cooldown. Multi-process request coalescing requires a shared lease before scaling beyond this local single-process worker.

Successful results are not cached beyond the active fetch; only failures use the cooldown, avoiding reuse after an owner clears/updates posting text.

The counting regression is red on baseline before reaching the CV retry, so no unstubbed network call is needed to demonstrate the duplicate analysis fetch.

Cached failures retain the actual network-check timestamp; a later manual check/edit wins via the existing compare-and-swap write.

Extended the counting test to assert that reusing a cached failure does not pretend to have rechecked the network.

Read-only review found a real stale-cache case after a newer failed manual check. Added a regression before fixing it; cached outcomes must be rejected when older than source_checked_at.

Manual-check regression reproduced red, then corrected by comparing cached network time with the job last-check time; explicit manual failure is not overwritten with old evidence.

The shared test isolation fixture now clears the process-local fetch cache between tests, just as it clears model and board caches. Removed the duplicate local cooldown reset fixture. Final targeted run: 102 passed; review regression was caught and fixed.
<!-- SECTION:NOTES:END -->
