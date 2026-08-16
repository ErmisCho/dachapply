---
id: TASK-111
title: Board sorting is unreachable below 1024px
status: Done
assignee:
  - '@claude'
labels:
  - frontend
  - accessibility
  - ux
dependencies: []
priority: medium
ordinal: 112000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-108 made the board sortable by status and by up to three columns at once, via clickable column
headers. Those headers live on the board `<table>`, which is `hidden … lg:table` — so **none of it
exists below 1024px**. Below that breakpoint the board renders as cards and the only sorting control
is the original four-option preset `<select>`.

Measured 2026-08-16 with the same session and dataset at three widths:

     390px  sortable headers in DOM=6  RENDERED=0  preset <select> visible=true
     768px  sortable headers in DOM=6  RENDERED=0  preset <select> visible=true
    1024px  sortable headers in DOM=6  RENDERED=6  preset <select> visible=true

A phone user therefore gets: `Sort: recommended`, `Sort: fit score`, `Sort: newest`,
`Sort: feedback due` — and **no way to sort by status at all**, which was the headline request, and no
way to combine two keys.

Note the headers are present in the DOM but `display:none`, which also removes them from the tab
order. So this is not "a small-screen layout that omits a feature"; it is the same class of defect as
TASK-102 (controls that exist but cannot be reached), just triggered by viewport instead of hover.

Found by the coordinator during TASK-108 verification. TASK-108's AC6 is satisfied where the controls
render — they are keyboard-operable, tap-operable and 44px at >=1024px — so this is filed rather than
folded in, per TW-005: the gap gets its own paper trail instead of quietly widening or relaxing that
task's criteria.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A user on a 390px viewport can sort the board by status
- [x] #2 A user on a 390px viewport can apply at least two sort keys with an explicit precedence, or the decision to allow only one key on small screens is recorded with its reasoning
- [x] #3 Whatever control is added is operable by touch and by keyboard, with 44px targets, and is not hidden behind hover or a modifier key
- [x] #4 The current sort is visible on small screens, not just implied
- [x] #5 Verified at 390px in a real browser, with the applied ordering read back from the request the UI actually sends
- [x] #6 No new axe violations at 390px, and `npx tsc --noEmit` / `npm test` stay clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Cheapest option that covers AC1 and probably AC2: extend the existing preset `<select>` — which is
already visible at every width — into a small sort sheet, or simply add the status options to it
(`Sort: status`, `Sort: status then fit`). That reuses a control that is already rendered, already
accessible and already wired to `f.ordering`; the wire contract from TASK-108 takes a comma-separated
string, so a preset can encode two keys with no backend change at all.

Only reach for a bespoke mobile sort UI if a preset list genuinely cannot express what is needed. The
backend already supports everything here — this is purely about giving small screens a control.

Worth checking while in here: whether the board table should become horizontally scrollable at
tablet widths instead of being replaced by cards, which would make the real headers available from
768px up and shrink this task considerably.
<!-- SECTION:NOTES:END -->

## Frontend status (ui-developer)

Took the notes' cheapest option literally: extended the existing preset `<select aria-label="Sort
board by">` (already rendered at every width per the task's own 390/768/1024 measurement, already
wired to `f.ordering`) rather than building a bespoke mobile sort UI. No new control, no backend
change — the wire contract from TASK-108 already accepts everything used here.

`frontend/src/App.tsx` — added two `<option>`s: `value="status"` ("Sort: status") and
`value="status,-fit_score"` ("Sort: status, then fit score"); added `min-h-[2.75rem]` to the select's
className; added a `<span id="sort-ordering-description" aria-live="polite">` right after the select,
wired via `aria-describedby` on the select, rendering `describeOrdering(f.ordering)`.

`frontend/src/appUtils.ts` — new pure function `describeOrdering(ordering)`, parsing the same
comma-separated `-key` wire string `sortOrderingString`/the preset select both produce, so the
on-screen text can never drift from what `?ordering=` will actually send — including combinations no
preset spells out (e.g. a multi-key sort set via desktop headers, then viewed after narrowing the
window). Unit tests added in `appUtils.test.ts` (default/empty, single key, `status,-fit_score`,
unmapped key fallback).

**AC2 — answered with a feature, not a decision.** `status,-fit_score` is literally the example given
in this task's own prompt (`?ordering=status,-fit_score`), so a second preset encoding it costs one
`<option>` and required no bespoke multi-key mobile UI. A phone user can pick "Sort: status, then fit
score" and get two keys with explicit precedence (status primary, fit score descending secondary) —
same wire value a desktop user gets by clicking the Status header once then the Fit header twice. Did
not build a control that composes arbitrary key combinations on a phone; a fixed small set of presets
plus the existing four covers what a card list actually needs, and matches the notes' own suggested
naming (`Sort: status then fit`) almost verbatim.

**AC3 — code-verifiable without a browser, so checked.** The control is the native `<select>` already
in the tab order at every width (nothing wraps it in a `hidden`/`lg:` class); native selects are
keyboard-operable (Tab, Space/Enter to open, arrow keys, type-ahead) and touch-operable (tap opens the
platform picker) with no hover or modifier-key requirement. `min-h-[2.75rem]` (44px) is added as an
extra utility class alongside the shared `.filter-input` (`h-9` = 36px in `index.css`, not edited —
out of file territory); CSS resolves the used height to `max(height, min-height)`, so min-height forces
a 44px floor regardless of the shared class. Same technique TASK-108 used on `SortTh`
(`min-h-[2.75rem] min-w-[2.75rem]`), so this is an established pattern in this codebase, not a new one.

