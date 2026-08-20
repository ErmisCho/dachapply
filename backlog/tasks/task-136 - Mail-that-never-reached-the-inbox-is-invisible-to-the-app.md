---
id: TASK-136
title: Mail that never reached the inbox is invisible to the app
status: Done
assignee: []
labels:
  - backend
  - mailbox
  - data
priority: high
ordinal: 136000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-08-19: *"be able to capture the first email that shows that I applied for a role."*

That email is not in the app, and no amount of re-running the check will find it. Measured:

    subject contains "applying"   -> 0 rows
    subject contains "get to know" -> 1 row, and it is the Google Calendar NOTIFICATION,
                                      classified not_job_related, matched to no job
    earliest message in the log:  2023-06-26

So the log reaches back over two years, and still does not contain *"Thank you for applying to
zooplus as Senior Software Engineer"* from 3 June — a message plainly visible in the owner's Gmail.

The cause is one line in `GmailApiTransport.fetch_new`:

    params = {'labelIds': 'INBOX'}

**The app only ever reads the inbox.** Anything archived, or filed into a label and skipped past the
inbox, has never been fetched and never will be. In the owner's Gmail screenshot the missing message
carries its own labels and no Inbox chip — it was archived, so it is invisible.

TASK-132 partly masked this: thread ingestion pulls in whatever else is in a thread the app already
knows, which is why the owner's own replies appeared. But a thread the app never saw at all stays
missing, and an application confirmation is usually the FIRST message of its own thread — precisely
the case thread-following cannot rescue.

### Why this is the most valuable message in the mailbox

It is the one that proves an application exists, dates it, and names the role. It is what
`applied_at` and the whole feedback clock are guesses about. Missing it means the app's picture of
the search starts halfway through.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Mail that is not in the inbox is reachable: the specific message *"Thank you for applying to zooplus as Senior Software Engineer"* (3 June, archived) is present in the log after this ships — named because it is the case that proved the gap
- [x] #2 The change is a deliberate scope decision, recorded: reading all mail rather than the inbox means the app sees far more, including things the owner filed away on purpose. State what is now read and why, in the code and in this file
- [x] #3 The volume does not run away: the owner's mailbox already yielded 641 messages from the inbox alone. State the bound (date floor, query, cap) and report what was skipped rather than discovering it as a surprise
- [x] #4 The resume marker still works: `run_check` resumes from `MAX(internal_date_ms)`, and widening the query must not make a future run re-read the whole mailbox or skip new mail. Verified by running a check twice and asserting the second fetches nothing new
- [x] #5 An application-confirmation message is recognised as such rather than landing as `not_job_related` — it is the evidence that an application exists, and TASK-109's classifier has no category for it today
- [x] #6 Existing behaviour is preserved: TASK-114's bulk/board guards still refuse to draft at newsletters, and widening the fetch must not resurrect the class of mail those guards exist to ignore. Verified by test, since a wider net catches more marketing
- [x] #7 Backend tests cover the widened query, the resume marker across two runs, and the bound; no test contacts a real mailbox
- [x] #8 Run against the owner's real mailbox with before/after counts recorded here — 653 messages and a missing 3-June application email are the numbers to beat
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20 close-out (evidence: backend suite 783 green; browser measurements on the built bundle at localhost:8000; prod-DB reads and app-command runs with the owner's approval; merges #51/#52/#53 live with HTTP 200): What the fetch reads now (AC2's in-file statement): everything in the mailbox except Spam and Trash - inbox, archived, filed, auto-labelled and sent mail alike - bounded by the resume marker plus FETCH_HISTORY_FLOOR_DAYS on a cold start, with backfill_historical_mail as the explicit marker-ignoring one-off for older mail. AC1/AC8: the 3 June zooplus confirmation is stored (count 1); totals 653 (pre-widening) -> 940 (task-time) -> 1000 today.

The narrow change is dropping `labelIds: 'INBOX'` (or swapping it for a Gmail `q=` that includes
archived mail). The care is in AC3 and AC6: the inbox filter has been doing double duty as a volume
bound and as a crude relevance filter, and removing it removes both at once.

A date floor is the obvious bound and should be chosen against real data — the log's earliest message
is 2023-06-26, so "everything" is years of mail. `after:` is already used by `fetch_new` for the
resume marker and is the same mechanism.

AC5 is a classifier change, not a fetch change, and is worth keeping separate in the diff:
`_classify_heuristic` has `rejection`, `interview_invitation`, `offer`, `recruiter_reply`,
`uncertain`, `not_job_related` — nothing for "your application was received". Adding a category
touches `MailboxMessage.CLASSIFICATIONS`, the digest, and the suggestion rules, so decide whether it
proposes anything (an `applied_at` date, perhaps) before adding it.

Beware the interaction with TASK-114: a wider fetch means more board and marketing mail reaching
classification. Those guards are tested and must stay tested — this is exactly the kind of change
that quietly re-opens a closed incident.
<!-- SECTION:NOTES:END -->
