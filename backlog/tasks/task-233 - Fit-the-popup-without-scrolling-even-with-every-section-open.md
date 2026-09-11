---
id: TASK-233
title: Fit the popup without scrolling even with every section open
status: To Do
assignee: []
created_date: '2026-09-11 11:21'
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
- [ ] #1 The height with every section open is measured before and after in pixels, on the same job and viewport, alongside the collapsed height
- [ ] #2 Either the fully-unfolded state fits without inner scrolling at a stated viewport size, or the task records why it cannot and what was chosen instead
- [ ] #3 The collapsed state does not get taller than it is today (686px on the detail surface, 800px for the compact popup) - fitting the open state must not cost the win TASK-228 measured
- [ ] #4 TASK-216 still holds: the popup reaches its final size on first render and slow provider discovery does not resize it
- [ ] #5 Still works at 360px and 430px, verified by the same-origin iframe method TASK-228 used, with any multi-column layout collapsing to one column there
<!-- AC:END -->
