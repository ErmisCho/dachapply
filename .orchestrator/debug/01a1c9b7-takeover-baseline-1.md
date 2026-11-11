# Debug session: host configuration contaminates backend baseline
Created: 2026-11-11
Session: 01a1c9b7-26c3-7492-a252-735314e098f5

## Phase 1 — Root Cause

### Error
`uv run pytest -q` timed out at 600 seconds with two failures already reported. Focused reproduction `uv run pytest -q -x` exited 1 after 251 passed, 1 failed in 144.35 seconds.

`jobradar/tests/test_api.py::test_one_failing_send_does_not_stop_the_rest_of_the_batch`:
```
assert [m.to for m in mail.outbox]==[['digest@example.test']]
AssertionError: the actual outbox contains the expected digest plus one owner alert.
```
Personal recipient details are intentionally excluded from this artifact; the original assertion is in the local temporary backend-first-failure.log.

### Reproduction
Windows, Python 3.13, owner checkout, inherited repository .env. Test injects SMTP failure and logs it. config/settings.py:690 reads ERROR_ALERT_EMAILS from owner .env; :780 configures AdminEmailHandler. Test overrides mail backend to locmem but not ADMINS. Its intentional ERROR therefore adds an owner-alert email to the asserted outbox.

### Suspect commits
No changes to application code in this session. Current branch starts at origin/main 913cb22; failure exists before fixes or browser measurements.

### Instrumentation data
Observed an extra alert recipient in mail.outbox, and the failing test's captured log confirms an intentional OSError('SMTP 550 mailbox unavailable'). Source confirms environment-derived ADMINS and jobradar logger's mail_admins handler.

### Hypothesized root cause
Host ERROR_ALERT_EMAILS leaks into the otherwise hermetic tests and adds logging emails to mail.outbox. Confidence: high, confirmed by the environment-only rerun.

## Phase 2 — Pattern
Environment contamination, not an analysis/retry regression. settings_test.py clears Gmail and database credentials but does not clear owner alert recipients. No task-scope production fix is proposed.

## Phase 3 — Impact
Impacts error-path email assertions throughout backend tests. No effect on TASK-358/359/360 implementation. Owner production logging must remain enabled.

## Phase 4 — Solution
Rerun the exact failing test with process-local ERROR_ALERT_EMAILS='' before deciding whether any repository fix is necessary. Then run unfiltered full suite with the same explicit environment isolation and a long enough execution window. Do not modify production settings or weaken assertions.

## Resolution
The exact failing test plus focused task coverage passed with process-local ERROR_ALERT_EMAILS='' (57 passed in 30.42 seconds). The unfiltered complete suite with that same environment isolation passed: 2122 tests in 749.80 seconds. No source files or test assertions changed; production alert configuration is untouched.

Separate browser-harness setup errors were also resolved without product changes: a new disposable SQLite database required `createcachetable`; a warm model-discovery cache prevented the first stuck-lookup injection, so the harness clears it before starting that scenario; the canned model must honor cancellation before recording an entry, just as the real shared runner does. Final browser run passed after those corrections. Served-index checks compare bundle references and exact JavaScript bytes rather than CRLF/LF template formatting. Static production checks use literal settings/button labels, not API-provided dynamic stage/error text.
