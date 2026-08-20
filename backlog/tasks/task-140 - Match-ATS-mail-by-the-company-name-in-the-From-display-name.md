---
id: TASK-140
title: Match ATS mail by the company name in the From display name
status: Done
assignee: []
labels:
  - backend
  - mailbox
  - data
dependencies:
  - TASK-137
priority: high
ordinal: 140000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-137 stopped the app attributing every Ashby and JOIN email to one arbitrary job. It did so by
making those hosts identify nobody, which is correct and also throws away a real match:

    2026-06-03 | PIDSO - Propagation Ideas & Solutions GmbH Recruiting Team <...@msg.join.com>
                 "We received your application for a position at PIDSO ..."

That is job 36's genuine application confirmation, and after TASK-137 it is unmatched, because its
sender domain is JOIN's and JOIN's domain now identifies nobody. The information needed to match it
was never in the domain — **it is in the display name**, which is exactly where an ATS puts the
client company, precisely because the envelope belongs to the ATS.

The same shape explains a bigger number already recorded: TASK-136 recovered **138 application
confirmations**, and most carry `job None` for this reason. Application confirmations are the messages
most likely to arrive through an ATS, because they are sent by the ATS at submission time — so the
matching rule that fails hardest is failing on the class of message the app most wants.

`owned_job_domains`' docstring argues against company-name matching, and that argument is sound
against matching on the message BODY or the subject, which are free text full of other companies'
names. The From display name is different: it is a short, structured field that the ATS populates
with one company, and TASK-137 has just established which hosts are ATS hosts, so the rule can be
scoped to exactly the case where the domain is known to be useless.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The named case matches: the 3 June "We received your application for a position at PIDSO" message attaches to job 36 again, verified against the real mailbox and not only by test
- [x] #2 Display-name matching applies ONLY where the sender domain is a known ATS host (`is_ats_host`, TASK-137). A message from a company's own domain keeps matching by domain, unchanged — this is a fallback for the case TASK-137 deliberately blinded, not a second general matching rule
- [x] #3 A display name that mentions no tracked company still matches nothing: the 138 recovered confirmations include companies never applied to, and inventing a match for them would recreate TASK-137's bug from the other direction
- [x] #4 An ambiguous display name matches nothing rather than guessing: if two tracked jobs' companies both plausibly match one display name, the message stays unmatched and that is reported. State the comparison rule (normalisation, minimum length, substring vs token) explicitly — "Deltia AI (Almetra)" vs "Almetra" is a real pair in this data and shows why bare substring matching is not obviously safe
- [x] #5 Before/after counts recorded here against the real mailbox: how many of the currently-unmatched messages this attaches, and to which jobs. 138 application confirmations and 763 unmatched messages are the numbers this is measured against
- [x] #6 Spot-check the result rather than trusting the count: list ALL newly attached messages — across at least three jobs when that many gained mail — and confirm by reading sender and subject that each really is that company’s mail. TASK-137 exists because a plausible-looking match was wrong for 73 messages. (Reworded via TASK-148; 2026-08-19 measurement: 1 of 1 attached messages read and confirmed — PIDSO → job 36.)
- [x] #7 TASK-137's guarantees are untouched: `join.zooplus.com` still matches job 37 by domain, no ATS host regains domain-matching, and the full backend suite passes with no test contacting a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-19: implemented as _match_by_ats_display_name, reached from match_job only when
is_ats_host(domain) is true (an ATS host cannot reach domain matching — owned_job_domains already
excludes it). Comparison rule (AC4, in the docstring): lowercase, strip ATS role phrases
(hiring/recruiting/talent team, careers, jobs, team) and legal forms (gmbh, ag, se, ltd, inc, llc,
kg, co), collapse punctuation, then require the job's FULL token set to be a subset of the display
name's tokens; zero matches or two distinct matching companies attach nothing. 'Deltia AI (Almetra)'
vs 'Almetra' is encoded as a test. 13 tests; suite 766 passed, hermetic.
AC1/AC3/AC5 verified 2026-08-19 with the owner's approval, dry run against the real mailbox:
`rematch_ats_display_name_messages` attaches exactly 1 message — uid 697, "PIDSO - Propagation
Ideas & Solutions GmbH Recruiting Team <no-reply@msg.join.com>", "We received your application for
a position at PIDSO ..." -> job 36, the named AC1 case. Before/after (AC5): 836 currently-unmatched
messages (763 at task-writing time; mail arrived since), of which this rule attaches 1, to job 36
only; nothing is invented for the never-applied companies in the back-catalogue (AC3's real-data
half). Sender and subject of the one attached message were read and confirmed as PIDSO's own mail.
AC6 stays unchecked: its wording demands newly-attached mail across "at least three jobs", and the
correct rule yields exactly one job — unsatisfiable as written; reworded via TASK-148 per TW-005
rather than silently relaxed. `--yes` not run; the owner can apply the single attachment any time.

`parseSenderHeader` already exists on the frontend (TASK-134) for splitting a From header into name
and address; the backend has `_sender_domain`. The display name is the other half of that same header
and needs no new fetching — it is already stored in `MailboxMessage.sender`.

AC4 is where this task will be won or lost. Company names in this repo's data include
`Deltia AI (Almetra)`, `PIDSO - Propagation Ideas & Solutions GmbH` and
`ONTEC AG`; ATS display names include `PIDSO - Propagation Ideas & Solutions GmbH Recruiting Team`
and `Taktile Hiring Team`. A token-based comparison after stripping legal-form and role suffixes
(GmbH, AG, SE, "Hiring Team", "Recruiting Team") is the obvious shape, but the rule must be written
down and tested, not tuned until the numbers look nice.

Do not extend this to the subject line or the body. The subject "Your application at ONTEC AG" would
match, but so would a newsletter mentioning a company, and TASK-114's guards exist because that class
of mail is already a problem.
<!-- SECTION:NOTES:END -->
