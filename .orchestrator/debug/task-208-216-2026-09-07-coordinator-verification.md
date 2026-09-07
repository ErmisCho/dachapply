# Coordinator verification — TASK-208 / TASK-216 (2026-09-07)

Both implementations were already merged into `origin/main` (TASK-208 = `131ea48`, TASK-216 = `e144e4e`)
by an earlier session; local `main` was 17 commits behind and was fast-forwarded before verifying.
Neither task had been closed. This pass is TW-003/TW-004: re-measure the load-bearing claims
independently rather than trusting the implementers' notes.

Runtime under test: `C:/Users/Administrator/AppData/Local/dachapply/main-runtime` at `e144e4e`
(Django `127.0.0.1:8000` redirects to the Vite dev server on `5173`, per TASK-205).

## TASK-216 — popup geometry, measured in Chrome

`GET /api/jobs/{id}/cv-generation/` was shimmed to resolve 6s late (read-only endpoint; nothing written).
The compact popup was opened from the board and its `getBoundingClientRect()` sampled 41 times over 10.0s
with a detached `setTimeout` sampler — `requestAnimationFrame` never fires in the automated tab, which is
what made a first attempt time out.

| observation | value |
| --- | --- |
| mount (MutationObserver, first frame with the dialog present) | 68.1 ms |
| geometry at mount | 704 x 1312 at (225.14, 329) |
| geometry at t = 9999.7 ms | 704 x 1312 at (225.14, 329) |
| max delta over 41 samples | dx 0, dy 0, dw 0, dh 0 |
| distinct sizes observed | 1 (`704x1312`) |
| delayed fetches actually intercepted | 1 |

Rubric criteria 1, 2, 3 and 5 are satisfied by measurement, not by reading the stylesheet.
Note that `frontend/src/cvPopup.test.tsx` only pins the `h-[80vh]` class in static SSR markup — it
asserts the class, not the box. The browser measurement above is what actually closes criteria 1/2/5.

## TASK-208 — feedback pane, measured in the live DOM

Read-only probe of the FEEDBACK DEADLINES pane on the running board (no owner data was mutated;
a status write would have created a real audit note on a real lead, so the mutation path is covered
by synthetic tests instead):

- 2 rows rendered, each with 1 `input[type=date]` (reschedule) and 1 `select` (status).
- Each `select` carries a per-lead `aria-label` (`Change status for <company> — <title>`).
- Each offers 11 options: new, reviewed, to_apply, applied, interview, offer, accepted, rejected,
  withdrawn, skipped, archived — identical to `JobLead.STATUSES` in `backend/jobradar/models.py`.

AC1-AC4 verified TRUE with file:line evidence by an independent audit and spot-checked here.

## TASK-208 AC5 — NOT satisfied

AC5: "Synthetic backend/frontend regressions cover reschedule plus status changes without using owner data."

Synthetic: yes. Coverage: no. Confirmed by direct grep, not by agent report:

- `Dashboard` in `frontend/src/App.tsx` is **not exported** (only `DashboardPanel` is), so no test can
  render it. Verified: `grep -o 'export function Dashboard[A-Za-z]*'` yields only `DashboardPanel`.
- `changeFeedbackStatus`, `rescheduleFeedback`, `loadFeedbackDuePanel` and `feedbackDueActionErr`
  appear in **zero** test files.

The existing tests hit the two ends and skip the middle: `feedbackDueControls.test.tsx` proves the row's
callbacks fire and that `updateFeedbackDueJob` returns `{updated:null,error}` on rejection, and
`test_api.py` proves the endpoint filters correctly. Nothing exercises the code that builds the PATCH
body or reacts to its outcome. Concretely, all 7 frontend and 6 backend tests stay green if you:

1. replace `onStatusChange={status=>changeFeedbackStatus(r,status)}` with a no-op;
2. drop `status_date` / `interview_stage` from the body `changeFeedbackStatus` builds;
3. delete `await loadFeedbackDuePanel()` from either handler (pane never refreshes);
4. delete `<ErrorBox error={feedbackDueActionErr}/>` (failures become silent).

Also: no backend test ever PATCHes `feedback_due_date`, so the reschedule half of AC5 has no backend
coverage at all. `test_api.py` asserts the date is *preserved* by a status patch, which passes just as
happily if the field became read-only.

AC5 stays unchecked until these are closed. AC1-AC4 are checked.

## Pre-existing follow-ups found, not in TASK-208's scope

- `frontend/src/App.tsx` reschedule input uses `defaultValue`, so a rejected date stays on screen
  (the error banner and the Due badge still show the truth, so the pane does not read as success).
- `loadFeedbackDuePanel` swallows a failed refresh with `catch{setFeedbackDueRows([])}`, rendering
  "No actionable job has a feedback deadline right now." — an affirmative false statement — with no
  error shown. Predates this task (TASK-146).
- The 11-status list is hand-mirrored in `frontend/src/App.tsx` and `backend/jobradar/models.py` with
  no parity test. They agree today, string for string.
