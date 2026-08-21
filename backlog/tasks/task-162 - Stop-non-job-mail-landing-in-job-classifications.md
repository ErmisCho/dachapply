---
id: TASK-162
title: Stop non-job mail landing in job classifications
status: Done
assignee: []
labels:
  - backend
  - mailbox
  - classification
dependencies:
  - TASK-161
priority: medium
ordinal: 162000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-21 while measuring TASK-161. The classifier puts mail that is not about a job
application into the classes that carry the strongest consequences.

Two of the six most recent messages classified as `rejection` or `interview_invitation` — the two
classes that, on attach, change a job's status outright — are not job mail at all:

    rejection             "Re: [Ticket#2026080110000112] Ersatzteil fuer PRINZ PZ-STM1"
                          a spare-parts support ticket
    interview_invitation  "You've got 3 unread messages"
                          a LinkedIn/Xing notification digest

This is worse than ordinary misclassification. `record_suggestions` turns `rejection` into
`{'status': 'rejected'}` and `interview_invitation` into an interview status plus a feedback-clock
clear. A false positive here does not merely add a row to a list — it offers the owner a one-click
action that would put a real job into a wrong state on the strength of a spare-parts email.

It also undermines TASK-161: ranking by consequence is only as good as the classification the rank
is computed from. TASK-161 is still worth shipping first (the ordering is right even when a few
inputs are wrong, and it surfaces these false positives instead of burying them), but the two
together are what make the panel trustworthy.

Note the shape of both examples: neither is an ATS or a recruiter. One is transactional support mail
that happens to contain refusal language, the other is a platform digest whose subject reads like an
invitation. A fix that only adds keywords will move the boundary rather than find it — the sender
and the message's relationship to any known application are the stronger signals, and
`_match_by_ats_display_name` and the ATS host-domain work (TASK-137) already exist to build on.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The two named messages — the `Ersatzteil`/Ticket support mail and the "You've got 3 unread messages" digest — no longer classify as `rejection` / `interview_invitation`, verified by re-running the classifier over those exact stored messages
- [x] #2 A measured false-positive rate is reported before and after, over a stated sample of production messages, rather than a claim that it "looks better" — state the sample size and how the ground truth was decided
- [x] #3 No regression on true positives: every message currently classified `rejection` or `interview_invitation` that IS genuinely a rejection or invitation still classifies that way, counted over the same sample
- [x] #4 Platform notification digests (LinkedIn, Xing, Wellfound, Substack and the other non-ATS senders already visible in the unmatched data) are excluded on a basis that is not a subject-line keyword list, and the basis is named
- [x] #5 The fix is defended against the case it exists for: a message that contains refusal or invitation language but has no relationship to any application does not reach a status-changing classification
- [x] #6 Any message whose classification changes is re-classified in place rather than left stale, or the task states explicitly why historical rows are not re-run and what that means for the 321-row panel
- [x] #7 Backend suite green, with a test per false-positive class that fails against the current classifier
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### 2026-08-21 close-out - the first attempt would have destroyed 26 genuine messages

Two rules, both named, neither a subject-line keyword list:

  RULE A  a sender that is a job board or a platform (slack.com, github.com, substack.com,
          wellfound.com) cannot reach rejection/interview_invitation/offer/application_confirmed.
  RULE B  `rejection` additionally requires application context -- domain_known, or one of
          bewerbung/beworben/bewerber/vorstellungsgespraech/application/applied/candidate/
          position/vacancy/role.

Both are enforced at ONE point (`_guard_status_changing`) applied to whichever classification a path
produces -- the heuristic's keyword hit or the LLM's own JSON. A prompt instruction is not an
enforcement point, so the LLM's RESULT is guarded rather than its prompt.

#### Measured against production, before and after (AC2/AC3)

Ground truth: hand-inspection of all 59 stored messages in a status-changing class, judging each on
"is this about the owner's application to a job".

    BEFORE   8 false positives of 59 = 13.6%
             slack.com digest; substack.com x2 newsletters; linkedin.com notification;
             email.stepstone.at marketing; ironhack.com marketing; telusinternational.ai
             "Invitation to Apply"; dual.de spare-parts support ticket
    AFTER    2 false positives of 59 = 3.4%
             6 of the 8 fixed. 0 genuine job mail demoted.

