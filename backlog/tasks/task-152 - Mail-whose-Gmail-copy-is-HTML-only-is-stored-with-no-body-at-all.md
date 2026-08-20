---
id: TASK-152
title: Mail whose Gmail copy is HTML-only is stored with no body at all
status: To Do
assignee: []
labels:
  - backend
  - mailbox
  - bug
dependencies:
  - TASK-132
priority: high
ordinal: 152000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-20 while investigating why `backfill_message_bodies` reports "126 attempted, 0
filled" and never shrinks.

The body parser asks the email library for a plain-text part and nothing else
(`services/mailbox.py`: `parsed.get_body(preferencelist=('plain',))`). A message whose Gmail copy
carries only `text/html` — which is most recruiter and ATS mail — therefore stores `body_text=''`
permanently. It is not a fetch failure and not a Gmail problem: the message is there and readable in
Gmail, and the app simply never looks at the part that holds it.

Measured against the owner's mailbox: **137 stored messages have an empty body**. A 12-row sample
(most recent first) fetched from Gmail:

    html-only, no text/plain part   11
    has a text/plain part            1     <- uid 934, stored empty anyway: second, separate case
    neither                          0
    fetch failed                     0

At least one of them (uid 913) is matched to **job 34**, so a real job conversation currently shows
a message with nothing to read in it. The owner sees an empty bubble and has to open Gmail — which
is the exact failure TASK-130 AC4 and TASK-134 were written to end.

This also explains the backfill's behaviour: those rows are re-attempted on every run, produce
nothing, and are counted as "failed or came back empty" forever. TASK-149 stopped the *phantom
fills*; this is the remaining, larger half of the same report.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A message whose only textual part is `text/html` is stored with readable body text — HTML converted to plain text (tags stripped, entities decoded, links preserved as text or dropped deliberately), not raw markup dumped into the field
- [x] #2 The conversion never emits markup that the conversation view would render as HTML: the existing "a literal tag stays literal" guarantee (TASK-134 #3, `decodeHtmlEntities` tests) still holds for the converted text
- [x] #3 A message that has a `text/plain` part keeps using it unchanged — HTML is the fallback, not the new preference, and no existing stored body changes meaning
- [x] #4 uid 934's case is explained and covered: it HAS a text/plain part and was still stored empty; state the cause and either fix it or file it separately with evidence
- [x] #5 `backfill_message_bodies` recovers the affected back-catalogue: run against the real mailbox, record before/after counts of empty bodies here (137 is the number to beat), and confirm the run terminates instead of re-attempting the same rows forever
- [ ] #6 Verified in the browser on one real, job-matched message (uid 913 on job 34 is the known case): its conversation bubble shows readable text where it showed nothing
- [x] #7 Backend suite green; new tests cover html-only conversion, plain-preferred-when-present, and the no-markup-leak guarantee, all with fixtures — no test contacts a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20, measured against the real mailbox after PR #56. AC5: empty bodies 137 -> 11 of 1000 (the 11 remaining are the attachment-only rows TASK-149 deliberately excludes). The backfill went from "126 attempted / 0 filled" on every run to "126 attempted / 126 filled", and the very next run reported "Attempted 0" - it terminates now instead of re-attempting forever. uid 913 on job 34 holds 2,653 characters beginning "Hello Ermis Chorinopoulos, We have received your application for the following job position/s Jira Plugin Dev...". AC2 re-checked against real data, not just fixtures: zero of the 1,000 stored bodies contain "<div" or "<b>", so the converter leaked no markup anywhere in the corpus. AC6 stays unchecked and is NOT this task's failure: the app has nowhere to display a body for a job without a pending suggestion - measured, 0 body elements across 30 rows in job 34's history popup - which is filed as TASK-155 and closes AC6 when it lands.

`get_body(preferencelist=('plain','html'))` gets the part; converting it is the real work. Prefer the
standard library over a new dependency (`html.parser.HTMLParser` subclass, or `re` plus
`html.unescape`) — a dependency for this needs an argument, since the guardrail-bearing draft path
also consumes `body_text`. Whatever is chosen, the classifier and the guardrails now see text they
never saw before, so re-check that a converted marketing mail cannot suddenly read as a recruiter
reply (TASK-114's bulk-mail guards are the relevant existing protection).
<!-- SECTION:NOTES:END -->
