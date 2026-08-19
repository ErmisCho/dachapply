---
id: TASK-131
title: purge_app_drafts body matching misses its own drafts by a leading dot
status: In Progress
assignee: []
labels:
  - backend
  - mailbox
  - bug
dependencies:
  - TASK-114
  - TASK-121
priority: medium
ordinal: 131000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-19 while checking whether the owner had duplicate drafts worth deleting.

`purge_app_drafts` identifies the drafts this app wrote by comparing the Gmail draft's body, after
whitespace normalisation, against `MailboxDraft.body_text`. TASK-114 chose that over a template
signature deliberately: `drafts.delete` is permanent with no Trash, so a draft the owner typed by hand
must be unmatchable by construction.

It does not match its own draft. Measured against the owner's live mailbox:

    gmail len 213 | stored len 212 | identical: False
    GMAIL  : .Thank you for the update on my application for Senior Software Engineer...
    STORED : Thank you for the update on my application for Senior Software Engineer...

A single leading `.`. Nothing was edited — that is mail transport, where a line beginning with a dot
is escaped on the wire (RFC 5321 dot-stuffing) and comes back with the escape intact through the
raw-message read. `_normalized_body` strips whitespace per line, so it never sees it.

### Why it matters even though it fails safe

The failure direction is the safe one: an unmatched draft is left alone, never wrongly deleted. But
the consequence is that **`purge_app_drafts` silently under-reports**. An owner running it to clean up
gets "nothing to do" for drafts the app definitely wrote, and the only signal is a count they have no
reason to distrust.

It matters more now than when TASK-114 wrote it. Since TASK-121 the command prefers the stored
`gmail_draft_id`, so this fallback only governs rows written BEFORE that — which is exactly the
back-catalogue an owner would reach for the command to clean.

There is also a trap for whoever fixes it: the obvious repair is to strip a leading dot, and the
obvious over-correction is to loosen the comparison generally. Loosening it moves the failure to the
dangerous side, where a hand-written draft that happens to resemble the template becomes deletable.
The safety argument in TASK-114's notes is the thing to preserve, not the exact string comparison.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A draft this app wrote is matched by the body-text fallback despite transport-level dot escaping — asserted with the real observed shape (a body identical except for a leading `.`)
- [x] #2 The safety property TASK-114 established is unchanged and re-asserted by test: a draft whose body the owner altered is NOT matched, and therefore never deleted
- [x] #3 The fix is specific to the escaping artefact, not a general loosening of the comparison — a body differing by real content, however slightly, must still fail to match
- [ ] #4 Verified against the owner's actual mailbox that the previously-unmatched draft is now recognised, reported as a count rather than acted on — no deletion is required to close this
- [x] #5 Backend tests cover the dot-escaped match, the edited-draft non-match, and the id-preferred path continuing to bypass body matching entirely
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-19: implemented in _normalized_body (one leading '.' stripped per line, RFC 5321 cited in the
docstring; comparison stays exact). Five tests cover the dot-escaped match, per-line unstuffing, the
owner-edited non-match, real-content non-match, and the id-preferred bypass; suite 766 passed.
AC4 blocker: needs `DACHAPPLY_ALLOW_PROD_DB=1 uv run python manage.py purge_app_drafts` (dry run)
against the real mailbox — prod-DB opt-in, owner's call.

`_normalized_body` (`mailbox.py`) is the one place to change. It already normalises line endings and
trailing whitespace; unescaping a leading `.` per line is the same class of transport-artefact
normalisation and belongs beside it, with a comment naming RFC 5321 so it does not read as arbitrary.

Do not "fix" this by comparing a prefix, a length, or a similarity ratio. The whole point of exact
matching is that a hand-written draft cannot collide with it.

Worth confirming while in there whether the escape appears only at the start of the body or on every
line beginning with a dot — the observed sample only shows the first line, and a body containing a
line starting with `.` further down would exercise the same rule.
<!-- SECTION:NOTES:END -->