The 9 rows actually rewritten: the 6 fixed false positives, plus two 1,149-day-old
`pannonjob.hu` "RE: Questions" with no application context either way, plus one of the owner's OWN
sent replies that had been classified `rejection`. The owner approved all 9 after seeing the dry-run.
0 pending suggestions were dismissed, so nothing on the board changed.

    status-changing messages   59 -> 50   (rejection 42 -> 38, interview_invitation 17 -> 12)
    unmatched panel rows      321 -> 309

**The two survivors are honest limits, not oversights.** `telusinternational.ai` "Invitation to Apply"
and `ironhack.com` "Thanks for your interest" both contain application-context vocabulary, so no
context rule can exclude them; and neither sender is a board or a platform, so Rule A does not apply.
Predicted before the change and confirmed after. Catching them needs a different signal (the message
proposes that the owner apply, rather than responding to an application they already sent).

#### The first attempt failed, and only a production dry-run caught it

The initial implementation passed 839 backend tests and looked correct. Its dry-run wanted to
reclassify **32** rows, of which ~26 were genuine job mail:

    455/457/499  ebcont.com, bmj.gv.at   "Invitation: Vorstellungsgespraech"  -> not_job_related
    765/766      yuvenda.msg.join.com    "Vorstellungsgespraech"              -> not_job_related
    283          aristo-group.at         "Bewerber Update Call"               -> not_job_related
    769..899     eu.greenhouse.io        "thanks for applying to Bitpanda!"   -> not_job_related
    740..937     smartrecruiters.com     "Vielen Dank fuer Ihre Bewerbung"    -> not_job_related/uncertain

Two causes:

**1. ATS senders were blocked.** greenhouse.io and smartrecruiters.com are members of
`JOB_BOARD_DOMAINS` -- a TASK-114-era categorization answering a DIFFERENT question ("is a job's
listing-page URL on this domain?"), still correct for that use. The coordinator's own instruction to
"add an `is_ats_host()` exemption" was insufficient and the implementer said so: `ATS_DOMAINS` never
contained those two, so that exemption alone would have fixed join.com and left the other 17 broken.
The fix is a separate, guard-only predicate `_is_ats_correspondence()` = `is_ats_host()` OR a small
named set {greenhouse.io, lever.co, personio.de, workday.com, smartrecruiters.com}, layered ON TOP of
the board check rather than replacing it, and deliberately NOT a move of those domains into
`ATS_DOMAINS` -- that predicate also feeds `owned_job_domains()`, `match_job()` and
`detach_ats_host_messages`, none of which this task should perturb.

**2. Rule B was applied to `interview_invitation`.** "Invitation: Vorstellungsgespraech", plain
"Vorstellungsgespraech" and "Bewerber Update Call" contain none of the context terms, so five genuine
invitations were demoted. Enumerating German interview nouns is unwinnable
(Vorstellungsgespraech, Kennenlerngespraech, Bewerbergespraech, Erstgespraech, ...). Rule B is now
scoped to `rejection` only, on the reasoning that the two classes carry different risks: generic
refusal language appears constantly in non-job mail -- which is why the spare-parts ticket matched --
whereas INTERVIEW_KEYWORDS are already specific enough that the extra gate bought nothing and cost
five real invitations.

`stelle` was deliberately excluded from the context terms by the implementer, correctly: it is a
substring of `bestellen`/`Bestellung`/`vorstellen`/`feststellen`, exactly the vocabulary a
parts-and-support ticket uses, so including it would have defeated the guard on the very message this
task names.

#### AC6 - historical rows

Done through `manage.py reclassify_messages`, dry-run by default, `--yes` to write, matching the
existing command idiom. It re-derives `domain_known` from each row's CURRENT `matched_job` (so a
manual attach since ingestion counts), touches only rows already in a status-changing class, and
dismisses only still-PENDING suggestions on a demoted row, never a confirmed one. A migration was
deliberately not used: the first attempt proves why a bulk rewrite needs a human-inspectable dry-run
between the code and the data.

Filed alongside TASK-161 on the owner's instruction ("file both, build the ranking first"), so the
ordering work is not blocked on the classifier work. Do not fold them together.
<!-- SECTION:NOTES:END -->
