# Private document benchmarks

<!-- TASK-370 -->
Fixtures contain private postings, profile/CV evidence, templates and possibly a photograph.
Keep fixtures and results outside every git checkout. Do not publish them. Commands print counts
and paths only. Export uses owner-scoped SELECTs inside a transaction that is rolled back;
it does not invoke model discovery or generation. Existing stored assets take precedence over
workspace assets, exactly as in the generator. Only the newest base CVs, configured letter
templates, photograph, evidence and adaptation rules are copied, never generated files/caches.

Run from `backend` in PowerShell. Choose a fresh directory under the system temp directory:

```powershell
$fixture = Join-Path $env:TEMP 'dachapply-fixture-370'
$env:DACHAPPLY_ALLOW_PROD_DB = '1'
uv run python manage.py benchmark_export --email owner@example.com --jobs 6 --out $fixture
# Explicit IDs instead: --jobs 12,34,56 (one explicit ID: --jobs ids:12).
```

When the owner keeps evidence in the file fallback (not pasted in settings), run the export from the checkout that holds that file, or set `DACHAPPLY_SOURCE_REPO` to it; otherwise the fixture has no evidence and every job blocks with "Candidate evidence is empty".

Export reads the currently configured DB. No real model calls occur during export. For the
benchmark, clear DATABASE_URL and use a NEW scratch sqlite database for EACH run. Never use
the owner's DB or workspace. Install the usual local generation tools (including TeX/pdfinfo)
and authenticate the provider before running. These runs make real, potentially paid calls.

```powershell
$env:DATABASE_URL = ''
$env:DACHAPPLY_ALLOW_PROD_DB = ''
$env:DB_NAME = Join-Path $env:TEMP 'dachapply-benchmark-370-one.sqlite3'
uv run python manage.py migrate --noinput
uv run python manage.py createcachetable
uv run python manage.py benchmark_run --fixture $fixture --experiment concurrency --workers 1 --out (Join-Path $env:TEMP 'dachapply-results-370-one')

$env:DB_NAME = Join-Path $env:TEMP 'dachapply-benchmark-370-two.sqlite3'
uv run python manage.py migrate --noinput
uv run python manage.py createcachetable
uv run python manage.py benchmark_run --fixture $fixture --experiment concurrency --workers 2 --out (Join-Path $env:TEMP 'dachapply-results-370-two')
```

Each run copies input files to a fresh `dachapply-benchmark-*` system-temp workspace and keeps
it for review. `results.json` contains its path, source-to-scratch job IDs, exported document
limit, model/effort/speed conditions, request start/end and failure classes, repairs, document
paths/hashes/pages, queue outcomes and CPU seconds/RSS samples every two seconds (including
live child processes; `unavailable` when psutil is absent). `summary.md` reports first useful
package, total elapsed time and documents/minute. A useful package has a ready CV and its
language's recommended wanted letter/message; alternative templates still finish and count
toward total completion. Times use the queue's durable finish timestamps. Blocked jobs are errors.

The experiment uses the real preparation queue and generator, retaining every variant and the
same model/effort; it refuses a fallback model. Provider quota retry timestamps, cancellation
and queue gates are retained; a run stops measuring once all currently runnable work finishes,
and reports scheduled retries as errors rather than waiting for a provider reset. It does not
invoke the daily scheduler or change daily budgets. Exported daily settings remain in the profile.
The queue override lasts for this run only. No default is raised.

Compare matched workloads manually for factual accuracy, language, page/layout quality and
all letter alternatives. Include mixed-language/same-job variants and jobs with identical
company/title to stress shared TeX compilation and filename collisions. The overwrite check
requires unique paths, unchanged final hashes, temp-workspace containment and matching job/user
preparation claims. Inspect CPU/RAM peaks and provider-limit/failure/cancellation counts; reject
two workers if resource pressure or errors increase or useful-package latency does not improve.
Keep the current default until measured benefit and quality/data-safety review support a change.

`jobradar.services.benchmark.EXPERIMENTS` maps names to functions accepting
`(jobs, user, workers, variant)` and returning preparation states in job order. TASK-368/369 can
add modes using the same fixture, request recorder and results contract; no modes for those
experiments are implemented here. `--variant` is reserved for those modes.
