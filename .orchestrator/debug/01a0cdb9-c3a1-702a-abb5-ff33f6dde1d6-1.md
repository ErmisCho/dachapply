# Debug session: ChatGPT JSON import returns HTTP 500
Created: 2026-09-23T10:11:00Z
Session: 01a0cdb9-c3a1-702a-abb5-ff33f6dde1d6

## Phase 1 — Root Cause

### Error
UI, verbatim: `The server encountered an error. Please try again.`

Server error recorded with the supplied payload: `django.db.utils.DataError: value too long for type character varying(250)`
HTTP status: `500`.

### Reproduction
The reported JSON was measured field-by-field with:
`cd backend && uv run python - <<'PY' ... print(key, len(value)) ... PY`

Environment: Windows 10; local Django runtime at `http://caren:8000`; production PostgreSQL behind the local runtime; hermetic tests use sqlite.
Frequency: always for this payload against the pre-migration PostgreSQL schema.

Actual bounded values from the supplied JSON:
- `source`: 92 / 120
- `salary_info`: 204 / 250
- `language_requirements`: 255 / 250 (over by 5)

### Suspect commits
No recent commit introduced the value: `language_requirements` has been `CharField(max_length=250)` since `backend/jobradar/migrations/0001_initial.py`; recent log contains no importer-length fix.

### Instrumentation data
- `views.import_eval` passes the JSON directly to `import_any_json` and has no exception boundary.
- `import_jobs_data` writes `language_requirements` into `JobLead` without model validation.
- PostgreSQL enforces `varchar(250)` and raises `DataError`; sqlite does not enforce the declared varchar length.
- `git show HEAD:backend/jobradar/models.py` confirms the shipped limit is 250.
- The reported payload also contains two `:contentReference[oaicite:N]{index=N}` artifacts inside `risk_notes`.

### Hypothesized root cause
A valid 255-character prose answer is written unchecked into `JobLead.language_requirements`, whose shipped PostgreSQL column is `varchar(250)`, so the database exception escapes as HTTP 500. · Confidence: high

## Phase 2 — Pattern

This is a trust-boundary/schema mismatch: LLM-generated prose is stored in short varchar columns, while sqlite hides overflows that PostgreSQL enforces. The same unchecked path writes company, title, location, URL, source, and salary information. No existing regression test covers one character beyond a model field limit. The citation markers are a second recurring LLM-output artifact at the same import boundary.

## Phase 3 — Impact

Affected files:
- `backend/jobradar/models.py`
- `backend/jobradar/migrations/0052_widen_job_text_fields.py`
- `backend/jobradar/services/json_importer.py`
- focused importer/API tests

Callers: `views.import_eval` calls `import_any_json`; all job import shapes route through `import_jobs_data`. Evaluation-only imports route through `import_evaluations` and need the same citation cleanup.

## Phase 4 — Solution

Store `salary_info` and `language_requirements` as text, widen the still-label-like `source`, validate all remaining bounded imported `JobLead` fields in Python before writes, and strip known citation artifacts at the shared import boundary. Add one over-limit endpoint regression plus focused acceptance tests for the reported prose and citation shape.

## Resolution

Pending implementation and verification.
