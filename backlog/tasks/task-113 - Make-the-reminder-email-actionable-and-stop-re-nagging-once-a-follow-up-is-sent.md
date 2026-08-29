---
id: TASK-113
title: >-
  Make the reminder email actionable and stop re-nagging once a follow-up is
  sent
status: Done
assignee:
  - '@pi'
created_date: '2026-08-17 19:38'
updated_date: '2026-08-29 08:57'
labels:
  - product
  - email
  - backend
  - frontend
dependencies:
  - TASK-86
  - TASK-110
priority: high
ordinal: 113000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Two features already do their halves and never meet. TASK-110 writes a ready-to-send reply into the
owner's real Gmail Drafts folder (112 of them on the first live run). TASK-86 emails a daily reminder
digest of due follow-ups and overdue feedback. The reminder email does not know the draft exists, and
the draft does not know anyone was reminded about it.

So today the reminder says *that* something is due and nothing else. `digest_body`
(`backend/jobradar/services/followup_digest.py:40-53`) emits plain text — `- {company} - {title} - due
{date}` — plus one link to the board root. No per-item link, no mention of a draft, no way to reach
either the draft or the job from the mail. Acting on a reminder means: open the app, find the job,
remember the thread, switch to Gmail, find the draft among the others, read it, send it.

Three concrete gaps make the connection impossible right now, not merely absent:

1. **The draft's identity is thrown away.** `GmailApiTransport.append_draft`
   (`backend/jobradar/services/mailbox.py:331-342`) calls `users.drafts.create` and discards the
   response, so the Gmail draft id never reaches the database. `MailboxDraft` (`models.py:353-374`)
   stores subject and body but no draft id, and `RawMessage.thread_id` is documented as
   *"transient, never persisted"* (`mailbox.py:76`). Without one of those ids there is no URL that
   opens the draft — this is the prerequisite for everything else here.
2. **Nothing records that a follow-up went out.** `FollowUp` (`models.py:167-174`) has a `completed`
   boolean and no date. `updated_at` is `auto_now` and moves on any unrelated save, so it cannot
   stand in for "the day I sent it".
3. **Sending a follow-up does not quiet the reminder.** `digest_items`
   (`followup_digest.py:32-37`) has two halves. Completing the `FollowUp` silences the first. The
   second — `jobs.filter(feedback_due_date__lte=today)` — keeps listing that job **every single day
   forever** until `feedback_due_date` moves or the status closes. A "mark it done" that only touches
   the FollowUp row leaves the user still being nagged about the job they just answered, which is the
   exact complaint this task exists to fix.

The email side needs no invention: `views.py:397-427` already sends an HTML mail with a real button
(password reset), and `send_mail(..., html_message=...)` is the same one kwarg here. The context page
needs no new route either — `/jobs/:id` (`App.tsx:348`) already renders the job with its notes and
follow-ups, and `Detail` is where the draft card belongs.

