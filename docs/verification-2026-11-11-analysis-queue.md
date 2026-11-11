# TASK-358 / TASK-359 / TASK-360 — verification, 2026-11-11

Verification takeover from Claude. The implementation was already merged in PRs #375 and #380 and deployed; this change records the missing measurements, not a replacement implementation.

Baseline: `origin/main` at `913cb22`. No application source, migration, provider selection, account data, authentication or CI configuration was changed.

## TASK-358: ten real analyses at concurrency five

On the owner's Windows machine, exported ten genuine open-job postings and the owner's Profile inside an explicitly **read-only PostgreSQL transaction**, then copied them into disposable local SQLite and a separate CV workspace. No production rows or real document files were written.

Ran the real `application_prep._pipeline` for all ten jobs, using its normal shared `_lane` limit of five. Discovery, the default provider, prompt builder, strict response validation, evaluation importer and sidecars were real. Wrapped `job_evaluator.run_structured_model` only to count entries/exits and durations; its response was not replaced. Suppressed only follow-on document preparation, because this measurement concerns automatic fit analyses, not another document-generation batch.

| Measurement | Result |
| --- | --- |
| Provider / model / effort | OpenAI Codex / `gpt-6.1-sol` / `high` (existing default) |
| Jobs / successful analyses | 10 / 10 |
| Peak simultaneous provider calls | **5** |
| Batch wall time | 165.33 seconds |
| Individual provider-call duration range | 59.96–91.65 seconds |
| Usage-limit errors / other provider errors | **0 / 0** |
| Whole-host CPU, mean / peak | 16.38% / 43.46% |
| Whole-host RAM, peak used / total | 43.078 / 95.103 GiB |
| Minimum available physical RAM | **52.025 GiB** |
| Resource samples | 163, approximately one second apart |

CPU uses Windows `GetSystemTimes`; memory uses `GlobalMemoryStatusEx`. These are **whole-machine measurements**, including a simultaneously running hermetic backend suite, not CPU/RAM attributable exclusively to this batch. No resource exhaustion or provider-limit failure was observed; five remains a supported default on this machine for this batch. This is not a guarantee against future shared-account quota exhaustion.

Local-model concurrency was not exercised: the existing default selected Codex, not Ollama/LM Studio. No claim is made that a local model can serve five requests at once.

## TASK-360: settings, Finding models, one-time cloud retry

Visible Chrome over CDP, `http://localhost:8011`, real built frontend and real Django routes, using disposable SQLite/workspace. Only the model-discovery block and provider answer were simulated.

1. Profile slider read 5 jobs, minimum 1 / maximum 10. A separate visible-browser persistence check saved 3, reloaded at 3, then restored and reloaded at 5 in the synthetic account. Time limit read 5 minutes.
2. Used keyboard input to change the time limit to 7, clicked **Save profile**, reloaded and observed 7. Restored 5 and verified the API readback.
3. Cleared the model-discovery cache and blocked discovery in an actual pipeline worker. Queue rendered **Finding models**, **0:29 so far**, and the one-time cloud button.
4. Clicked **Use cloud models only this time**. The real action endpoint returned 200; the replacement cloud analysis reached Done in **3.069 seconds**, rather than waiting for the configured timeout.
5. The resulting evaluation was saved locally; the Queue showed `skipped`, fit 40, matching the canned cloud answer. The Profile's `use_cloud_models_only` stayed **false**.
6. Released the abandoned discovery worker. The simulated provider honored its cancellation callback before model entry: only one replacement provider call ran, and the abandoned worker could not overwrite the result.

## TASK-359: short usage-limit line and automatic continuation

Same disposable visible-browser runtime; real generation endpoint, task runner, persistent control store, shared retry timer and task polling. A simulated provider returned the existing parsed usage-limit error. Its reset was accelerated so the existing reset-plus-one-minute scheduler woke approximately 25 seconds later; the scheduler itself was not replaced.

- The panel rendered exactly one line: **Codex limit reached. Continues automatically at 09:01.** (the disposable runtime used UTC).
- No echoed prompt or CLI banner appeared in the panel. **Cancel generation** remained enabled.
- Without a second Generate click, polling observed the **same task ID** change `scheduled → running`; the panel changed to **Generating documents · step 1/5 · 12%**.
- Both generator entries had the identical input fingerprint `22f9bb651e2b06e30b72d634a705c41f29d07e5100b00a1c0730c732b7622783`.
- Cancelled the resumed task through its real panel control; it became `cancelled`.
- Zero browser JavaScript exceptions. This proves the simulated-limit recovery path, not a real quota outage or successful document generation.
- Existing restart-recovery, cancellation, missing-reset and prompt-sanitization tests also passed. Restart recovery was covered by tests, not a live supervisor restart in this browser run.