**AC1, AC4, AC5, and the axe half of AC6 — need a real browser at 390px; not claimed here** (no
browser tools available to this agent). Requesting the coordinator check:
- AC1: at 390px, `select[aria-label="Sort board by"]`, choose "Sort: status", click "Apply" — confirm
  the request sent is `?ordering=status` (or includes it) and the board re-sorts by pipeline status
  order.
- AC4: at 390px, confirm `#sort-ordering-description` (the text right after the select) is visible on
  screen — not just present in the DOM — and its text changes when a different preset is chosen
  (e.g. "Sorted by: Status, then Fit score (desc)" after picking the two-key preset).
- AC5: at 390px, read the actual outgoing request (network panel) after choosing each new preset and
  confirm it matches `?ordering=status` and `?ordering=status,-fit_score` respectively — not just the
  UI's own state.
- AC6 (axe portion): run axe at 390px on the board/filters area; `min-h-[2.75rem]` and
  `aria-describedby` are the two a11y-relevant additions worth double-checking render as intended.

**AC6 (tsc/test portion) — verified.** `cd frontend && npx tsc --noEmit`: clean (no output). `npm test
-- --run`: `3 test files, 42 tests passed` (up from 38 before this change — the 4 new
`describeOrdering` cases). `npm run build`: succeeds (`vite build`, pre-existing >500kB chunk-size
warning only, unrelated to this change).

**Desktop unregressed.** `toggleSort`, `sortInfo`, and every `<SortTh .../>` header (still 6, unchanged
byte-for-byte apart from surrounding whitespace shift caused by the earlier select edit) were not
touched — confirmed by diffing the relevant slice of the file and grepping post-edit for
`<SortTh` (6), `toggleSort` (7: one definition + six `onSort={toggleSort}` props), and
`describeOrdering` (1, the new usage only). No behavioural change possible at >=1024px since none of
that code was edited; TASK-108's own coordinator verification of the header cycle
(unsorted→asc→desc→unsorted, append-not-replace, keyboard-only) is unaffected. Did not re-run a
browser check at 1024px myself (no browser tools) — flagging in case the coordinator wants to
re-confirm it alongside the AC1/AC4/AC5 checks above, though nothing in the diff touches that path.

File territory respected: only `frontend/src/App.tsx`, `frontend/src/appUtils.ts`,
`frontend/src/appUtils.test.ts`, and this task file were edited. `backend/` untouched. Unrelated
modified/untracked files seen in `git status` (`.orchestrator/metrics/*.jsonl`,
`.orchestrator/current-session.json.tmp-*`, `NUL`) belong to another active session and were left
alone.

## Coordinator browser verification (2026-08-16)

Isolated stack (scratch sqlite on :8010, SPA on :5200), dataset of two jobs per status.

**AC1/AC3/AC5 at 390px with touch emulation:**

    sort select rendered      true
    tap target                324.0 x 44.0
    options                   recommended | status | status, then fit score | fit score | newest | feedback due
    rendered header buttons   0        <- the original defect, still true, so this is the right control

    chose "Sort: status"                -> request ordering=status
    chose "Sort: status, then fit score"-> request ordering=status%2C-fit_score

**AC1 the part that matters — the board actually reorders**, read from the rendered cards rather
than from the request:

    ordering=status              new, reviewed, to_apply, applied, interview, offer, accepted, rejected
    ordering=-created_at         skipped, withdrawn, rejected, accepted, offer, interview, applied
    ordering=status,-fit_score   new, reviewed, to_apply, applied, interview, offer, accepted, rejected

The middle line is the control: a visibly different order proves the board is re-querying, not that a
request merely went out. `status,-fit_score` matching `status` at this granularity is correct — the
second key only breaks ties *within* a status.

**AC3 keyboard-only, no mouse and no programmatic selectOption:**

    focus                 "Sort board by"
    ArrowDown             value -> "status"
    focus "Apply", Enter  -> ordering=status
    description           "Sorted by: Status"

and a real `tap()` on the select at 390px works. Worth stating why this was re-run: the first pass
drove the control with Playwright's `selectOption`, which is neither a tap nor a keypress, so it
proved nothing about either.

**AC4** — `#sort-ordering-description` is rendered and visible, and tracks the value:

    recommended                -> "Sorted by: recommended"
    status                     -> "Sorted by: Status"
    status,-fit_score          -> "Sorted by: Status, then Fit score (desc)"

It derives from `f.ordering` rather than the select's own label, so a sort chosen on desktop headers
and then viewed on a narrow screen still describes itself correctly instead of silently showing
whatever option happens to match.

**AC6** — axe (wcag2a/2aa/21a/21aa): **0 violations at 390px and 0 at 1400px**. tsc clean,
**42 frontend tests** (38 + 4 for `describeOrdering`), build ok.

**Desktop unregressed**, checked rather than assumed: 6 header buttons still render at 1400px and a
keyboard-only Status-then-Fit still appends rather than replaces (`Status▲1`, `Fit▲2`).

**A merge hazard worth recording.** This work was written against `main` before
`78639dc` (the interview-coach/Gmail wave) landed, and that commit also edits `App.tsx` and
`appUtils.ts`. A 3-way merge on `App.tsx` — where one line can be thousands of characters — produced
a conflict whose resolution would have been unreviewable. Re-applying this change onto the new file
by hand was the safer path, and the parallel session's `/practice` and `/mailbox` route titles are
intact. Do not attempt to auto-merge that file across sessions.