**Scope decision, deliberate and reversible in one sentence: the app still never sends mail.** The
"send" action opens the prepared draft in Gmail, where sending is one click by the owner. TASK-110 AC1
made no-send a load-bearing guarantee — there is no send call site anywhere in the backend and the
test transport has no `send` method to accidentally call — and reversing it would need the
`gmail.send` OAuth scope, a re-consent, and its own decision record about a machine sending
salary-negotiation mail unattended. It is not smuggled in here. If the owner wants a literal in-app
send button, that is a separate task, filed explicitly, per TW-005.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `append_draft` returns Gmail's response ids and `MailboxDraft` persists them (draft id, message id, thread id); a draft written by a live run stores non-empty values, verified by reading the row after `uv run manage.py check_mailbox --force`
- [x] #2 Each due item in the reminder email that has a ready draft carries a direct link that opens **that** draft in Gmail — verified by clicking the link from the received mail and landing on the composed draft, not on the Drafts list (the working URL form and account-disambiguation segment are recorded in the notes, since Gmail's compose parameter is easier to get wrong than to guess)
- [x] #3 The same item carries a second button that opens the job in DACHApply, and that page shows, on one screen: what happened (the matched thread's sender, subject, date and classification, plus the job's status and existing notes) and the exact text that would be sent — the draft body verbatim, not a summary
- [x] #4 Items with no ready draft are honest rather than silently linkless: a guardrail-blocked draft shows its `block_reason` and no Gmail link; an item that never produced a draft says so
- [x] #5 The email renders as an HTML mail with real buttons and keeps a plain-text alternative whose links are still usable — reuse the `views.py:397` pattern; both parts are asserted by a test
- [x] #6 Confirming a follow-up was sent records the date on the FollowUp (a dedicated field, not `updated_at`) and appends a `follow_up` ApplicationNote to the job naming the draft that was sent
- [x] #7 Confirmation is available as an explicit action on the job page, and is also recorded automatically when the next mailbox check can prove it — the stored draft id is gone from Drafts **and** the thread has a newer message from the owner. Deletion alone must not count as sent (covered by a test)
- [x] #8 After a send is recorded, the job disappears from the reminder email until it is genuinely due again: the FollowUp is completed **and** `feedback_due_date` is pushed forward or cleared, so neither half of `digest_items` re-lists it. Pinned by a test that runs the digest the following day and finds the job absent
- [x] #9 If the send schedules a next follow-up, the reminder returns on that date and not before; if none is scheduled, the job stays quiet — asserted for both branches
- [x] #10 The app still sends no mail on this path: `grep -rn "messages.send\|smtplib" backend/jobradar/services/` surfaces no new call site, and the review page's send button is a link to Gmail
- [x] #11 `cd backend && uv run pytest -q` passes with new tests covering AC5-AC9; `npx tsc --noEmit` and `npm test` pass. No test touches a real mailbox
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reuse TASK-121's persisted Gmail ids and single URL builder, adding the exact-draft form and actionable HTML/plain digest rows. 2. Add dedicated sent timestamps and one atomic confirmation function that completes the due follow-up, clears the feedback clock, records a note, and optionally schedules the next follow-up; reuse it for manual and proven automatic confirmation. 3. Show captured thread context plus the verbatim draft and explicit confirmation on the existing job detail page. 4. Cover deletion-only, digest quiet/reschedule, ownership, MIME alternatives, and UI behavior; then run live read-only/link checks, full gates, Asian Dad eval, and squash-merge.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Filed 2026-08-17 from the owner's own description of the flow they want: *"when I receive an email with
my reminders, this means a draft is already prepared — I click a link, see what was going on and what
is going to be sent, send it, and then the platform logs the date and stops notifying me about that
job until I should follow up again."*

Order of work — AC1 first and alone. Everything else is unbuildable without a persisted draft id, and
it is the smallest change in the task: capture the `users.drafts.create` response instead of throwing
it away (`mailbox.py:342`), add three CharFields to `MailboxDraft`, migrate. The 112 drafts already in
the owner's mailbox pre-date this and will have empty ids; that is fine, they are not what the reminder
links to.

Reuse before building:
- HTML mail with a button already exists at `views.py:397-427` — copy its table/inline-style shape
  rather than adding a template engine or an email library.
- The context page already exists. `Detail` at `/jobs/:id` renders notes and `JobFollowUps`
  (TASK-77); the draft card goes there. Do not add a `/drafts/:id` route.
- The link from the email points at that existing authenticated route. A signed one-click token is
  **out of scope** — the owner is the only recipient and normal login is enough. Adding token auth
  would mean a mail that acts on the account without a session, which is a bigger security surface
  than this feature is worth.
- Joining a digest item to its draft is `job` → `MailboxDraft.objects.filter(job=..., status='written')`,
  latest first. Both models already point at `JobLead` (`models.py:328`, `models.py:363`); no new
  relation is needed.

