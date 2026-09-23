---
id: TASK-246
title: Paste the ChatGPT response where the prompt was copied
status: To Do
assignee: []
created_date: '2026-09-22 21:19'
updated_date: '2026-09-23 06:53'
labels:
  - frontend
  - ux
dependencies: []
priority: high
type: enhancement
ordinal: 245000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-09-22, with a screenshot of the intake page after saving a job.

The 'Job saved' panel currently ends the flow: it copies the analysis prompt and offers 'Copy prompt again' and 'Open dashboard'. The user then has to leave for the dedicated import page to paste ChatGPT's JSON back, which is where the round trip actually completes. The owner wants that same window here - paste the output, validate, import - so the intake page is one loop instead of a handoff.

The implementation already exists and should be reused rather than rebuilt: ImportEval (App.tsx:684) posts to /evaluations/import/ and renders ImportResultSummary, and DuplicateResolver (App.tsx:681) handles the collision case. The job detail page already embeds the same pair inline for its calibration flow, so there is a precedent for using it outside its own page. The risk this task exists to avoid is a third copy of that logic drifting from the other two.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 On the job intake page, the panel that hands over the prompt also accepts the response: a paste box and an import control, without navigating away
- [x] #2 Importing there produces the same result summary the dedicated import page produces - created/updated/skipped counts and per-job lines - and the same duplicate-resolution path when the response collides with existing jobs
- [x] #3 The behaviour is one implementation used in both places, not a second copy that can drift from /import
- [x] #4 Errors are reported as they are on the import page: invalid JSON, a response that parses but carries nothing importable, and a server rejection are distinguishable
- [x] #5 Covered by a frontend regression check, and verified in the running app by importing a real response on the intake page
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Verified live by the coordinator (TW-003/TW-004)

Driven in a browser against a scratch sqlite database, never production. Backend on :8001, Vite on
:5199, logged in through the product's own demo button.

    save a job on /add -> 'Job saved' panel renders 'Paste ChatGPT's answer'
    paste an evaluation JSON, press Validate and Import
      URL after import       /add                      -- never navigated (AC1)
      panel result           'Import successful -- 1 job found and imported.
                              Probe GmbH - Backend Engineer Probe position'  (AC2)
      job's evaluation       fit 78, recommendation apply -- the round trip really completed (AC5)
      job count              9 -> 9                    -- no re-submit (the type=button fix)
      backend log            one POST /api/evaluations/import/

Anti-drift re-counted from source rather than accepted: `api('/evaluations/import/'` appears 4 times
on this branch and 4 times on main -- zero added -- and `<ImportPaste` appears exactly twice (AC3).

Gates: npx tsc --noEmit clean, npm test 290 passed in 18 files.

## Two corrections to the implementing agent's report

- It reported the baseline as 279 in 18 files. That is the task-244 branch's count. main is **275 in
  17**, and 290 = 275 + its 15. The agent flagged the discrepancy itself rather than quietly adopting
  my number, which is the right instinct.
- A first attempt at this verification pasted the payload into the wrong textarea -- the job URL box,
  whose placeholder also begins 'Paste ...' -- and the import silently did nothing, because the real
  box was empty. The backend log is what caught it: no POST had been made. Retargeted on the
  aria-label the agent added (`Paste ChatGPT JSON`), which is also the reason that label is worth
  having.

## Public mode

The agent checked rather than assumed: `views.import_eval` carries no AllowAny, unlike its neighbour
`public_submit`, so DRF's default IsAuthenticated rejects a logged-out visitor. No import control is
rendered in public mode, and a test pins that it appears only outside the public branch.

## Known remaining drift, not introduced here

The dashboard prompt modal is a fourth paste-and-import with extra behaviour of its own (auto-import
on paste, board refresh, a success event). Out of this task's territory and left alone; worth its own
task if the duplication ever bites.

## AC4 measured at the API, the layer those strings come from

The three failure modes are distinct, so the UI can tell them apart (it renders the server's message
through ErrorBox):

    invalid JSON                  400  'Invalid JSON on line 1, column 2: Expecting property name ...'
    parses but nothing importable 400  'Root must contain jobs, new_jobs, or job_updates list'
    wrong shape                   400  'Root must contain evaluations list'
    valid, re-imported            400  type evaluation_conflicts -> the duplicate/override resolver

That last line is worth keeping: re-running the same payload lands on the conflict path rather than
silently double-importing, which is the resolver AC2 asks for.

## What was NOT driven live, named rather than glossed

Chrome stopped responding partway through this verification, so the /import page itself was not
re-driven after the extraction. It renders the same ImportPaste instance as the intake panel -- the
tests pin that it kept no state, no textarea and no import POST of its own, and the endpoint behaviour
above is shared by both call sites -- but that is structural evidence, not a live click. Worth ten
seconds the next time the app is open: load /import, paste anything invalid, confirm the message
still appears there.
<!-- SECTION:NOTES:END -->
