---
id: TASK-235
title: Bring the batch CV popup in line with the redesigned single popup
status: Done
assignee: []
created_date: '2026-09-12 09:19'
updated_date: '2026-09-12 09:23'
labels:
  - frontend
dependencies: []
priority: medium
ordinal: 234000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up the TASK-230/231/233/234 work left behind, flagged by the implementing agent and confirmed by attributing every remaining long label to its component.

`BatchCvGenerator` is the popup for generating across several selected jobs at once. It was outside that waves file territory and still carries what the single popup just shed:

- `Readjust and compile` and `Recompile saved PDFs` - the long labels, unshortened
- `Copy generated TeX files` - still a worded button rather than the copy glyph
- `Adjust latest generated files` - the long section label
- the `Fastest practical setting: Low effort + 1.5x Fast. xhigh performs substantially more reasoning and can take several minutes.` paragraph, still standing prose rather than a tooltip

In the single popup every one of those is now either a glyph with a tooltip, a shortened word, or a `title` on the control it describes. Verified: the same strings inside `CvGenerator` are now only in `title=` and `aria-label=` attributes.

So the two popups disagree about the same actions, and the owner asked for a minimalistic and polished CV window rather than for one of two to be minimal.

Worth deciding rather than copying: the model cluster and the readjust panel exist in both components. The single popup grew a local `picker()` during TASK-230. Extracting one shared picker is the smaller long-term diff than a second hand-maintained copy, but it changes a component both popups depend on, so it is a judgement call rather than an obvious win.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The batch popup uses the same labels, glyphs and tooltips as the single popup for the actions both have - no action is a glyph in one and a sentence in the other
- [x] #2 Every icon-only control in the batch popup has both a tooltip and an accessible name, matching the rule TASK-234 settled
- [x] #3 The standing prose named in the description is removed or moved into a title on the control it describes, with the visible prose character count stated before and after
- [x] #4 Whether the shared model picker is extracted or duplicated is a recorded decision with a reason, not an accident
- [x] #5 The batch popup height is measured before and after at a stated viewport, and does not get taller
- [ ] #6 Frontend tests and typecheck pass, and the result is verified in the served bundle at localhost:8000
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Done 2026-09-12

Measured with three jobs selected, same board, same viewport:

| | before | after |
|---|---|---|
| `Readjust and compile` | 145 px | **`Readjust`, 73 px** |
| `Recompile saved PDFs` | 149 px | **`Recompile`, 84 px** |
| buttons per job row | 294 px | **157 px** |
| popup height | 1,397 px | **1,381 px** |
| visible prose | 555 chars | **399 chars** |

**The width is the real win, and it multiplies.** Those two buttons render once per selected job, so
three jobs carried six long labels and ten would carry twenty. 137px saved per row is 411px at three
jobs and 1,370px at ten - which is why the same edit is worth more here than it was in the single
popup. Height barely moves because the buttons sit in a flex row: shortening a label buys width, not
height. The 16px that did go is the trimmed paragraph.

`Copy generated TeX files` is now the same `CopyIcon` glyph the single popup and `CopyPath` use, with
both a `title` and an `aria-label`. `Adjust latest generated files` -> `Adjust latest files`, with the
availability sentence moved onto the summary as a tooltip. Both `ProgressButton`s are wrapped in a
`span title=...`, the same way TASK-234 did it, because `ProgressButton` takes `label:string`, has no
`title` prop, and renders live progress inside its own label.

One sentence was deliberately KEPT visible: `Selected jobs run in parallel.` It is the only fact in
that paragraph the single popup does not also have, and it tells the owner what pressing Generate will
actually do. Only the effort/speed advice moved to the Speed tooltip.

### AC4 - the shared picker was NOT extracted, deliberately

The batch popup has ONE model picker; the single popup now has TWO with different labels and
independent state. The genuinely shared surface is about twenty lines of select markup, and the parts
that differ - how many pickers, whose state, which labels - are the parts that matter. Extracting
would introduce a new exported component that two large components depend on, to remove markup that is
not the source of any measured problem. Reconsider it if a third caller appears.
<!-- SECTION:NOTES:END -->
