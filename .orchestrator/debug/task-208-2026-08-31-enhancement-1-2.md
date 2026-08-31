# Debug session: TASK-208 status test omitted board metadata
Created: 2026-08-31T14:27:00Z
Session: task-208-2026-08-31-enhancement-1

## Phase 1 — Root Cause

### Error

```text
FAILED test_feedback_due_job_status_patch_removes_closed_lead_and_keeps_actionable_change
assert None == datetime.date(2026, 9, 2)
1 failed, 4 passed
exit code 1
```

### Reproduction

```bash
cd backend
uv run pytest -q jobradar/tests/test_api.py -k feedback_due
```

Environment: Python 3.13 / Django test database. Frequency: 1/1.

### Suspect commits

- Current TASK-208 backend regression, which PATCHed only `{status: rejected}`.
- Existing `JobLeadSerializer.update`, which clears status/feedback dates when moving to a non-active dated status unless the client explicitly supplies status metadata.

### Instrumentation data

- `JobLead.DATED_STATUSES` is `applied`, `interview`, `offer`.
- `JobLeadSerializer.update` clears `status_date` and `feedback_due_date` for a transition outside that set when `status_date` is absent.
- The real board control that TASK-208 is required to reuse does not send status alone: its frontend status vocabulary treats `rejected` as date-bearing and sends `status_date`, preventing that implicit clear.
- The new TASK-208 frontend status handler uses the same board metadata shape; the test did not.

### Hypothesized root cause

The regression exercised a status-only PATCH rather than the board-compatible request shape TASK-208 actually sends, triggering an existing serializer clear that the UI request intentionally avoids. · Confidence: high

## Phase 2 — Pattern

Tests for reused mutation paths must copy the caller's complete request shape, especially when serializer update logic distinguishes omitted fields from explicit values.

## Phase 3 — Impact

No production code failed. The terminal-status row still disappears by the endpoint's actionable-status filter. A separate actionable-to-actionable transition is needed to prove the row remains visible with its new status.

## Phase 4 — Solution

Patch the terminal transition with the same status metadata the frontend sends, and use a separate lead for `interview -> offer` so persistence/removal and actionable visibility are independently asserted.

## Resolution

Updated the regression to send the same status metadata as the UI and split terminal-removal from actionable-to-actionable persistence. Five focused feedback-due backend tests, the full 1,041-test backend suite, and the synthetic browser status/date interaction passed.
