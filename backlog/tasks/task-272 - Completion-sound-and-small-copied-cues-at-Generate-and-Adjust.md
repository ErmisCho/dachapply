---
id: TASK-272
title: Completion sound and small copied cues at Generate and Adjust
status: Done
assignee: []
created_date: '2026-10-07 13:30'
labels:
  - ui
dependencies:
  - TASK-271
priority: medium
ordinal: 269000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-10-07: "once the cv and/or letter is generated (depending on the selection) I get a sound notification that is elegant and professional also the message: Generated TeX files copied to clipboard. should be a little indication next to the generate button, and then disappear, when also copying the .tex files from adjusting I should get a little visual cue that the button was clicked and text was copied to my clipboard."

Today CvGenerator shows `clipboardMessage` ("Generated TeX files copied to clipboard.") as a full-width SuccessMessage at the top of the panel, and it stays there. The Adjust area's "Copy generated TeX files" icon button gives no feedback when clicked. Built on TASK-271's branch because both touch App.tsx.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 When a Generate run finishes successfully (CV, letter, or both, as selected), one short, soft completion chime plays: two or three gentle sine tones, under one second, at moderate volume. No sound plays on failure or cancel. The bulk generator plays it once when the whole batch finishes, not once per job
- [x] #2 The sound needs no new dependency and no audio file. It does nothing silently where audio is unavailable or blocked, and never throws
- [x] #3 The "Generated TeX files copied to clipboard." banner no longer appears at the top of the panel. A small indicator (e.g. a check and "Copied") appears inline next to the Generate button when the TeX was copied, then fades out by itself within a few seconds. A clipboard failure still shows its error
- [x] #4 Clicking the Adjust area's "Copy generated TeX files" button gives a brief visual cue on the button: the icon swaps to a check and a "Copied" label or tooltip shows, then it reverts after about 1.5–2 s. On failure it does not show "Copied"
- [x] #5 The same small cues apply where the same copy controls exist in the bulk generator rows
- [x] #6 vitest covers the chime trigger (success only), the auto-hiding inline indicator, and the copy-button cue; tsc and the full suites green
- [x] #7 Verified in a browser: after a real recompile or generation the inline indicator appears next to Generate and then disappears, the copy button shows its cue, and the chime path runs (AudioContext called) on success
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- `playChime()` in appUtils.ts uses the Web Audio API, with no dependency and no audio file. It plays two sine notes, A5 then E6 0.12 s later, each with a 15 ms attack and exponential decay to a peak gain of 0.1, ending at 0.77 s. One AudioContext is created lazily and resumed if suspended. It does nothing without AudioContext and never throws.
  - Generate chimes only when its task is ready. Readjust and Recompile flash the chip but stay silent.
  - The bulk generator chimes once, after all rows finish, if any row is ready.
- The top "Generated TeX files copied to clipboard." banner is gone. `CopiedChip` ("✓ Copied", role=status) now sits right after Generate, shown by `useFlash(3000)`, and the CSS `copied-fade` animation fades it out (no animation under prefers-reduced-motion).
- The Adjust "Copy generated TeX files" button and each bulk row's copy button are `CopyTexAction`. After a successful copy, CopyIcon swaps to CheckIcon, "Copied" shows and the title becomes "Copied" for 1.8 s. On failure there is no cue and the error shows.
- Coordinator browser verification: headless Chrome at 1366x768 on a scratch server built from the branch. The run and status endpoints were stubbed in the page, and AudioContext was instrumented to count notes.
  - A real click on Generate that returned ready played 2 notes. The "Copied" chip appeared 8 px to the right of Generate, the top banner was absent, and the chip was gone after 5 s.
  - A failed run played 0 new notes and showed its error.
  - A real click on the Adjust copy button showed "Copied" (text and title) at 0.5 s and was back to normal at 2.5 s. The clipboard held the TeX text, starting `% Job listing:`. The owner's clipboard was restored afterwards.
- Tests: copyCues.test.tsx has 8 tests. All 13 mutation checks were caught. vitest: 352 passed. tsc: clean.
<!-- SECTION:NOTES:END -->
