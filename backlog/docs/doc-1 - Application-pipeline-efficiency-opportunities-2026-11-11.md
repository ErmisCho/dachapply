---
id: doc-1
title: Application pipeline efficiency opportunities - 2026-11-11
type: other
created_date: '2026-11-11 14:54'
updated_date: '2026-11-11 15:28'
---
# Application pipeline: spend less work to reach useful applications sooner

Read-only, targeted investigation on 2026-11-11. The three approved quality improvements are tracked separately as TASK-364 (test isolation), TASK-365 (PR production build), and TASK-366 (repeatable browser recovery checks). Those tasks remain To Do; no application or CI implementation was performed.

## Measured baseline

Source: the existing private local `C:/latex/.dachapply-cache/cv-benchmarks.jsonl`, read without modification. It contained 665 valid records; the latest recorded timestamp was 2026-11-11T07:48:45.656Z. No prompts, candidate data, task IDs or error details are reproduced here.

For each route below, use the most recent 20 successful, uncached `gpt-6.1-sol` records, not all-time averages:

| Route | Effort in sample | Median recorded elapsed |
| --- | --- | --- |
| Fit analysis | 20 high | 81.00 s |
| Requirements analysis | 20 high | 15.59 s |
| Generation | 20 high | 139.57 s |
| Revision | 12 high / 8 medium | 67.73 s |

Generation sample mix: 17 CV-only, 2 letter-only, 1 combined. Within that mixed sample, median model-generation stage was 123.97 s; median CV-compilation stage was 1.56 s. These mixed historical samples are not controlled comparisons between document mixes or effort levels. End-to-end recorded task time may include waiting, so stage medians must not be added or treated as a causal speedup estimate.

Of the last 50 uncached default-model generation records, 49 were ready and one failed for a usage limit. This is recorded task completion, not a content-quality score; it does not prove factual accuracy or readiness without review.

The document-worker code default is 1 (`backend/config/settings.py:159`); the repository-root `.env` had no `PREP_QUEUE_CONCURRENCY` override. The active supervisor's inherited environment was not inspected, so its live limit is not asserted. Analysis concurrency was separately measured at five in TASK-358; that does not validate five concurrent document generations.

## Ranked opportunities, not implemented fixes

### 1. Optimize time to a reviewable package, not completion of every alternative

`application_prep.prepare` appends every variant of one job to the shared FIFO; `_pump` takes the front entry. Consequently, that job's extra letter variants can be ahead of another job's first useful package. Benchmark package-aware scheduling: prioritize a CV plus a usable recommended letter across jobs before fallback variants, while preserving explicit owner Move-to-front actions, cancellation, daily limits and eventual generation of every requested alternative.

Do not remove alternatives: TASK-348 explicitly requires every applicable letter option. Measure time until the first/next reviewable application and overall batch completion; these are different objectives. A scheduling change alone does not reduce total model work.

### 2. Avoid reading the same posting in separate model requests where quality permits

The automatic pipeline calls `job_evaluator.evaluate_jobs` for fit; an apply/maybe import calls preparation. When requirements are absent, `application_prep._analyse` starts a separate requirements model request. Consider one validated response carrying both fit and requirements; existing combined-import prompt/schema concepts already exist in `prompt_builder.py`. Preserve missing-text handling, quote validation, skip behavior, owner-edited requirements and per-job failure isolation.

Automatic `_start` also launches a CV or a letter as separate tasks, while `cv_generator.generate_cv_package` already supports generating both together. Benchmark a combined recommended CV+letter package versus the separate path, keeping fallback letters and independently usable successful artifacts. Neither fewer requests nor the existing one combined timing sample proves a latency/quality win by itself.

### 3. Measure the document bottleneck before raising analysis concurrency again

The generation model stage is a much larger measured cost than LaTeX compilation. Check the live document-worker limit first, then compare one versus two concurrent document jobs on the same small labelled workload. Count provider-limit errors, model calls, time to useful package, repairs and manual corrections. Retain the current default unless the measured benefit and quality justify a change. The fit-only concurrency-five experiment is not a document-load test.

### 4. Avoid repeated unsuccessful posting retrieval

`posting_fetch.fetch_missing_sources` revisits thin/incomplete postings on each analysis, and `cv_tasks._retry_missing_source` can fetch again before individual document variants when usable original text is still absent. The existing `source_checked_at`/fetch-error fields provide a possible freshness signal. Measure duplicate fetches, then consider bounded retry/cooldown and shared per-job retrieval, with explicit manual Retry/Refresh still available and changed postings invalidating old results. Keep SSRF checks and owner text-choice protections intact.

## Effectiveness and experiment order

Track usable, accepted application packages per unit of model work, not merely jobs analysed or documents produced. Include wrong-language results, missing required documents, factual overclaims, repair attempts and owner readjustments. Existing timing telemetry alone does not measure those quality outcomes.

Recommended order: establish first-package latency and call counts; test package-aware scheduling and existing combined-generation capability; then assess fit+requirements consolidation and modest document concurrency. Preserve the owner's TASK-303 default of GPT-6.1-Sol/high until a labelled quality comparison supports changing it. Do not lower effort or raise concurrency simply because it looks cheaper.

No paid model calls, new real workload, production writes or pipeline configuration changes were made for this investigation. The opportunities above need owner selection and controlled verification before implementation; no percentage speedup is claimed.


## Tracked follow-up work

- TASK-367: useful application packages before fallback variants.
- TASK-368: benchmark fit plus requirements in fewer requests.
- TASK-369: benchmark a combined recommended CV and letter request.
- TASK-370: measure safe document concurrency independently of fit concurrency.
- TASK-371: avoid repeated unsuccessful posting fetches.

## Error evidence to future Backlog bugs

TASK-372 is the high-priority error-feedback feature, delivered as TASK-372.1 (durable private capture/redaction), TASK-372.2 (incremental unresolved-only grouping and Backlog linkage), and TASK-372.3 (verified resolution, old-evidence suppression and regression detection).

Lifecycle: capture occurrence -> triage/group -> link bug task -> verify fix -> complete bug task -> mark linked occurrence IDs resolved. Resolved occurrences remain auditable but are not analysed again, including after restart or old-log replay. A genuinely new post-fix occurrence is not silently discarded: it is handled as a regression, distinguished from the same failure on an unfixed old build. New arrivals during closure must not be bulk-marked done.

This extends existing alerting and private adjustment/compile evidence, not another logging framework. Technical summaries are sanitized before shared/public Backlog; sensitive raw evidence stays owner-only and outside git. Operational quota/transient failures are classified without creating a bug for every log line. No new always-running paid-agent loop or error dashboard is requested.

All these records are To Do. The collector/triage/resolution feature is not implemented or running yet.
