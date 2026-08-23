---
id: TASK-170
title: Suggestions pick arbitrarily between two jobs at the same company
status: To Do
assignee: []
labels:
  - backend
  - mailbox
  - bug
dependencies:
  - TASK-163
priority: high
ordinal: 170000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-21, on the Formunauts suggestion: *"this should belong to one of the Formunauts
processes according to when I had the interview with them and when I sent the email to them to
apply."*

They are right, and it is a bug rather than a missing nicety. `suggest_job_for_message` keys its
candidate map by the company's TOKEN SET:

    matches: dict[frozenset, JobLead] = {}
        matches.setdefault(company_tokens, job)
    return next(iter(matches.values())) if len(matches) == 1 else None

Two tracked jobs at the same company produce the SAME key, so `setdefault` silently keeps whichever
the queryset yielded first and `len(matches) == 1` reports no ambiguity at all. The "more than one
claimant -> None" guard that protects against two DIFFERENT companies does not fire here, because
from the map's point of view there is only one claimant.

Measured against production 2026-08-21:

    Formunauts, 2 tracked jobs
      id=292  status=archived   "Senior Front End Developer"        created 2026-06-20
      id=535  status=interview  "Senior Back End Developer Python"  created 2026-07-09

    the suggestion offered id=535 -- correct here, but by iteration order, not by evidence

    companies with more than one tracked job: 11
      Dynatrace 3, SQUER 3, APC Business Services 3, tts GmbH 3,
      STRABAG BRVZ 2, Formunauts 2, DataScience Service 2, Austro Control 2

This is TASK-137's bug recurring in a new place. Its docstring already records the lesson: *"a host
more than one tracked job's URL resolves to identifies no single company -- the previous version kept
whichever job happened to be first in iteration order."* Same failure, different key.

**The owner's proposed discriminator is the right one: timing.** A message belongs to the process it
is temporally part of — the application the owner sent, and the interview that followed. The data to
do this exists: `MailboxMessage.received_at`, the owner's own sent mail (`sent_by_owner`, stored
since TASK-132), `JobLead.applied_at`, and the job's status history.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Two tracked jobs at the same company are recognised as two candidates, not silently collapsed into one — proven by a test that fails against the current token-set-keyed map
- [ ] #2 When several jobs at one company are candidates, the suggestion is chosen by timing: the message is attributed to the process whose application/interview window it falls in, using the message's `received_at` against the job's own dates. State the rule chosen
- [ ] #3 The owner's OWN sent mail to that company is used as evidence of when each application happened, since `sent_by_owner` messages have been stored since TASK-132 and are what actually date an application
- [ ] #4 When timing cannot separate the candidates, the suggestion is `None` rather than a guess — the "more than one claimant" principle still applies, it just now has to survive same-company candidates
- [ ] #5 Measured against production: for each of the 11 companies with more than one tracked job, state how many of their messages get a suggestion, and hand-inspect a stated sample to say how many name the right process. This is the criterion that matters — a plausible-looking wrong process is worse than no suggestion
- [ ] #6 No regression on single-job companies: the suggestions verified correct in TASK-163 (Formunauts, EBCONT x2, Northscope, PIDSO) still resolve to the same jobs
- [ ] #7 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Do not fix this by keying the map on job id instead of token set and then returning the first of N.
That converts a silent wrong answer into a silent wrong answer with more steps. The ambiguity must
either be RESOLVED by timing evidence or reported as no-suggestion.

Watch the archived case: Formunauts id=292 is `archived` and id=535 is `interview`. Job status is
tempting as a tiebreak and is NOT sufficient on its own — an archived process still receives mail
(rejections arrive after the owner has moved on), and attributing a late rejection to the live
process because the other one is archived would be exactly wrong.

### Coordinator measurement against production, 2026-08-23 (and the rule change it forced)

The first implementation dated a process from `applied_at` and the owner's own sent mail only. Measured
against production (82 tracked jobs, 854 unmatched messages) it did not work:

    companies where timing can separate two candidates    1 of 11
    Formunauts (the case this task was filed about)       0 suggestions on all 7 of its messages

Every suggestion it produced on a multi-job company won by being the ONLY dated candidate, so the
discriminator described in AC2 never actually ran. Field coverage explains why:

    applied_at        23/82 (28%)      status_date       37/82 (45%)
    last_update_date  49/82 (60%)      interview_at       0/82 (0%)
    owner sent mail   11/82

The sent-mail evidence was also contaminated: six jobs carried a first-sent date BEFORE the job
existed, by 238-685 days (old correspondence matched onto the thread), so `_process_started_at`
was reading an application date that was up to two years wrong.

**Three changes follow, and AC2's "state the rule chosen" now means this rule:**

1. Widen the evidence to `status_date` and `last_update_date` as well as `applied_at`. Measured
   effect: separable companies 1/11 -> 6/11, and both motivating cases then resolve BY EVIDENCE
   (Formunauts -> 535, DataScience Service -> 462) rather than by iteration order.
2. Bound sent-mail evidence to `received_at >= job.created_at`, removing the contamination above.
3. **Owner decision, 2026-08-23:** a 90-day cap. If the winning process started more than 90 days
   before the message arrived, the answer is `None`. Owner's reasoning: *"the user can be applying at
   multiple positions for a company, so if the time is too much apart, the email is probably
   referring to another job position/interview round."* 90 was chosen against the five attributions
   measured correct (1, 5, 8, 12 and 28 days) while staying clear of the late-rejection case this
   task's notes already warn about.

`interview_at` is populated on ZERO of 82 jobs despite TASK-078 being marked Done. Filed separately as
TASK-179; it is not a dependency of this task.
<!-- SECTION:NOTES:END -->
