---
id: TASK-243
title: 'Status messages look like a template, not like this product'
status: Done
assignee:
  - '@pi'
created_date: '2026-09-21 16:30'
updated_date: '2026-09-22 12:47'
labels:
  - frontend
  - ux
dependencies: []
priority: medium
type: enhancement
ordinal: 242000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-09-21, looking at the CV generation window with both a success and an info message showing: it 'seems a bit unpolished and AI generated like'.

Measured rather than guessed. index.css:222-230 gives every status message 1rem/1.1rem padding, a 1rem radius, a gradient background and box-shadow 0 10px 30px rgba(15,23,42,.08); index.css:224 makes the icon a 1.55rem FILLED disc in the tone colour with white glyph and its own coloured glow, box-shadow 0 4px 12px var(--status-glow). The compact variant (index.css:223) trims padding and radius but keeps the glowing disc at full size. Two of these stacked is what the screenshot shows.

The app already contains the quieter pattern it should be matching: .field-error-message (index.css:12-13) is flat - no background, no shadow - with a 1.35rem OUTLINED glyph in currentColor. So this is bringing one surface in line with the house style, not inventing a style.

Scope note, because it is bigger than the screenshot: StatusMessage and SuccessMessage are used 54 times across App.tsx. This is a change to a shared visual primitive, not to the CV window alone, which is why AC4 asks for the other call sites to be checked rather than assumed.

Related: TASK-228 already moved this same window toward 'smaller and calmer'; these banners are the part that did not get the message.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The success and info messages in the CV generation window are visually quieter than today: stated before/after numbers for rendered height and for the icon, measured in the browser at the same width, not adjusted by eye
- [x] #2 The treatment is consistent with what the app already uses for field errors rather than a second visual language - flat or near-flat, an outlined glyph rather than a filled disc with a coloured glow, and no drop shadow that lifts a one-line message off the page
- [x] #3 Meaning still survives the quieting: success, info and error remain distinguishable without relying on colour alone, and the role=status / role=alert semantics are unchanged
- [x] #4 Every one of the 54 existing StatusMessage and SuccessMessage call sites still renders correctly - none left with a broken layout, a missing icon, or text that now collides with its container
- [x] #5 Dark mode is checked as deliberately as light mode, with the same measurements
- [x] #6 Verified in the served bundle at localhost:8000 after a rebuild, not only in tests
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Verified by the coordinator, independently (TW-003)

The implementing agent's numbers were re-taken rather than trusted, in a separate rig: a throwaway
page linking the BUILT stylesheet, measured in Chrome with getBoundingClientRect and
getComputedStyle, before and after, same widths.

| | before | after |
|---|---|---|
| the owner's stacked pair | 88.0px, pills touching | 71.4px, 6px deliberate gap |
| compact message | 44.0 | 32.5 (-26%) |
| full + title | 83.3 | 64.6 (-22%) |
| icon | 24.8px FILLED disc + coloured glow | 21.6px OUTLINED ring, no shadow |
| container shadow | 0 4px 14px / 0 10px 30px | none |
| background | gradient | flat |
| contrast | -- | 7.44 / 8.26 light, 14.77 / 12.56 dark |

Call-site enumeration re-counted from source rather than accepted: 54 identifier mentions = 35 JSX
usages (23 SuccessMessage + 12 StatusMessage) + 2 definitions, of which 22 pass compact and 12 pass a
title. That matches the agent's shape breakdown.

## AC6 closed on the owner's machine

Rebuilt in the runtime worktree, then measured what localhost:8000 actually serves -- not a rebuild
in the development checkout, which is a different dist:

    served stylesheet   assets/index-fbkUlsKR.css   == the runtime worktree's dist/index.html
    page                rendered, 3,647 chars, no error boundary
    probe vs served CSS height 32.5px, box-shadow none, background-image none,
                        icon 21.6px, transparent fill, solid ring, no glow

## The deviation from the brief, accepted with its reason

The brief said no background; a flat opaque tone fill was kept. The reason is measured, not
aesthetic: the CV popup is bg-white with no dark variant, so a message there has to read on a white
island AND on a dark page, and no single text colour clears 4.5:1 against both. The fill is what
makes 7.44 and 14.77 both true. The criterion asked for 'flat or near-flat', which this is.

That surface bug is filed as TASK-244 -- ErrorBox measures 1.41:1 there -- and its AC4 requires these
fills to be re-evaluated once the popup has a dark variant.
<!-- SECTION:NOTES:END -->
