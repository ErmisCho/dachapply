---
id: TASK-130
title: One conversation, one draft, one decision, and show the full thread
status: In Progress
assignee: []
labels:
  - backend
  - frontend
  - mailbox
  - bug
dependencies:
  - TASK-127
priority: high
ordinal: 130000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-08-19, looking at the grouped conversation card TASK-127 shipped: *"one drafted
reply is enough"* and *"I want to be able to see the whole conversation with them in one window, no
previews."*

TASK-127 grouped the CARD by job but left everything inside it per-message, so a three-message
conversation renders three of everything. Measured against production the same day:

    pending suggestions for job 37 (zooplus):
      feedback_clear  msg 653
      feedback_clear  msg 393      <- three identical proposals, same job, same type
      feedback_clear  msg 391

    written drafts per job:  job 37 -> 3   (identical text, one per message)

This is not only a display repeat. The backend really did create three identical
`MailboxSuggestion` rows and write three identical drafts into Gmail. Confirming one clears the
feedback clock; the other two remain pending, still asking for a decision that no longer means
anything. And the owner's Gmail Drafts folder has three copies of the same reply.

Two causes, both in `build_suggestions`/`maybe_draft_reply`: they run per message with no awareness
that another message on the same job already produced the same proposal, or already has a draft
waiting.

### The second half: the conversation is still previews

The card shows the newest message's body in a small scroll box, and then a *"FULL CONVERSATION
(3 MESSAGES, NEWEST FIRST)"* list that is only subject + sender + an "Open in Gmail" link. So the
owner cannot read the exchange without leaving the app — which is the thing the whole feature was
for. They asked for the bodies, in one window, without previews.

Note this reverses part of TASK-127 AC4's bounding, which existed because one job carried 95
messages. TASK-129 has since detached those (they were XING newsletters), so real conversations are
small — the zooplus one is three messages. The bound should follow the real shape now, not the
polluted one.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 One pending proposal per (job, type): `build_suggestions` does not create a second pending `feedback_clear` (or `status_change`, or `interview_date`) for a job that already has one pending — verified by a test that runs it twice over two messages on the same job and asserts one row, not two
- [x] #2 The duplicates already in production are cleaned up, with the count reported — job 37 currently has three identical pending `feedback_clear` rows and the owner sees three identical decisions
- [ ] #3 One drafted reply per conversation, not per message: a job that already has a written, undecided draft does not get another one written into Gmail. Verified against the real state — job 37 currently has three identical drafts in the owner's Drafts folder
- [x] #4 The conversation card shows every message's FULL body inline, in one window, with no "preview" that requires opening Gmail to read the text. "Open in Gmail" stays as a way to reply there, not as the way to read
- [x] #5 A long conversation stays navigable without hiding content behind a link — state the approach (expand/collapse per message, page scroll, sticky header) rather than reintroducing a scroll box that truncates a body mid-sentence
- [x] #6 One conversation renders one set of actions: the accept/decline pair belongs to the conversation's proposals, deduplicated, not repeated per message
- [x] #7 Existing guarantees survive: one confirm/dismiss call per suggestion, no batching that half-applies, and the app still never sends mail
- [x] #8 Backend tests cover the dedupe at generation and the no-second-draft rule; `npx tsc --noEmit` and `npm test` clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20 close-out (evidence: backend suite 783 green; browser measurements on the built bundle at localhost:8000; prod-DB reads and app-command runs with the owner's approval; merges #51/#52/#53 live with HTTP 200): AC2: dedupe_pending_suggestions reports 'No job has more than one pending suggestion of the same type. Nothing to do.' - the job-37 triplicate was already decided away; re-run confirms nothing to do. AC4 observed: 8 of 8 bodies render full inline (1,259-1,892 chars each) in the panel conversation. AC3 stays unchecked: purge_app_drafts --yes permanently deletes Gmail drafts with no trash, so the deletion is the owner's action; the dry run lists the 2 matched drafts ready for it.

`build_suggestions` (`mailbox.py`) creates rows unconditionally because it was only ever called once
per message from `run_check`, and nobody asked what happens when three messages on one job each
trigger the same rule. The narrow fix is a "does a pending one already exist for this (job, type)"
guard inside it — which also makes `attach_message_to_job`'s idempotency guard redundant in the good
way, since both then rely on the same rule.

AC3's equivalent for drafts lives in `maybe_draft_reply`: it already refuses on classification and on
`bulk_mail_reason`; "this job already has a written draft the owner has not dealt with" is another
refusal of the same kind, in the same one entry point.

AC2 is a data cleanup like TASK-129's. Prefer the same shape: dry run by default, report per job,
`--yes` to act. Dismissing the extra rows is right — they are not wrong, merely redundant, and the
one that survives still carries the same payload.

AC4/AC5 pull against TASK-127 AC4's cap, which was written when one job had 95 messages. TASK-129
removed that pollution, so the honest bound now is per-message collapse (headers always visible,
bodies expandable, newest expanded by default) rather than a fixed scroll box — that shows the whole
conversation in one window without a 20-message job becoming a wall.

The three drafts already in the owner's Gmail are a separate cleanup: `purge_app_drafts` can remove
app-written drafts and already matches on the stored `gmail_draft_id`. Do not delete anything the
owner may have edited — that command's existing body-text safety rule is there for exactly this.
<!-- SECTION:NOTES:END -->
