---
id: TASK-87
title: Label placeholder-only inputs and add a non-color signal to skill badges
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 13:10'
labels:
  - frontend
  - a11y
dependencies: []
priority: medium
ordinal: 92000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Two targeted accessibility gaps, both patches rather than passes because other pages already do these right (aria-labels in EditableJobDetails App.tsx:125, real labels in ProfileSettings App.tsx:191):

1. Placeholder-only inputs: login email/password (App.tsx:90), the dashboard filter inputs — "Search title, company, text", "Location", "Min fit score" (App.tsx:98) — and JobForm's detail inputs (App.tsx:107) rely solely on placeholders, which screen readers announce inconsistently and which vanish once the user types.
2. Color-only state: SkillLabels conveys matched/weak/missing purely as green/yellow/red on otherwise identical text (App.tsx:50 — `tone(s)` is the only differentiator; the title attribute only says "Click to cycle"). A colorblind user cannot tell which skills they lack. Status badges are fine (their text differs) — this is the one true color-only case in the app.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every input on login, the board filter bar, and JobForm has a programmatic label (visible label or aria-label matching the placeholder)
- [x] #2 Skill match state is distinguishable without color — a glyph prefix and/or the state word in the title attribute
- [x] #3 An axe run (or equivalent) on login, dashboard, and add shows no label violations, recorded in the closing notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
aria-label duplicating the placeholder text is the cheapest compliant fix and needs no layout change. For badges, a ✓/~/✗ prefix plus state word in title covers screen readers and colorblindness in one edit to `tone(s)`.

### Closing notes (2026-08-16)

**The ticket's list of offenders was incomplete, and an axe baseline taken before any work started
is what showed it.** The described inputs (login, filter bar, JobForm) were only part of the
problem; the actual critical failures were elsewhere:

    BEFORE                                            AFTER
    /login    1 violation,  0 label-related           1 violation,  0 label-related
    /         3 violations, 2 label-related           1 violation,  0 label-related
              label: 6 nodes (per-row date inputs)
              select-name: 7 nodes (per-row selects)
    /add      1 violation,  1 label-related           0 violations
              select-name: 1 node (work-mode select)

Thirteen unlabelled nodes on the dashboard and `/add`, none of them named in the description. The
one violation left on `/login` and `/` is a pre-existing `color-contrast` issue, out of this task's
scope and deliberately not counted.

AC3 is therefore met, but on its own it would have been a weak check: **axe accepts `placeholder` as
an accessible-name source**, so the login inputs — the exact placeholder-only case this task was
filed about — passed axe both before and after. AC1 is the stronger bar, and it was verified
separately by walking the DOM on each page and asserting every control has an `aria-label`,
`aria-labelledby`, an associated `<label for>`, a wrapping `<label>`, or a `title`:

    /login          3 controls, 0 without a programmatic name
    /              94 controls, 0 without a programmatic name
    /add            9 controls, 0 without a programmatic name
    /public-submit 10 controls, 0 without a programmatic name

Board controls are named with row context (`"Status for Acme Backend Engineer"`, `"Application date
for …"`) rather than seven identical "Status" labels. Where a placeholder existed the aria-label
reuses it verbatim, so AC1's "matching the placeholder" is literally true. Fixing `PasswordInput`
once also covered ResetPassword, ChangePassword and AccountDeletion.

AC2 measured on the live board — badges now carry a glyph *and* the state word:

    ✓ Python   title="Python: matched. Click to cycle: missing → weak → matched. …"

so the state survives greyscale and reaches a screen reader, which the previous colour-only
`tone(s)` did neither of.
<!-- SECTION:NOTES:END -->
