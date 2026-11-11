---
id: TASK-371
title: Avoid repeated unsuccessful posting fetches for the same job
status: To Do
assignee: []
created_date: '2026-11-11 15:24'
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
- [ ] #1 A deterministic failure/retry workload counts actual fetch attempts for repeated analyses and document variants of the same unchanged job; the changed behavior reduces redundant attempts.
- [ ] #2 A bounded cooldown or equivalent deduplication never permanently suppresses recovery; an explicit manual Retry/Refresh can request a new fetch.
- [ ] #3 A changed URL or accepted/updated posting invalidates obsolete fetch decisions; concurrent requests for one job do not launch redundant equivalent retrievals.
- [ ] #4 Existing network/SSRF checks, posting freshness, owner Keep-current/Use-fetched decisions and account isolation remain intact.
- [ ] #5 Failures and the next permitted retry remain understandable to the user; regression tests cover repeated failure, recovery and manual bypass without real network calls.
<!-- AC:END -->
