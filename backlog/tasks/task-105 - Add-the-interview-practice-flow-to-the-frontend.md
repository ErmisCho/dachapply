---
id: TASK-105
title: Add the interview practice flow to the frontend
status: Done
assignee: []
created_date: '2026-08-16 18:38'
labels:
  - product
  - frontend
  - interview-coach
dependencies:
  - TASK-104
priority: high
ordinal: 106000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Frontend half of the coach absorption (see TASK-104): a practice page in the DACHApply SPA
replacing the discarded Next.js app. Practice an interview answer in German or English, see the
clarity/structure/confidence scores with feedback and the suggested rewrite, and review past
sessions to watch progress — the coach MVP's scope, restyled as a native DACHApply page.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A /practice route lets an authenticated user pick a language, enter a question and answer, and get scores, feedback and the rewrite from the TASK-104 endpoints
- [x] #2 Practice history is visible with per-dimension scores over time (numbers or simple bars; no charting dependency)
- [x] #3 The job detail page offers "Practice for this interview", pre-linking the session to that job
- [x] #4 The page follows the app's established patterns: ErrorBox/StatusMessage affordances, labeled inputs, keyboard operability, a per-route tab title, and nav reachability on mobile (44px targets)
- [x] #5 npx tsc --noEmit and npm test pass
<!-- AC:END -->

## Outcome (2026-08-16, wave 11)

/practice built in App.tsx with CSS score bars + numeric badges (no new dependencies), history
(job-filtered when opened via ?job=), nav entries in both the desktop row and the mobile
profile-dropdown (TASK-67 pattern), and the job-detail "Practice for this interview" link.

MEASURED in a real browser on a live local stack (backend :8010 scratch sqlite, vite :5199):
EN and DE submissions produce scores/feedback/rewrite and an instant history row; the pre-link
renders "Linked to VerifyCorp — Backend Engineer" and the stored session has language=de, job=1;
tab title "Practice — DACHApply"; at a true 372px viewport the Practice link is absent from the
nav row, present in the account dropdown, and measures 44.0px tall; ErrorBox surfaced a real
in-page error during verification (a CSRF harness misconfig — the affordance works). tsc clean,
npm test 33/33, both coordinator re-runs. Asian-dad verdict: PERFECT (6/6 PASS).

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Ship with TASK-104 in one wave as a single full-stack agent (the one-shot). AC4's list exists
because the closed waves 1-9 established those conventions — a new page must not regress them.
The scoring display should reuse the existing badge idiom rather than inventing one; mind the
non-color-signal rule from TASK-87.
<!-- SECTION:NOTES:END -->
