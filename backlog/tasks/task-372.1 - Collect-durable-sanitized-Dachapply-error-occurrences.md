---
id: TASK-372.1
title: Collect durable sanitized Dachapply error occurrences
status: To Do
assignee: []
created_date: '2026-11-11 15:26'
updated_date: '2026-11-12 14:07'
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add opt-in local-only SQLite occurrence intake with fixed safe summaries, replay keys, atomic progress, bounded storage and health. No migration; Azure collection explicitly unavailable without a durable deployment store. 2. Connect ERROR logging and explicit preparation/document/mailbox failure outcomes. Document source coverage and retention. 3. Run hermetic focused and full backend tests plus frontend checks; record evidence without status or AC changes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TASK-372.1 implementation (uncommitted; status and AC boxes deliberately unchanged):
- Added opt-in LOCAL-ONLY SQLite occurrence collection in backend/jobradar/services/error_occurrences.py. No Django model or migration. DEBUG=False/Azure is explicitly unavailable because container storage is ephemeral; local collection does not use Neon.
- Connected django.request/jobradar ERROR logs, application preparation failed outcomes, CV/adjustment terminal failures, provider failure construction, failed compiler attempts, and scheduled/manual mailbox errors. Fixed safe summaries and hashes only; no raw evidence archive, prompt/CV/mail text, request/session data, exception messages or paths retained.
- Stable source-scoped occurrence ids; bounded atomic batch intake with persistent replay keys/cursor digest, unresolved query, concurrent SQLite transactions, 10,000 row/4,096 page cap, no unresolved eviction, safe process-local degraded health and no collector logging.
- docs/error-occurrences.md contains setup, local-only limitation, explicit connected/unavailable coverage matrix, retention, saturation behavior, adapter identity/cursor contract, and seams for 372.2/372.3. Browser, CI/deploy and historical-file adapters are explicitly unavailable with activation guidance; no CI/auth/secrets changes.
AC evidence: #1 coverage matrix + test_coverage_matrix_is_explicit + real 500/mailbox/compile integration tests. #2 test_source_intake_redaction_and_non_errors. #3 test_replay_restart_rotation_and_atomic_progress + test_concurrent_replay_and_distinct_failures. #4 fixed-vocabulary intake + redaction/non-error test (including SQLite bytes), existing error-alert redaction suite. #5 test_bounded_storage_and_failure_without_logging + test_oversized_batch_rolls_back + retention documentation. #6 source-parametrized intake, caught worker/provider, real 500/mailbox/compile, concurrent replay, restart/generation rotation and collector-failure tests.
Validation so far: new test_error_occurrences.py: 17 passed, 0 failed. Initial focused occurrence/error-alert/mailbox suite: 43 passed, 0 failed, 9 warnings. Expanded focused run: 117 passed, 1 failed, 49 warnings; failed assertion found inconsistent Unavailable wording in historical coverage row, corrected; new suite rerun is green. Full backend suite pending.
Environment: default uv cache access denied; empty temp cache lacked pinned playwright offline. Reused existing project .venv with UV_NO_SYNC=1, UV_OFFLINE=1, UV_CACHE_DIR in system temp, UV_PROJECT_ENVIRONMENT pointing to existing environment; no dependency installation. pytest's mode-0700 Windows directory creation denies the sandbox access, so verification uses an in-process mkdir-mode harness (511/inherited ACL) and a unique system-temp --basetemp. One early basetemp quoting error created an inaccessible empty directory backend/UsersAdministratorAppDataLocalTempdachapply-372-focused-303af31e-f359-4a08-a6e3-e8c445ddb301; deletion/ACL reset is denied by sandbox. It contains no test code and is explicitly ignored for full-suite discovery. The empty .venv automatically created by the failed uv bootstrap was removed.
Frontend commands: cd frontend; npx tsc --noEmit (blocked: ENOTCACHED, no local node_modules); npm test (blocked: vitest executable unavailable). Both ran offline with npm cache under system temp; 0 tests executed. No frontend files changed.

