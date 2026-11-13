---
id: TASK-372.2
title: Turn only unresolved error groups into linked Backlog bugs
status: Done
assignee: []
created_date: '2026-11-11 15:26'
updated_date: '2026-11-12 16:55'
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
- [x] #1 Triage uses only unresolved new/changed occurrences; persisting a cursor/checkpoint and task linkage prevents unchanged evidence from being re-analysed after every session or restart.
- [x] #2 Equivalent failures are grouped by a stable technical signature with environment/build context; one unresolved group links to at most one active bug task, including retries after a partially failed task-creation attempt.
- [x] #3 Created bugs contain a sanitized symptom, source/time/affected operation, observed evidence, occurrence count and verification-oriented acceptance criteria; unknown reproduction steps and root causes are labelled unknown rather than fabricated.
- [x] #4 Expected user cancellations, quota limits and transient operational failures are captured/classified without automatically flooding the product-bug backlog; actionable/retry-exhausted failures have a documented disposition, not silent suppression.
- [x] #5 A dry-run shows proposed new/updated tasks and classifications; normal operation uses the Backlog CLI and stores private evidence links without copying raw sensitive logs into shared task files.
- [x] #6 The agreed maintenance/session entrypoint can request the unresolved-only list; tests demonstrate idempotence, grouping, redaction and recovery from CLI failure without paid model calls.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Extend the local SQLite store with safe context, stable groups, private links and checkpoints. 2. Add unresolved-only triage management command using the Backlog CLI with recovery markers and dry-run. 3. Verify grouping, idempotence, privacy and failure recovery; run required suites and record results without status or AC changes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TASK-372.2 implementation (changes deliberately uncommitted; status and AC unchanged):
- Extended the opt-in private SQLite store with bounded classification/build metadata, error_groups checkpoint/task links, and private error_group_links. No Django model/migration.
- Added triage_errors management command: changed unresolved groups only; --dry-run previews actions/classifications; --list returns the full unresolved maintenance queue. Backlog subprocess CLI is the only task writer; stable title markers recover partially successful creates; SQLite serializes cooperating triagers.
- Fixed vocabulary redaction and sanitized bug descriptions with source, time, affected-operation/build digests, counts, unknown reproduction/root cause, verification AC. Unknown/cancellation/quota/transient dispositions stay visible without automatic bug creation. Only actionable/retry_exhausted create bugs. Legacy/current unclassified hooks require trusted local review. TASK-372.3 resolution/regression intentionally excluded; group/task/evidence links remain queryable.
- Documented entrypoint, classification/review procedure, privacy, recovery-marker requirement and CLI write-lock/intake contention limitation in docs/error-occurrences.md.
AC evidence in backend/jobradar/tests/test_error_triage.py:
1: test_group_incremental_restart_and_private_links; test_build_and_operation_separate_groups_and_resolved_excluded; test_changed_classification_and_command.
2: test_group_incremental_restart_and_private_links; test_build_and_operation_separate_groups_and_resolved_excluded; test_cli_failure_and_partial_creation_recovery[False/True]; test_parallel_triagers_create_one_task.
3: test_redaction_and_bug_content.
4: test_dispositions (6 classifications); test_legacy_rows_and_untrusted_classification; documented disposition/review procedure.
5: test_changed_classification_and_command; test_redaction_and_bug_content; test_group_incremental_restart_and_private_links.
6: test_changed_classification_and_command; test_command_failure_is_sanitized; restart/idempotence/grouping/redaction/recovery tests above; all Backlog subprocess calls faked, no models/providers.
Validation so far:
- Initial requested uv run pytest failed before execution because uv's default cache is inaccessible. Redirected UV_CACHE_DIR to system temp. Plain pytest then reported 31 setup errors because Python 3.13 mode-0700 temp directories are inaccessible in this Windows sandbox; an explicit basetemp had the same ACL issue.
- Final focused verification: 34 passed, 0 failed. Exact PowerShell commands (cwd backend):
$env:UV_CACHE_DIR = Join-Path $env:TEMP 'dachapply-3722-uv'; $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -c "import os,pytest; original=os.mkdir; os.mkdir=lambda path,mode=0o777,**kw: original(path,0o777,**kw); raise SystemExit(pytest.main(['-q','--tb=line','-p','no:cacheprovider','--basetemp',os.path.join(os.environ['TEMP'],'dachapply-3722-focused-4'),'jobradar/tests/test_error_occurrences.py','jobradar/tests/test_error_triage.py']))"
The in-process test runner only changes mkdir mode to inherit temp ACLs; no product/test fixtures changed for this sandbox workaround. All outputs under system temp. An intermediate run caught an accidentally removed sqlite3 import (15 failed/19 passed); restored it before the final 34-pass run.
- cwd frontend: npx tsc --noEmit: blocked before checks, ENOTCACHED (TypeScript dependency absent, registry unavailable offline); npm test: blocked before test collection, vitest not installed. 0 frontend tests executed. No frontend changes.
- git diff --check: passed.
Full backend suite started once; results will be appended when complete. No production DB, real Backlog task creation in tests, CI/auth/secrets edits, or git commit/push/reset/stash/checkout.

Final validation:
- Full backend suite, run once: 2176 passed, 2 failed, 969 warnings, 873.12s. Exact PowerShell commands (cwd backend):
$env:UV_CACHE_DIR = Join-Path $env:TEMP 'dachapply-3722-uv'; $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -c "import os,pytest; original=os.mkdir; os.mkdir=lambda path,mode=0o777,**kw: original(path,0o777,**kw); raise SystemExit(pytest.main(['-q','--tb=line','-p','no:cacheprovider','--basetemp',os.path.join(os.environ['TEMP'],'dachapply-3722-full-1')]))"
- Full-suite failures: test_analysis_time_limit.py::test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit (11.43s vs <5s); test_model_discovery_returns_although_a_server_it_started_holds_the_output (2s subprocess timeout). These tests exercise existing process control code outside TASK-372.2; occurrence storage is disabled there by settings_test. No changes to those tests/services.
- Isolated rerun: 1 passed, 1 failed in 9.86s. Discovery passed; model process kill still failed (child did not exit within 5s). Exact commands (cwd backend):
$env:UV_CACHE_DIR = Join-Path $env:TEMP 'dachapply-3722-uv'; $env:PYTHONDONTWRITEBYTECODE='1'; uv run python -c "import os,pytest; original=os.mkdir; os.mkdir=lambda path,mode=0o777,**kw: original(path,0o777,**kw); raise SystemExit(pytest.main(['-q','--tb=line','-p','no:cacheprovider','--basetemp',os.path.join(os.environ['TEMP'],'dachapply-3722-timing-1'),'jobradar/tests/test_analysis_time_limit.py::test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit','jobradar/tests/test_analysis_time_limit.py::test_model_discovery_returns_although_a_server_it_started_holds_the_output']))"
- No PERFECT evaluation claimed: full validation is not green and frontend checks cannot execute with missing offline dependencies. Resolution/regression (TASK-372.3) remains deliberately unimplemented.
- Final code-only follow-up made the new-file TASK-372.2 markers explicit hash comments; behavior unchanged. All changes remain uncommitted, task status/AC unchanged.
2026-11-13 (coordinator): 34 tests (CLI faked); review fix: updates append notes instead of replacing descriptions (PR 405).
<!-- SECTION:NOTES:END -->
