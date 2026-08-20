---
id: TASK-145
title: Board defaults to attention order and remembers a saved multi-sort
status: Done
assignee: []
labels:
  - backend
  - frontend
  - board
priority: high
ordinal: 145000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner instruction 2026-08-19: *"by default the applications that are new should be at the top of the
job board, and then the ones that they are in the stage of interview. (make it that I can make
multiple sorts through a setting)"*

Asked which of two readings they meant, the owner chose **attention order**, explicitly and with the
alternative in front of them:

    New            <- group 1
    New
    Interview      <- group 2
    Interview
    ------------------------------
    Reviewed / To apply / Applied / Offer / Accepted   (pipeline order)
    rejected / withdrawn / skipped / archived           (last)

Not pipeline order, in which Interview is fifth rather than second. They also declined the variant
that keeps `stale_rank` as the top key, so overdue follow-ups no longer float above everything by
default.

For the saved sort, the owner chose **per account, synced** — stored on `UserProfile` beside the
mailbox settings, not in `localStorage` beside the filters.

### What already exists, and must not be rebuilt

Most of the machinery is here and is good:

- `nextSortKeys(current, key, max=3)` and `sortOrderingString` in `appUtils.ts` — click-driven
  multi-sort, up to three keys, already tested.
- The wire contract `?ordering=status,-fit_score` and `parse_board_ordering` in `views.py`, which
  allowlists keys through `BOARD_ORDERINGS` specifically so a client cannot order by an arbitrary
  related column (`?ordering=-created_by__password`) and read values off the row order. That guard is
  security, not tidiness, and stays.
- `_status_pipeline_rank()`, generated from `JobLead.STATUSES` so a new status cannot silently fail
  to sort.
- `test_board_ordering.py` already covers this area.

What is missing is only the two things asked for: the default is
`('stale_rank', 'status_rank', 'priority_rank', '-evaluations__fit_score', '-created_at')`, which is
neither of the owner's groups; and the chosen sort is component state that does not survive a reload.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The default board order puts `new` first and `interview` second as GROUPS, with every other status following in pipeline order and `rejected`/`withdrawn`/`skipped`/`archived` last — verified by asserting the actual row order returned for a fixture covering all eleven statuses, not by reading the ordering tuple
- [x] #2 The attention rank is generated from `JobLead.STATUSES` rather than restated as a second literal list, the way `_status_pipeline_rank()` already is — a status added to the model must not silently sort into an arbitrary position
- [x] #3 `stale_rank` is demoted, not deleted: the owner chose the variant WITHOUT staleness on top, so it must no longer lead, but it stays as a later key so ordering within a group is unchanged. State where it now sits
- [x] #4 A saved multi-sort persists per account: a `UserProfile` field storing the sort, with a migration, so the same order appears on another device — the owner explicitly chose this over `localStorage`
- [x] #5 The saved sort is editable from a settings menu, not only by clicking table headers, and clicking headers still works exactly as it does today
- [x] #6 A saved sort survives a reload AND the header arrows reflect it: today `sortKeys` is `useState([])` while `f.ordering` rides along in `dachapply_filters`, so the two can already disagree after a reload. They must agree
- [x] #7 `parse_board_ordering`'s allowlist still refuses an unknown or hostile key, and a saved value containing one degrades to the default instead of erroring or reaching `order_by()` — verified by a test that feeds it `-created_by__password`
- [x] #8 An empty or absent saved sort falls back to AC1's new default, and clearing the setting is possible — a user must be able to get back to the default without editing the database
- [x] #9 The three-key maximum still holds end to end, and a saved value with more keys is truncated rather than honoured
- [x] #10 `test_board_ordering.py` passes with its existing cases intact plus the new ones; the full backend suite passes unchanged; `npx tsc --noEmit` and `npm test` clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20 close-out (evidence: backend suite 783 green; browser measurements on the built bundle at localhost:8000; prod-DB reads and app-command runs with the owner's approval; merges #51/#52/#53 live with HTTP 200): AC4 shipped in #52: an absent ?ordering= falls back to profile.board_sort_keys through the same parse_board_ordering path (explicit param wins; hostile saved values degrade; four new tests). The other eight ACs were already test/code-proven; #6's must-clause holds by construction (sortKeys derives from f.ordering) and the saved sort now genuinely survives to another device.

AC1 and AC2 pull in the same direction and are the whole backend job: one more `Case/When` built from
`JobLead.STATUSES` that maps `new -> 0`, `interview -> 1`, and everything else to `2 + its pipeline
index`, with the closed statuses last. Written that way the owner's grouping and the existing pipeline
order are the same expression, and no list is typed twice.

AC6 is a pre-existing inconsistency this task inherits rather than creates. `f.ordering` is already
persisted inside `dachapply_filters`; `sortKeys` — the state that draws the arrows — is not. Moving
the source of truth to the profile field is the chance to make one of them derive from the other
instead of adding a third copy.

Do not widen `BOARD_ORDERINGS` to make the new default expressible. The default is server-side and
does not go through the allowlist; the allowlist exists for client-supplied keys and widening it for
convenience is how the guard in its docstring gets defeated.
<!-- SECTION:NOTES:END -->