Exact verification harness (PowerShell, from backend; temporary basetemp is unique per invocation):
$env:UV_CACHE_DIR = Join-Path $env:TEMP 'dachapply-372-uv-cache'
$env:UV_OFFLINE = '1'
$env:UV_NO_SYNC = '1'
$env:UV_PROJECT_ENVIRONMENT = 'C:/Users/Administrator/Backup/Projects/dachapply/.venv'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_ADDOPTS = '--basetemp=' + ((Join-Path $env:TEMP ('dachapply-372-full-' + [guid]::NewGuid())) -replace '\\','/')
uv run python -c "import os,pytest; mkdir=os.mkdir; os.mkdir=lambda path,mode=511,*,dir_fd=None: mkdir(path,511,dir_fd=dir_fd); raise SystemExit(pytest.main(['-q','--tb=line','-p','no:cacheprovider','--ignore=UsersAdministratorAppDataLocalTempdachapply-372-focused-303af31e-f359-4a08-a6e3-e8c445ddb301']))"
New-test rerun uses the same environment/harness with pytest.main(['-q','--tb=line','-p','no:cacheprovider','jobradar/tests/test_error_occurrences.py']): 17 passed. Initial green focused run adds jobradar/tests/test_error_alerting.py and jobradar/tests/test_mailbox_failure_alerts.py: 43 passed. Expanded focused run also adds jobradar/tests/test_application_prep.py and jobradar/tests/test_application_prep_queue.py: 117 passed, 1 failed (documentation assertion corrected as above).
Requested bare `uv run pytest -q --tb=line -p no:cacheprovider <focused files>` could not bootstrap the environment (cache denied / offline dependency absent), then yielded 43 setup errors due to Windows pytest temp ACLs without the harness. Bare full discovery initially stopped with 1 collection error on the accidental inaccessible directory; --ignore above excludes that directory only, not tests.
Frontend exact commands (from frontend): $env:npm_config_cache = Join-Path $env:TEMP 'dachapply-372-npm-cache'; $env:npm_config_offline = 'true'; npx tsc --noEmit; npm test. Both blocked by absent local dependencies (ENOTCACHED / vitest not recognized); no tests ran.

Final validation:
- Complete backend run: 2155 passed, 2 failed, 969 warnings in 944.62s. The mailbox failure was introduced by assuming a persisted pk on a test adapter; fixed the hook to use a fresh occurrence identity if no persisted identity exists. No fixture changes. Final focused run below verifies it passes.
- Remaining process timeout failure: jobradar/tests/test_analysis_time_limit.py::test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit. Reproduced both on changed code and with original HEAD versions of application_prep.py/cv_generator.py loaded in memory (no checkout/reset, no file mutation). The child sleep process is not killed within five seconds in this Windows environment. Left unrelated process-killing implementation unchanged. Full suite was not rerun after the small mailbox identity fix; no all-green full-suite or PERFECT evaluation claim.
- FINAL focused: 63 passed, 0 failed, 9 warnings in 7.14s. Same environment and mkdir harness documented above; exact invocation:
uv run python -c "import os,pytest; mkdir=os.mkdir; os.mkdir=lambda path,mode=511,*,dir_fd=None: mkdir(path,511,dir_fd=dir_fd); raise SystemExit(pytest.main(['-q','--tb=line','-p','no:cacheprovider','jobradar/tests/test_error_occurrences.py','jobradar/tests/test_processing_counts.py','jobradar/tests/test_mailbox_failure_alerts.py','jobradar/tests/test_error_alerting.py']))"
- New collector tests separately: 17 passed, 0 failed. Frontend checks blocked, zero frontend tests executed, as documented above. git diff --check passes.
Baseline proof (same environment, plus DJANGO_SETTINGS_MODULE=config.settings_test; unique system-temp basetemp):
uv run python -c "import os,subprocess,pytest,django; mkdir=os.mkdir; os.mkdir=lambda path,mode=511,*,dir_fd=None: mkdir(path,511,dir_fd=dir_fd); django.setup(); from jobradar.services import application_prep,cv_generator; [(exec(compile(subprocess.check_output(['git','show','HEAD:backend/jobradar/services/'+name+'.py']).decode(),'<baseline '+name+'>','exec'),module.__dict__)) for name,module in [('cv_generator',cv_generator),('application_prep',application_prep)]]; raise SystemExit(pytest.main(['-q','--tb=line','-p','no:cacheprovider','jobradar/tests/test_analysis_time_limit.py::test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit']))"
Baseline result: 1 failed in 7.55s, identical subprocess.TimeoutExpired while waiting for the sleeping child. Initial isolated changed-code repro: 2 passed, 2 failed (timeout + mailbox adapter), before mailbox fix.
No migration, commit, push, branch operation, AC check or status change. No browser/CI/deploy/historical-file adapter, Backlog task creation, or resolution implementation. Azure production remains explicitly unavailable under this documented local-only store design.
<!-- SECTION:NOTES:END -->
