---
id: TASK-237
title: Use the real job-posting text in CV and letter generation
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-14 14:40'
updated_date: '2026-09-17 14:01'
labels:
  - frontend
  - backend
  - data
  - ai
dependencies:
  - TASK-226
priority: high
type: bug
ordinal: 236000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The source-text preview used during CV and motivation-letter generation can show text that is not the actual posting at the job's original URL. Restore a trustworthy source-of-truth path so the user can inspect the real posting text before generation and the generator receives that same text. This is a regression/follow-up to TASK-30 and TASK-32. Start only after the currently active TASK-226 is complete.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 For a job whose stored summary differs from its original URL, the generation flow shows the actual full posting body rather than a summary, evaluation, rewritten description, or URL placeholder
- [x] #2 CV and letter generation receive the same full posting text shown to the user
- [x] #3 An inaccessible or expired original URL is reported honestly; the UI does not label synthetic or summarized text as the real posting
- [x] #4 Existing jobs with intentionally corrected source text and jobs without a URL continue to work
- [x] #5 A regression check covers a posting whose actual body differs from its stored summary
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Execute through the session-orchestrator workflow after TASK-226 is complete
- [ ] #2 Pre-register task-specific Asian Dad criteria before implementation and receive PERFECT after the required quality gates
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Trace the real path first: JobLead.source_text = original_source_text or raw_description (models.py:278); cv_generator._prompt embeds it (cv_generator.py:926); original_source_text is only ever filled from ChatGPT-collected JSON whose prompt ASKS the model to open the URL (prompt_builder.py:62,78,94) and nothing verifies it did. That unverified hop is the regression.
2. Add a stdlib-only server-side fetch of the job's own URL (urllib + html.parser, no new dependency) behind an SSRF guard: http(s) only, refuse loopback/private/link-local/reserved resolved addresses, revalidate every redirect hop, hard timeout and 2 MB read cap.
3. Expose it read-only as GET /api/jobs/<id>/source-text/live/ - it never writes; adoption stays the existing explicit PATCH /api/jobs/<id>/source-text/, so hand-corrected text is never overwritten silently (AC4).
4. Carry provenance in the generation payload: generation_preview gains job {url, source_text, source_chars, source_is_fallback} so the flow can label stored text honestly instead of presenting it as the posting (AC3).
5. Frontend: one pure exported PostingSource component used by BOTH generation surfaces (the single CvGenerator, which shows no source text at all today, and BatchCvGenerator), showing stored text with provenance, a fetch control, the fetched body in its own labelled pane, and the server's failure reason verbatim.
6. Hermetic regression tests (patched sockets, never the network) for a posting whose body differs from its stored summary, for each honest-failure shape, for the no-write property, and for the SSRF guard including a redirect into a private address.
7. Coordinator verifies in a browser against a scratch database (AC1/AC2 cannot be proved from code), grades against the rubric sealed before implementation, then commits, pushes and opens the PR.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## What was actually wrong, traced before any code

`JobLead.source_text` = `original_source_text or raw_description` (models.py:278) and
`cv_generator._prompt` embeds it under ORIGINAL JOB TEXT (cv_generator.py:926). The only thing that
ever fills `original_source_text` is ChatGPT-collected JSON whose prompt **asks** the model to open
the URL and copy it verbatim (prompt_builder.py:62,78,94). Nothing verified that it did, and the
generation flow had no way to check: the single CvGenerator surface showed no source text at all, and
BatchCvGenerator showed `original_source_text||raw_description` with no provenance label.

## The shape of the fix

- `services/posting_fetch.py` (new, stdlib only -- urllib + html.parser + gzip): reads the posting at
  the job's own URL and flattens it to text.
- `GET /api/jobs/<id>/source-text/live/`: **read-only by construction**. It never writes, so adopting
  a fetched body stays the user's explicit act through the existing PATCH source-text action -- which
  is what makes AC4 true structurally rather than by a guard.
- `generation_preview` gained one `job` key carrying `url`, `source_text`, `source_chars` and
  `source_is_fallback`. That flag is the provenance the UI needs to stop calling a cleaned
  description a collected posting.
- One pure exported `PostingSource` component renders on BOTH generation surfaces. The batch dialog
  dropped its second per-row request to /jobs/<id>/ because the preview payload now carries it.

## Gate: only accounts that can see the panel can make the server dial

Added by the coordinator, not the implementer: the endpoint sits behind `is_cv_owner` like
`cv_generation_preview`. CODEX_CV_ENABLED is DEBUG-only by deployment, so the deployed container
exposes no outbound fetcher at all. Test: test_an_account_without_cv_capability_cannot_make_the_server_fetch_anything.

## Measured by the coordinator, in the running app (TW-003/TW-004)

Scratch sqlite database, never production. Backend on :8001, Vite on :5199.

