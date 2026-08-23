---
id: TASK-174
title: Move unmatched mail off the board and default it off
status: To Do
assignee: []
labels:
  - frontend
  - mailbox
  - ux
dependencies:
  - TASK-163
  - TASK-171
priority: high
ordinal: 174000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-23: *"I am finding too much trouble to have the unmatched email attach to a job thing,
like maybe this menu can be toggled and under mailbox instead of in the homepage and the default mode
would be to not show this."*

The unmatched-mail list is rendered inside the `mailbox_review` dashboard panel on the board — the
first thing the owner sees on the home page. Four tasks have now been spent making it smaller and
more actionable (TASK-161 ranking, TASK-163 suggestions and parking, TASK-169 the identification
window, TASK-171 preview and dismiss), and it went from 321 rows to 7 at an explicit 3-month window.

It is still the wrong place for it. Attaching mail to a job is a **maintenance chore**, done in
batches when the owner chooses; the board is for **today's decisions**. Every row of chore on the
home page competes with the thing the board exists for.

Note what is NOT being asked for: the feature itself is fine and stays. This is about where it lives
and whether it is on by default.

**Most of the mechanism already exists.** Panels can be hidden today — `DashboardPanel` has a Hide
action and the hidden set persists in `localStorage` under `dachapply_dashboard_panel_hidden`. What
does not exist is: this panel being hidden by DEFAULT for a new or existing user, and the same list
being reachable from `/mailbox`, which is where the owner expects mailbox work to live and which
already carries the runs, the suggestions and the manual-run control.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The unmatched-mail list is reachable from the Mailbox page, showing the same rows in the same order with the same controls it has on the board today (rank order, suggestions pre-filled, preview, attach, dismiss, and every reveal count)
- [ ] #2 It is NOT shown on the board by default — for an existing owner whose `localStorage` has no preference recorded, and for a brand-new account
- [ ] #3 The owner can still turn it back on from the board's existing panel controls; the default is a default, not a removal
- [ ] #4 It is not rendered twice at once in a way that double-fetches: state how the two locations share (or do not share) their data, and measure the request count on each page
- [ ] #5 An owner who had previously hidden or shown that panel keeps their choice — the new default applies only where no preference exists, so this change does not silently override a deliberate setting
- [ ] #6 Nothing else moves: the Email Decisions panel and the rest of the board are untouched, verified by the panel list before and after
- [ ] #7 Verified in a browser: board does not show it, Mailbox does, attach still works end to end from the new location
- [ ] #8 Frontend typecheck and tests green; `localhost:8000` loads both pages without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Do not delete the panel or the board code path — AC3 requires it to remain switch-on-able, and AC5
requires an existing explicit preference to survive. The distinction that matters is "no preference
recorded" versus "explicitly set to shown", and `dachapply_dashboard_panel_hidden` currently records
only the hidden set, so absence is ambiguous. Decide how to represent "never chose" and say so.

The Mailbox page is currently slow for an unrelated reason (TASK-172, `/api/mailbox-runs/` shipping
1.27MB). Land that first or this list will inherit a 36-second page.
<!-- SECTION:NOTES:END -->
