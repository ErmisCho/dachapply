---
id: TASK-238
title: Link to the original posting from CV and letter generation
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-14 14:41'
updated_date: '2026-09-17 13:48'
labels:
  - frontend
  - ux
dependencies:
  - TASK-226
priority: medium
type: enhancement
ordinal: 237000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a small direct control in the CV and motivation-letter generation flow that opens the selected job's original external listing. The existing TASK-32 link goes to internal job details; this control must go to the original posting URL. Start only after the currently active TASK-226 is complete.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each job with an original listing URL has a compact, clearly recognizable control beside its source text or job identity in the generation flow
- [x] #2 Activating the control opens the original external listing in a new browser tab without closing the generation flow or starting generation
- [x] #3 The control is keyboard reachable and has an accessible name that identifies its destination
- [x] #4 Jobs without an original listing URL do not show a broken or misleading control
- [x] #5 The behavior is covered by the smallest appropriate frontend regression check
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Execute through the session-orchestrator workflow after TASK-226 is complete
- [ ] #2 Pre-register task-specific Asian Dad criteria before implementation and receive PERFECT after the required quality gates
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Confirm what already exists: BatchCvGenerator renders a <Link to=/jobs/:id> (TASK-32, internal details) beside each row title - this task's control is a different one, to job.url itself.
2. job.url is already on board list rows (JobLeadListSerializer excludes only raw_description and original_source_text), and generation_preview now carries job.url too, so no extra request is needed on either surface.
3. Ship the control as a plain <a href={job.url} target=_blank rel=noopener noreferrer> - the native platform feature, not a window.open handler - inside the shared PostingSource component so both generation surfaces get it from one place.
4. Accessible name states the destination (open the original posting for <company> <title> at <host> in a new tab); no control at all is rendered when job.url is empty (AC4).
5. Regression test in frontend/src/postingSource.test.tsx via renderToStaticMarkup (this repo's vitest run has no DOM and TASK-177 forbids adding one): href/target/rel and accessible name with a URL, absence without one.
6. Coordinator measures AC1-AC4 in the running browser - control present on both surfaces, keyboard reachable, opens a new tab without closing the flow or starting generation - then grades against the rubric sealed before implementation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## What shipped

The control is a plain `<a href={job.url} target="_blank" rel="noopener noreferrer">` with an
external-link glyph and the visible text 'Original posting', inside the shared `PostingSource`
component -- so both generation surfaces get it from one place, and neither can drift from the other.
No `window.open` handler: an anchor is the native control, and it keeps middle-click and ctrl-click
working. It renders only when `job.url` is non-empty.

TASK-32's internal `<Link to={/jobs/:id}>` in the batch dialog is untouched; a test pins that it is
still there, because this task exists to be a DIFFERENT control from that one.

## Measured by the coordinator, in the running app (TW-003/TW-004)

Scratch sqlite database, Vite :5199 against a backend on :8001.

- **AC1, both surfaces.** Single popup (board) and the #cv-generator section: control present. Batch
  dialog: present on the Example GmbH row, absent on the NoLink AG row. Row toggles now read
  'Show the source text and original posting for <company> <title>'.
- **AC2, real click.** Clicked at (742,376) with the mouse: the tab did not navigate (still
  http://localhost:5199/), the dialog stayed mounted, the Generate button stayed idle, no progress
  element appeared. `href` is `https://example.com/` -- the job's own URL, not /jobs/1 --
  `target=_blank`, `rel=noopener noreferrer`.
- **AC2, no generation started.** With a fetch spy installed, activating the control produced
  **zero** requests; nothing matching cv-generation/(run|revise|recompile).
- **AC3, keyboard.** `tabIndex` 0, element **18 of 20** in the dialog's tab order, `focus()` lands on
  it (`document.activeElement === anchor`), and the name announced is
  'Open the original posting for Example GmbH Machine Learning Engineer at example.com in a new tab'.
  Pressing Return on it activated the link without navigating the current tab or closing the dialog.
- **AC4, no URL.** Job 2 (url='') in both surfaces: zero anchors, no `href=''`, no stub, and the
  stored text still shown.

Focus and key events were driven directly rather than through the automated tab's focus ring, which
does not fire in a hidden tab -- the probe is `document.activeElement`, not a focus event.

## AC5

`frontend/src/postingSource.test.tsx`, 11 tests, rendered with `renderToStaticMarkup`: this repo's
vitest run has no DOM and TASK-177 forbids adding one, which is why `PostingSource` is pure and takes
the payload as props. It asserts href/target/rel and the accessible name with a URL, absence without
one, and that neither surface kept private markup.

## Gates

`npx tsc --noEmit` clean, 267 frontend tests in 16 files, backend 1203 passed.

## DoD #1 is NOT checked

Same reason as TASK-237: the workflow half is true, the 'after TASK-226 is complete' half is not --
226 is still In Progress pending a second physical device and a reboot, which is owner action.
<!-- SECTION:NOTES:END -->
