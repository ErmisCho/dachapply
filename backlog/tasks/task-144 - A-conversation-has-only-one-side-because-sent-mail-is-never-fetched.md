---
id: TASK-144
title: A conversation has only one side because sent mail is never fetched
status: In Progress
assignee: []
labels:
  - backend
  - frontend
  - mailbox
dependencies:
  - TASK-138
priority: high
ordinal: 144000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-08-19: *"I no longer see the conversation with left and right so I can easily
understand who is who."*

The left/right rendering works — measured on the board today, an owner message is
`rgb(37,99,235)` at x=805 and the other party's is slate at x=52. The problem is that there is almost
nothing to put on the right:

    owner-sent messages in the whole log:  10 of 940

    job  36  PIDSO       56 messages   0 from the owner
    job 760  Deltia AI   17 messages   0 from the owner
    job 656  Dynatrace   13 messages   0 from the owner
    job 462  DataScience  8 messages   0 from the owner
    job 353  Ahoi Kapptn  8 messages   0 from the owner
    job  37  zooplus      9 messages   4 from the owner
    job  44  Takeda      12 messages   2 from the owner
    job 779  SQUER        9 messages   2 from the owner

Nine of the twelve busiest conversations are entirely one-sided, so they render as a column of
identical left-hand bubbles. That is not a rendering bug, it is missing data.

The cause is what the app fetches. `fetch_new` reads mail that arrived; the owner's own replies live
under Gmail's `SENT` label and are never fetched. The 10 that exist arrived by accident of TASK-132's
thread ingestion, which pulls in whatever else is in a thread the app already knows — so the owner's
reply is captured only when the recruiter had already written into that same thread.

An application conversation almost always begins with the owner writing first. That message is the
one the app is least likely to have.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The owner's own sent mail is fetched, so a conversation has two sides: at least one job that currently shows 0 owner messages shows the owner's own replies afterwards, named in this file with before/after counts. 10-of-940 is the number to beat
- [ ] #2 A fetched sent message is stored with `sent_by_owner=True` and renders on the owner's side — the existing left/right rendering must be what displays it, not a second code path
- [ ] #3 Sent mail never produces a suggestion, a draft, or a reply-to-yourself: the classifier and suggestion rules must not treat the owner's own words as a recruiter's. Verified by test, because this is the failure that would put a draft reply to the owner's own email in Gmail Drafts
- [ ] #4 The volume stays bounded by TASK-141's lookback window — sent mail is subject to the same six-month bound as received mail, not a second unbounded fetch
- [ ] #5 Sent mail that belongs to no tracked job does not flood the unmatched list: state how it is scoped (thread membership, matched job, or query) and what is skipped
- [ ] #6 TASK-137's matching still holds: a sent message is matched by the thread it belongs to, not by its recipient's domain, since the owner sends *to* ATS addresses and matching on those is the exact bug TASK-137 fixed
- [ ] #7 Two-sided rendering is verified in a browser, with a screenshot-equivalent measurement: in one real conversation, at least one bubble measures on the left and one on the right, with different backgrounds
- [ ] #8 The resume marker and TASK-141's bound both still hold with the extra query in place: two consecutive runs, the second fetches nothing new
- [ ] #9 Backend tests cover the sent-mail query, the `sent_by_owner` flag, and the no-suggestion guarantee; the existing suite passes unchanged; no test contacts a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`GmailApiTransport` already knows how to query with `labelIds` — TASK-136's whole argument was about
removing `INBOX` from it. `SENT` is the same mechanism pointed at a different label, and
`sent_by_owner` already exists on the model and is already honoured by the frontend, so the rendering
half of this task should be nothing.

AC3 is the dangerous one and deserves the test written first. `_classify_heuristic` takes a subject
and body and has no idea who sent it; a sent message full of "thank you for the invitation" reads
exactly like a recruiter's mail to it. The guard belongs where suggestions are generated, keyed on
`sent_by_owner`, not on a keyword.

AC6 matters for the same reason. The owner's sent mail is addressed to `no-reply@ashbyhq.com` and
friends, so any matching that looks at the *recipient* domain rebuilds TASK-137's bug pointing the
other way. Thread membership is the honest key and `thread_id` is populated on every row.
<!-- SECTION:NOTES:END -->
