---
id: TASK-228
title: >-
  Make the CV generation window smaller and calmer without losing a single
  feature
status: In Progress
assignee: []
created_date: '2026-09-10 11:49'
updated_date: '2026-09-10 21:46'
labels:
  - frontend
dependencies:
  - TASK-227
priority: medium
ordinal: 227000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request, 2026-09-10: make the CV generation window minimalistic and smaller but concise, without removing any features.

The popup is App.tsx line 587 - one 11,162-character line. Its shell is fixed at `h-[80vh] w-[44rem] max-w-[calc(100vw-2rem)] overflow-y-auto`, so it is 704px wide and 80% of the viewport tall whether it is showing four dropdowns or a full generation report, and it scrolls internally rather than fitting.

Everything currently in it, so the "without removing any features" half is checkable rather than a promise: Provider, Model, Effort, Speed, Detected language, Create CV, Create motivation letter, Adjust latest generated files, Copy generated TeX files, the generation report (Main changes, Changed files, Checks, Not claimed), Close - plus whatever TASK-227 adds, which is why this depends on it.

Smaller and calmer are different things and both are wanted: fewer pixels, and less shouting inside them. Progressive disclosure (the report and the advanced model controls are not needed until they are) is the obvious lever, but collapsing a control is only acceptable if it is still reachable - hiding is not removing, and removing is out of scope.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every control listed in the description is still reachable after the change, checked off one at a time against the running window rather than asserted as a group
- [x] #2 The window is measurably smaller: rendered width and height in pixels are stated before and after, for the same job in the same state
- [x] #3 The common case - opening the window to generate, before any report exists - needs no inner scrolling, or the scrolling that remains is named and justified
- [ ] #4 It still works at 360px and 430px wide, verified by a stated measurement method rather than by reading the CSS
- [ ] #5 Frontend tests cover anything newly collapsible staying reachable, and the result is verified in the served bundle at localhost:8000 after `cd frontend && npm run build`
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Branch `task-227-228-cv-window`, shipped with TASK-227. Sealed rubric at
`.claude/.asian-dad/task-228-rubric.json` (gitignored, written before implementation).

## Measured, same job (1467), same state, same viewport (1706x1824)

| | before | after |
|---|---|---|
| shell | **704 x 1459 px** | **608 x 800 px** |
| natural content | 1,294 px | 750 px |
| inner scrolling | none | none |
| controls | **21** | **24** |

**-46% height, -14% width, -54% area.** Both numbers are `getBoundingClientRect()` on the popup
shell, not readings of the Tailwind classes. The before-figures were taken by putting the ORIGINAL
code back and re-measuring the same job, so it is like-for-like rather than two different jobs.

## AC1 -- nothing was removed, checked one at a time

The two inventories were captured from the running window and compared. All 21 before-controls are in
the after-list; the three extra are `Model settings` (summary), `Adjust latest generated files`
(summary) and `Mark applied` from TASK-227.

What moved rather than went: the model cluster (Provider, Model, Effort, Speed and the "fastest
practical setting" hint) and the readjust panel (instructions textarea, correction image, Readjust and
compile, Recompile saved PDFs, Copy generated TeX files) are now inside collapsed `<details>`. The
model summary prints the live selection -- `Model settings  OpenAI Codex - gpt-5.6-sol - low - 1.5x` --
so collapsing costs no information about what would run.

## AC3 -- no inner scrolling in the common case

`scrollHeight 798 == clientHeight 798`. Measured on a job that HAS generated artifacts (four extra
CopyPath rows); a job without them has more room, not less.

## The height is still fixed, and that is deliberate

`h-[80vh]` was not arbitrary. **TASK-216** put it there so slow provider discovery could not resize the
popup after it opened (its AC1: "reaches its final size and position on the initial render"). The
first attempt here used `max-h-[85vh]` alone, which makes the box content-dependent and reintroduces
exactly that jump. Caught before commit by TASK-216 own test.

The shipped rule is `h-[50rem] max-h-[85vh] w-[38rem] max-w-[calc(100vw-2rem)]`: smaller, still
stable on load, still bounded on a short viewport. `48rem` was tried first and overflowed by 8px on a
job with artifacts, which is why it is 50. A test pins that a fixed height exists at all and was
falsified against a ceiling-only version.

## AC4 -- NOT checked

360px and 430px were not measured. `max-w-[calc(100vw-2rem)]` is unchanged from before and the fixed
width only went DOWN (44rem -> 38rem), so nothing narrow can be worse than it was -- but that is
reasoning from the CSS, which this criterion explicitly does not accept, so it stays unchecked.

## AC5 -- half checked

Frontend tests pass (241, up from 237) and `npm run build` in the owner checkout succeeded
(`index-B6BgHVW-.js`). The served-bundle half is not done, for a reason worth writing down:

**localhost:8000 does not serve this checkout.** It serves a separate git worktree at
`C:/Users/Administrator/AppData/Local/dachapply/main-runtime`, pinned to deployed main (TASK-199), and
when a Vite dev server is running the backend redirects to it. So a branch under test is invisible on
localhost and needs its own dev server -- on a port that is not in `CSRF_TRUSTED_ORIGINS`, which is
why verifying TASK-227 write needed a throwaway backend on 8001 with that origin trusted. Every
harness used here was reverted; none of it is in the commit.

This closes by loading localhost after the merge lands and the runtime worktree syncs.

## Merged and in production, 2026-09-10

PR #144, merge commit `0d425db`, deploy green, `/api/health/` 200. The deployed bundle
`index-BSPnwo3G.js` contains `h-[50rem]`, so the sizing change is observable in what production
serves rather than argued from the merge.

Still **In Progress**: AC4 (360px / 430px) and the served-bundle half of AC5 remain unchecked.
<!-- SECTION:NOTES:END -->