| what | measurement |
|---|---|
| AC1 small page | job 1 (example.com) -> panel shows the page's own body, 129 chars |
| AC1 large page | job 5 (Wikipedia ML) -> **135,059 chars**, byte-identical tail to the API, box 160px / scrollHeight 64,624px, overflow-y auto, resize both, scrolled to the end |
| AC2 | after adopt: panel 129 chars == `preview.job.source_chars` 129; `_prompt(job,...)` contains that body verbatim and **'Stored summary, not the posting body.' is gone** |
| AC3 expired URL | job 3 -> role=alert 'The site answered 404 Not Found.', one <pre> only, no adopt control |
| AC3 provenance | job 1 'Collected original posting text (122 characters). This is the text generation will use.' / job 4 'Cleaned description - no original posting text was collected (70 characters).' rendered amber rgb(180,83,9) |
| AC4 no write | after four live fetches through the running server, all five jobs' `original_source_text` byte-unchanged in the database |
| AC4 no URL | job 2 -> zero anchors, no href='', no fetch control, Generate still enabled, stored text still shown |
| fetcher, real network | example.com 129 / Wikipedia 135,059 / 404 honest / 127.0.0.1 refused / ftp refused / dead DNS honest |

## A green suite was not enough, again

The implementer's first version returned `ok=True` with 10,664 characters of U+FFFD for
https://www.python.org/jobs/ -- Fastly answers `content-encoding: gzip` to a request that never asked
for it, and urllib does not decompress. That is exactly the failure this task exists to stop, and only
a live fetch found it. Fixed with a capped gzip/deflate unpack plus `Accept-Encoding: identity`;
brotli is an honest error rather than a new dependency. Regression test:
test_gzipped_page_is_unpacked_instead_of_being_served_as_garbage.

## Known ceilings, recorded rather than hidden

- The host check runs at resolve time, so a DNS rebind between the check and urllib's own resolution
  still wins. Closing it needs a pinned-IP connector; the threat here is a pasted job link.
- A body over 2 MB compressed is refused rather than truncated.
- No JavaScript is executed, so a JS-only posting reports that instead of inventing content.

## Gates

Backend 1203 passed (pre-change baseline 1187, +16 new). Frontend: `npx tsc --noEmit` clean, 267
tests in 16 files. `npm run build` in the owner's checkout -> assets/index-CDTdXTGz.js.

## DoD #1 is NOT checked

It reads 'execute through the session-orchestrator workflow **after TASK-226 is complete**'. The
workflow half is true (rubric sealed before implementation, two agents in separate file territories,
coordinator verification, graded against the sealed rubric). The sequencing half is not: TASK-226 is
still In Progress because its AC1/AC3/AC4 need a second physical device and a reboot, which is owner
action rather than engineering. The owner asked for the remaining engineering tasks to proceed.

## Merged, but NOT Done: production cannot be verified

PR #157 squash-merged to main as 71b3049 with CI green (test job passed). The branch
`task-237-238-real-posting-text` is deliberately NOT deleted, because TW-00A step 5 comes after step
6 and step 6 cannot be reached.

**The deploy job failed on an external condition, not on this change:**

    ERROR: (ReadOnlyDisabledSubscription) The subscription 'f0d59028-5822-491c-8ab1-693dfd9c0057'
    is disabled and therefore marked as read only. You cannot perform any write actions on this
    subscription until it is re-enabled.

That is also why production itself is unreachable: `GET https://dachapply.livelysea-3461ad21.westeurope.azurecontainerapps.io/api/health/`
fails at TCP connect (DNS resolves to 20.23.217.200; curl reports connect=0.000000s, timing out at
21s on every attempt). The uptime-monitor workflow has failed on every scheduled run since
2026-09-16T09:25Z; the last success was 2026-09-16T04:03Z. **This predates this work by about 36
hours and no change in this repository can fix it** -- the Azure subscription has to be re-enabled by
the owner.

Rollback image recorded before the merge, per TW-006:
`ghcr.io/ermischo/dachapply:02b08c829ecc826ca3ddc48eff7dac5a67709691`.

**Verified on the owner's machine instead (CLAUDE.md 'finish on the owner's machine'):** the runtime
worktree at AppData/Local/dachapply/main-runtime was synced to 71b3049 and rebuilt; localhost:8000 now
serves `assets/index-Bq6sDx6K.js`, which matches that worktree's `frontend/dist/index.html`,
`/api/health/` returns 200, and the page renders (1,705 chars, no error boundary). Note the feature
is local-only in effect anyway: CODEX_CV_ENABLED is DEBUG-only by deployment, so the generation flow
-- and therefore this panel and this endpoint -- do not exist in the deployed container.

Status stays In Progress until the subscription is re-enabled and a deploy reaches production.
<!-- SECTION:NOTES:END -->