AC8 is the one most likely to be quietly half-done. The obvious implementation marks the FollowUp
complete, passes its own test, ships, and the user keeps getting the identical daily mail — because
the *other* half of `digest_items` fires off `feedback_due_date`, which nothing touched. Write the
test as "run `send_due_digests()` again the next day and assert this job is not in the body", not as
"assert `followup.completed is True`". The first is the promise; the second is an implementation
detail that can be true while the promise is broken.

AC7's automatic detection is the nice half and should not hold up the manual one. `GET /drafts/<id>`
returning 404 means *gone*, which is "sent" or "deleted by hand" — indistinguishable on its own,
which is exactly why the second condition (a newer message from the owner in the same thread) is in
the AC rather than left to judgement. When both cannot be established, fall back to the explicit
action and record nothing.

Gmail deep-link caveat worth measuring rather than assuming: the compose URL takes the draft's
*message* id, not the draft id, and the `/u/0/` segment addresses whichever Google account happened to
sign in first. Persist both ids (AC1 asks for both) and use the account address in the path segment so
the link cannot open the wrong mailbox. AC2 is written as "click it and see where you land" for this
reason — per TW-004, a URL format recalled from memory is a hypothesis.

Related: [[TASK-86]] is the reminder email being made actionable, [[TASK-110]] is the draft being
linked to, [[TASK-109]] owns the mailbox check that AC7's detection rides on, [[TASK-77]] built the
follow-up UI the confirmation action extends.

Validation 2026-08-29:

- Reused TASK-121 persistence and the single Gmail URL builder. A forced live Gmail-API run (run 39) fetched 29 messages and wrote draft row 120 with non-empty outer draft id `r-8981485646021395959`, draft message id `1a049f5579e5e1b4`, and thread id `1a0434dcf4512896`.
- Measured rather than assumed the exact URL. `/mail/u/<email>/` returned Gmail 404, so draft links now use the already-proven account selector: `https://mail.google.com/mail/u/0/?authuser=<percent-encoded-account>#drafts?compose=<gmail_message_id>`. Opening the generated row-120 link in the owner-authenticated browser resolved to the correct account (`/u/1/`) and opened the existing composed draft pane, not the Drafts list. No message was sent or edited; the tab was closed and the temporary screenshot deleted.
- Browser-verified the existing `/jobs/:id` screen with a disposable synthetic demo draft: status, matched message context, notes, verbatim body, explicit sent action, and optional next date were present together. Confirmation set matching FollowUp/MailboxDraft timestamps, cleared feedback, wrote one audit note, created the selected next date, and immediately removed the action. All fixture rows and notes were then removed and the demo state restored.
- Digest regression coverage proves HTML buttons plus plain links, exact Gmail/job URLs, blocked/no-draft wording, owner scoping, selected follow-up identity, feedback-only reminders, next-day silence, and optional rescheduling. Mailbox tests prove automatic confirmation only when a draft disappears AND a newer owner-authored same-thread message exists; either condition alone records nothing.
- Gates: 1025 backend tests passed; 191 frontend tests passed; TypeScript/Vite production build passed; Django checks, migration drift check, and compileall passed; npm audit reports 0 vulnerabilities. No test contacted a live mailbox. No Gmail send or SMTP call site exists; grep hits only no-send comments/docstrings/tests.
- Asian Dad Eval: PERFECT across all 10 sealed binary criteria (self-graded rubric disclosed).

Implementation squash-merged in PR #91 as 983fcb70b1c69fcf5ac9ca7976da7ea9581710b1. Task marked Done only after the implementation reached main.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Made reminder emails actionable with exact Gmail-draft and job buttons, honest missing/blocked states, a one-screen job context, durable sent timestamps/audit notes, conservative mailbox reconciliation, and optional next scheduling. Verified with live Gmail ID persistence and exact-link opening, synthetic browser confirmation/cleanup, 1025 backend tests, 191 frontend tests, production build, Django checks, zero npm audit findings, and Asian Dad PERFECT.
<!-- SECTION:FINAL_SUMMARY:END -->
