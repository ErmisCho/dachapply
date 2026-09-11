---
id: TASK-233
title: Fit the popup without scrolling even with every section open
status: In Progress
assignee: []
created_date: '2026-09-11 11:21'
updated_date: '2026-09-11 20:26'
labels:
  - frontend
dependencies:
  - TASK-230
priority: medium
ordinal: 232000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-09-11: the popup should try not to require scrolling even if all menus were unfolded.

Measured first, because the request may not be satisfiable the obvious way. On the owner display, same job, CvGenerator:

    every section collapsed (today) :   686 px
    every section unfolded         : 1,273 px   (+587)

The compact popup is `h-[50rem]` = 800px, capped by `max-h-[85vh]`. So with everything open the content overflows by about 473px. Making the popup tall enough instead is not available: on a 1080p laptop `85vh` is roughly 918px, still short of 1,273, and on a large display an 1,273px popup would occupy most of the screen and undo TASK-228, which took it from 1,459 to 800 precisely to stop that.

**So "never scroll with everything open" and "smaller" are in direct conflict in a single column, and one of them has to give.** The obvious escape is horizontal: the model cluster and the adjust panel are stacked today and are independent of each other, so at wide widths they could sit side by side, which roughly halves the unfolded height. That is a layout change, not a tweak, and it interacts with TASK-216 (the popup must reach its final size on first render, so the height cannot depend on what is open) and with the 360px case, where two columns must collapse back to one.

Decide the trade deliberately rather than discovering it: this task may legitimately end as "scrolling in the fully-unfolded state is accepted, and here is why", and that is a better outcome than a popup that fills the screen.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 With every section open, the popup fits a laptop screen without inner scrolling - stated as measured pixels against a stated laptop viewport (1920x1080 at 100% and 1536x864 at 125% scaling are the realistic cases), not against the owner large monitor
- [x] #2 Scrolling still exists as a safety net for the cases that cannot fit (360px, a long generation report), and is not removed - it simply is not reached in the normal fully-open state
- [x] #3 The collapsed state does not get taller than it is today, and the popup does not become so wide that it stops being the compact thing TASK-228 made it
- [x] #4 TASK-216 still holds: the popup reaches its final size on first render and slow provider discovery does not resize it
- [x] #5 Still works at 360px and 430px, verified by the same-origin iframe method TASK-228 used, with any multi-column layout collapsing to one column there
- [x] #6 The height with every section open is measured before and after, same job and viewport, alongside the collapsed height
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Measured 2026-09-11, at a real laptop viewport

| | before | after |
|---|---|---|
| popup | 608 x 800 | **768 x 681** |
| collapsed overflow | 0 | **0** |
| fully-open overflow, laptop (1532x740) | ~473 px | **0** (679 content in 679 available) |
| bottom edge | - | 721 of 740, so it fits on screen |
| 360 / 430 px | one column | one column, nothing clipped, no sideways page scroll |
| 1366 px board popup | - | spans 226-994 inside 1363, does not run off-screen |

Two columns at `lg` (1024px), which is the same line `index.css:379` stops forcing a 44px touch-target
floor, so layout density and control density switch together. Below it, one column with touch targets
intact. Scrolling is kept as the safety net and is still reached at 360/430px and for a long report -
it is simply not reached in the normal fully-open state. Final shell:
`h-[43rem] max-h-[92vh] w-[48rem] max-w-[calc(100vw-2rem)]`.

### Two things measuring caught that reasoning had wrong

1. **Laying the artifact paths out two-up made that block GROW, 266px to 589px** - at half width the
   long file paths wrap over several lines. Reverted. It was my change, made to save height, and it
   cost 323px.
2. **The first "it fits" readings were of the loading skeleton.** The popup renders its body only once
   `preview` arrives; before that there are no `<details>` at all, so 622px was the spinner. The probe
   now asserts `details.length > 0` before believing a number. Off-screen iframes
   (`left:-9999px`) also throttle layout, which is why two runs disagreed - the probe is on-screen now.

### Left In Progress deliberately

The height is verified on a 1532x740 viewport, which is the 1536x864-at-125% case the AC names. It is
**not** verified on a 1366x768 laptop, where the viewport is around 700px and the fully-open content
would still overflow. Whether that machine matters is the owner call, so the task stays open rather
than being closed on the viewport that happened to pass.
<!-- SECTION:NOTES:END -->
