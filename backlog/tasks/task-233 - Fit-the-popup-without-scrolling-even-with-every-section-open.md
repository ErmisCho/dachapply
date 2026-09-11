---
id: TASK-233
title: Fit the popup without scrolling even with every section open
status: To Do
assignee: []
created_date: '2026-09-11 11:21'
updated_date: '2026-09-11 20:08'
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
- [ ] #1 With every section open, the popup fits a laptop screen without inner scrolling - stated as measured pixels against a stated laptop viewport (1920x1080 at 100% and 1536x864 at 125% scaling are the realistic cases), not against the owner large monitor
- [ ] #2 Scrolling still exists as a safety net for the cases that cannot fit (360px, a long generation report), and is not removed - it simply is not reached in the normal fully-open state
- [ ] #3 The collapsed state does not get taller than it is today, and the popup does not become so wide that it stops being the compact thing TASK-228 made it
- [ ] #4 TASK-216 still holds: the popup reaches its final size on first render and slow provider discovery does not resize it
- [ ] #5 Still works at 360px and 430px, verified by the same-origin iframe method TASK-228 used, with any multi-column layout collapsing to one column there
- [ ] #6 The height with every section open is measured before and after, same job and viewport, alongside the collapsed height
<!-- AC:END -->
