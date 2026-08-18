---
id: TASK-129
title: Detach the job-board newsletters TASK-114 left attached to jobs
status: Done
assignee:
  - '@claude'
labels:
  - backend
  - mailbox
  - data
priority: high
ordinal: 129000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-114 stopped job-board mail from matching tracked jobs. It never detached the rows that had
already matched. Measured against production 2026-08-18 while scoping TASK-127:

    messages attached to job 538 (Broadpin powered by PROMATIS): 95
      66 x XING Jobs <jobs@mail.xing.com>
      29 x XING <info@e-mail.xing.com>
      classifications: {'recruiter_reply': 95}

Every one is a XING newsletter. None is correspondence about that application. They are attached
because `owned_job_domains()` used to map a lead saved from `xing.com/jobs/...` to the board's own
domain, so every mail XING ever sent matched an arbitrary tracked job — the defect TASK-114 diagnosed
and fixed going forward.

Left alone this is mostly invisible. It stops being invisible the moment TASK-127 renders "the whole
conversation about this company", because Broadpin's conversation is ninety-five advertisements. It
also skews anything that counts mail per job.

### Why this is not just a delete

`MailboxMessage` is the append-only log of everything `check_mailbox` read (TASK-109 AC5), and that
guarantee is worth keeping — the rows are evidence of what the app did, including what it got wrong.
What is wrong is not that the rows exist, it is that `matched_job` points at a job the message has
nothing to do with. Clearing the association preserves the log and removes the false claim.

The messages are also the reason 112 unwanted drafts existed (TASK-114's live incident). Those drafts
are already deleted; their `MailboxDraft` rows remain and point at the same wrong jobs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Messages whose sender is a job board (the existing `is_job_board()` — no second list) have their `matched_job` cleared, and the count cleared is reported. The rows themselves are NOT deleted: the append-only log survives, only the false association goes
- [x] #2 A dry run is the default and prints what WOULD change, per job, before anything is written — the same shape `purge_app_drafts` uses, and for the same reason: this touches production data the owner cannot easily reconstruct
- [x] #3 Pending `MailboxSuggestion` rows derived from those messages are dismissed rather than left proposing changes to a job from a newsletter — verified by counting pending suggestions before and after
- [x] #4 Nothing that is genuine correspondence is touched: a message from an employer domain that merely mentions a board, or a real recruiter reply, must be unaffected — asserted by test with both kinds present
- [x] #5 It is idempotent: running it twice changes nothing the second time and says so
- [x] #6 Run against production, with the before/after counts recorded in this file — the 95 on job 538 is the number to beat, and the result must be checked rather than assumed
- [x] #7 Backend tests cover the board-sender match, the employer-sender exclusion, suggestion dismissal and idempotency; no test touches a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`is_job_board()` and `JOB_BOARD_DOMAINS` already exist from TASK-114 and are the right predicate —
matching on the message's SENDER domain, not the job's URL. Do not introduce a second list; if a
board is missing from it, add it there so the live path benefits too.

A management command in the shape of `purge_app_drafts` (dry run by default, `--yes` to act, prints
what it matched) is the obvious home, and gives the owner the same review-before-commit flow they
already know.

AC4 is the one that needs care. The predicate must look at the sender, and a genuine reply forwarded
through a board's relay is the awkward case — if one is found, prefer leaving it attached and say so
in the output. Detaching real correspondence is worse than leaving a newsletter attached, because the
newsletter is merely noise while the reply is the record of an application.
<!-- SECTION:NOTES:END -->

## Outcome (2026-08-18) — run against production

`detach_job_board_messages` (dry run by default, `--yes` to act), shaped like `purge_app_drafts` so
the owner gets the same review-before-commit flow. Matches on the message's SENDER domain via the
existing `is_job_board()` — no second list, and nothing was missing from `JOB_BOARD_DOMAINS`.

The dry run earned its place. It showed the command would dismiss **five of the owner's nine pending
suggestions**, which is exactly the moment to check rather than proceed. Checking proved all five
came from marketing mail:

    job 461  Stepstone <info@email.stepstone.at>          classified interview_invitation
             "Ermis, bist du bereit fuer den naechsten Karriereschritt"
    job 535  "devjobs.at Wunschjob" <wunschjob@devjobs.at>  x4
             "Wir haben den perfekten Job fuer dich gefunden!"

The Stepstone advert had been classified an **interview invitation** and was proposing to set an
interview date on a real job. The devjobs.at four are verbatim the newsletter TASK-114 was filed
about.

Applied:

    Detached 100 message(s) across 3 job(s); dismissed 5 pending suggestion(s).
      job 461 (DataScience Service GmbH):  1 message,  1 pending suggestion
      job 535 (Formunauts):                4 messages, 4 pending suggestions
      job 538 (Broadpin powered by PROMATIS): 95 messages, 0 pending suggestions

    before: 9 pending suggestions, 95 XING newsletters on job 538
    after:  4 pending suggestions (3 zooplus, 1 Deltia AI), 0 on job 538
    log:    653 message rows intact -- nothing deleted, only the false association cleared
    re-run: "No job-board sender is matched to a job. Nothing to do."  (AC5, idempotent)

The owner's decision list went from nine items to four, and the five that disappeared were all
adverts. `MailboxDraft` rows from the same era are untouched: no AC asks for it, and `MailboxDraft.job`
points at `JobLead`, not at the message, so clearing `matched_job` does not affect them. Worth its own
task if those log rows ever matter.