## Automated gates and localhost

| Command | Result |
| --- | --- |
| `cd backend && ERROR_ALERT_EMAILS='' uv run pytest -q -o faulthandler_timeout=120` | **2,122 passed**, 749.80 seconds |
| Focused analysis-lanes, time-limit, queue, processing-control and reproduced email test | **57 passed**, 30.42 seconds |
| Separate full `test_queue_estimate.py` rerun | **11 passed**, 5.67 seconds |
| `cd frontend && npm test` | **520 passed**, 45 files |
| `cd frontend && npm run build` in development checkout | Passed; includes TypeScript check |
| `npm run build` in owner's dedicated `main-runtime/frontend` checkout | Passed; includes TypeScript check |
| Lint | Explicitly `skip` in project policy; no lint result claimed |

The initial unfiltered backend run timed out after ten minutes. A subsequent fail-fast run exposed an unrelated host configuration leak: the owner's `ERROR_ALERT_EMAILS` caused deliberate test failures to add an alert to the test email outbox. The process-local blank override above removes that external recipient configuration; no assertions, production settings or CI gates were weakened. Root-cause record: [baseline investigation](../.orchestrator/debug/01a1c9b7-takeover-baseline-1.md).

Verified served JavaScript **bytes**, not merely filenames, against each runtime's built `dist` asset:

| Runtime | Bundle | SHA-256 |
| --- | --- | --- |
| Normal owner localhost `:8000` | `index-7gE3REiF.js` | `bd8852babcc7bccf0b45c9045b1c5cfbddf93591a565d615c173131ea10f0862` |
| Disposable verification `:8011` | `index-BMmLK5Nk.js` | `30ca303739374d76a7b29fdad8094b5120627be2efb5dc6df0a422acf5ebab11` |

The separate checkouts' installed toolchains produce different bundles; each served bundle matched its own build and its own `dist/index.html` reference. The normal owner's sign-in page rendered successfully in Chrome with no JavaScript exceptions; its supervisor was not stopped or restarted. The document/build-only takeover does not change runtime source.

Production `/api/health/` returned 200 with `{"status":"ok","database":"ok"}`. The existing production bundle `index-7gE3REiF.js` contains both settings labels, the one-time cloud button and scheduled-task support. Dynamic Finding models / usage-limit text is supplied by the API, so static-string presence alone was not used as evidence for those scenarios. No production deployment or production failure injection was performed.

## Evidence and limitations

Private local artifacts are under `%TEMP%\dachapply-takeover-E40uat\`: `batch/report.json` (all samples/calls/outcomes), `browser/browser-report.json`, `browser/events.jsonl`, five browser screenshots, full test logs and `served-report.json`. The runnable assertion-based harnesses are `batch.py`, `browser_runtime.py`, `browser-check.mjs` and `verify-served.mjs` in the same directory; they are verification tools, not additions to the application. The private job/Profile snapshot is deliberately **not committed**. Temporary artifacts may later be cleaned by Windows; the sanitized measurements above remain versioned.

Harness-only setup corrections: created Django's configured cache table; explicitly bypassed a warm discovery cache to reproduce a stuck lookup; preserved the real provider cancellation boundary; compared bundle references/bytes instead of template newline formatting. None required a product-code fix.

Existing acceptance criteria remain unchanged. Prior mutation-test evidence belongs to the original implementation; this takeover reran the existing suites and did not add or modify tests. Separate takeover rubrics were sealed before these measurements/fixes, not retroactively presented as pre-implementation rubrics for Claude's work.

## Evaluation

Separate sealed takeover rubrics: **TASK-358 PERFECT, TASK-359 PERFECT, TASK-360 PERFECT** — each seven explicit acceptance criteria plus the measured-claims floor passed. The evaluator rechecked raw batch outcomes/samples, browser events/input fingerprints, served-byte hashes and test logs, rather than accepting a worker's success summary.

**Self-graded: the criteria and these verdicts share an author.** These verification-only rubrics were sealed before new measurements but after Claude's existing implementation; they are not represented as independent pre-implementation grading. Repeated PERFECT results here do not establish sensitivity to future defects. A separate `codex review --commit` returned no findings and confirmed the evidence/limitations; it did not implement changes or rerun suites.

Merge disposition is recorded in the Backlog task notes; tasks remain In Progress until the evidence merge, then their completion is merged separately.
