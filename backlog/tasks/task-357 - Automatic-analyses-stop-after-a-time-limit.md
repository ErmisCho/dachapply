---
id: TASK-357
title: Automatic analyses stop after a time limit
status: Done
assignee: []
created_date: '2026-11-09 16:10'
labels:
  - owner-request
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-11-09: "why so many jobs are waiting to analyse" -> "yes, there should be a time limit".

Measured on the local runtime (`%LOCALAPPDATA%\dachapply\dashboard\processing.sqlite3`, read-only): one
`pipeline` unit (job 1427, a re-analysis) has been `running` since 2026-11-08 13:40Z with no completion
or failure in `execution.log`, and the runtime process has not restarted since 2026-11-06. Analyses run
one at a time (`_pipeline_lock` plus the one-running-`pipeline` claim in `processing_control`), so 19
`pipeline` units queued behind it (9 on 11-08, 10 on 11-09) never ran. The daily budget is stamped at
queue time, so about 10 more pile up each day.

Cause in code: both automatic model calls run with no deadline. `job_evaluator.evaluate_jobs` is called
from `application_prep._pipeline` without `cancelled=`, and the requirements analysis calls
`run_structured_model(...)` without `cancelled=`. `cv_generator._run_command` only enforces a deadline
or kills the process tree when given a `cancelled` callback (or a timeout). Posting fetches already
have their own limits (`TIMEOUT_SECONDS = 10`, `RENDER_SECONDS = 20`).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The automatic fit analysis (`application_prep._pipeline`) and the application-requirements analysis stop their model call once the run has taken longer than one named limit of 10 minutes, through the existing `cancelled` hook, so the model's process tree is killed rather than left running.
- [x] #2 A run that hits the limit ends as failed: the job's Queue entry shows a reason that names the time limit (e.g. "stopped after 10 minutes") with Retry offered, never a run left at Waiting/Analysing.
- [x] #3 After a timed-out run, `_pipeline_lock` is free and the next queued analysis starts: a test runs two jobs where the first one's model call never returns on its own, and the second job's analysis completes.
- [x] #4 A test proves a real subprocess that outlives the limit is killed (not merely abandoned) by the analysis path, with the limit patched to a fraction of a second so the test takes seconds.
- [x] #5 Analyses that finish inside the limit behave exactly as before; the full backend suite (`cd backend && uv run pytest -q`) passes.
- [x] #7 Every other backend `subprocess.run(..., capture_output=True, timeout=...)` (or equivalent pipe capture with a timeout) that runs a CLI able to leave a background process is listed in the notes with a verdict, and any that can hang the same way is fixed the same way.
- [x] #6 Model discovery (`cv_generator._discover_model_options`: `ollama list`, `ollama show`, `lms ls`) never blocks indefinitely when the CLI leaves a background process holding its output pipe: a test with a real child that spawns a long-lived grandchild inheriting stdout proves discovery returns within seconds.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Immediate unblock for the owner (not this task's code): Stop, Start, Resume on http://localhost marks the
stuck unit interrupted and lets the queued ones run.

Root cause, measured 2026-11-09 with `py-spy dump` on the live runtime (worker pid 46856): the stuck thread
is not in the analysis at all. Stack: `Thread.join` <- `Popen._communicate` <- `subprocess.run` <-
`_discover_model_options` (cv_generator.py:228, `ollama list`, timeout=2) <- `available_model_options` <-
`_pipeline` (application_prep.py:534). Two `_readerthread`s alive, no child process. On Windows,
`subprocess.run` kills the child on timeout and then waits for the pipes with no timeout; a background
process the CLI started holds the inherited pipe, so it never returns. The first premise above ("the model
call has no deadline") was true but not this hang's cause; AC #6 added for the real one.

How this is prevented from happening again (owner asked, 2026-11-09):
1. Root cause removed (AC #6): model discovery can no longer wait forever on a pipe a background process holds.
2. Same trap closed everywhere (AC #7): every other piped subprocess call with a timeout is audited, not only the one that hung.
3. Backstop (AC #1-#3): whatever blocks next, an automatic analysis ends after 10 minutes as failed with Retry, and the queue moves on.
4. Regression tests (AC #4, #5, #6): the exact trap (child leaves a grandchild holding stdout) and a non-subprocess block are reproduced in the suite, and each test was shown to fail without the fix.
5. Diagnosis recipe for next time: `uvx --from py-spy py-spy dump --pid <worker pid>` shows the stuck thread's stack in seconds; it found this cause after code-reading alone did not.

Known follow-up, not in this task: the dashboard's Stop drains until no unit is running, so a stuck unit makes Stop hang at "stopping" (which also refuses writes). With the 10-minute limit a stuck analysis can no longer cause that, but a bounded drain would be its own task.

Immediate recovery done 2026-11-09: the runtime tree (pid 68276) was ended with the owner's approval; the watchdog restarts it and `recover()` marks the stuck unit interrupted.

What was built (2026-11-09):
- `application_prep._bounded(work)`: runs `work(cancelled)` in a daemon thread, waits `ANALYSIS_TIME_LIMIT = 600`
  s, then sets `cancelled` and raises `GenerationCancelled`. The caller alone records the outcome, so
  `_pipeline_lock` and the durable unit are released. Fit analysis: fetch, model discovery and
  `evaluate_jobs(cancelled=)` all inside. Requirements: `_bounded(partial(_analyse, job))`.
- Wording: "Analysis failed: Stopped after 10 minutes, the time limit for one analysis. Press Retry." and
  "Requirements analysis failed: ... Press Prepare to retry." Not transient (no automatic retry): a run this
  slow is likely slow again, and a retry would spend another 10 minutes of the one lane.
- `cv_generator._discovery_run`: `ollama list` / `ollama show` / `lms ls` write stdout to a temp file, not
  a pipe. Measured: the old shape (`capture_output=True, timeout=2`) returned after 15.1 s, when a
  leftover child holding the pipe exited; never if it never does.
- `evaluate_jobs` re-checks `cancelled` before committing (from Codex review: an answer that arrives in
  time followed by a slow preview could otherwise save after the failure was recorded).

Audit (AC #7):
| Call | Hangs the same way? | Action |
|---|---|---|
| `draft_chat._run` (codex/claude CLI, timeout) | Yes: run() kills only the .cmd shim | via `_run_command`, which now kills the tree on timeout |
| `mailbox_ai._run` (codex CLI, timeout) | Yes | same |
| `pdfinfo` x2, `pdftoppm` | No: no background process | unchanged |
| `taskkill` in `_stop_process` | No timeout, no background | unchanged |
| `interview_coach` `curl --max-time` | No | unchanged |
| pdflatex via `_run_command` | Already polled with `cancelled` | unchanged |

Follow-ups, not done here: the owner's manual "Analyse with model" calls `run_structured_model` with no
limit; on Linux `_stop_process` kills only the direct child (pre-existing).

Out of scope: the owner's manual "Analyse with model" from the board, and document generation, which
have their own cancel paths.
2026-11-10: deployed to production in image 64812d1 (health ok). Done.
<!-- SECTION:NOTES:END -->
