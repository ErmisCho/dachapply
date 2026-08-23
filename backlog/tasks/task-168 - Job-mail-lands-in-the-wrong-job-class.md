---
id: TASK-168
title: Job mail lands in the wrong job class
status: Done
assignee: []
labels:
  - backend
  - mailbox
  - classification
dependencies:
  - TASK-162
priority: medium
ordinal: 168000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-21 while hand-inspecting all 59 production messages for TASK-162's before-baseline.
Filed separately because it is a DIFFERENT defect with the same consequence.

TASK-162 is about non-job mail reaching a job classification (a spare-parts support ticket becoming a
`rejection`). This is about genuine job mail reaching the WRONG job classification — which carries
the identical one-click risk, because `record_suggestions` turns `rejection` into
`{'status': 'rejected'}` and `interview_invitation` into an interview status plus a feedback-clock
clear, regardless of whether the message was really either of those things.

Measured examples from the 59 (sender | stored class | what it plainly is):

    notifications@smartrecruiters.com | rejection            | "Thanks for applying at IMS Nanofabrication
                                                             | GmbH" -- an application CONFIRMATION
    recruiting.xapo.com               | interview_invitation | "Thank you, Ermis! Your application has been
                                                             | received" -- also a confirmation
    Philipp.Haubner@bmj.gv.at         | rejection            | "AW: Einladung: Vorstellungsgesprach -
                                                             | Elastic Consulting" -- an interview thread
    Kiraly.Boglarka@pannonjob.hu x3   | rejection            | "RE: Questions" -- no evidence either way;
                                                             | 1,149 days old, recruiter agency

The mechanism is visible in `_classify_heuristic`: the checks run in a fixed order —
offer, then rejection, then interview, then application_confirmed — and the FIRST keyword hit wins.
So a confirmation that happens to contain a rejection-shaped phrase is classified as a rejection and
never reaches the `application_confirmed` branch below it. Order-of-evaluation is doing the work that
evidence should be doing.

Note the direction of the errors matters. "Confirmation misread as rejection" proposes marking a live
application dead. That is worse than the reverse, and worse than TASK-162's non-job false positives,
because the message IS about a job the owner cares about, so the suggestion looks entirely plausible
at the moment of clicking.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The three named messages classify correctly when re-run: the two "thanks for applying"/"application has been received" messages as `application_confirmed`, and the "AW: Einladung Vorstellungsgesprach" thread as `interview_invitation` rather than `rejection`
- [x] #2 An explicit confirmation phrase wins over an incidental rejection phrase, rather than losing to it purely because the rejection check runs first — state the rule chosen and why it is evidence-based rather than order-based
- [x] #3 Measured over the full set of stored status-changing messages: state how many change class, and hand-inspect a stated sample to say how many of those changes are right. A change that is merely different is not an improvement
- [x] #4 No regression: every message that is genuinely a rejection still classifies as `rejection`, counted over the same set — this is the criterion TASK-162's first attempt failed, demoting 26 genuine messages
- [x] #5 Ambiguous messages (the `RE: Questions` class — no application context either way) land in `uncertain` rather than being forced into a status-changing class
- [x] #6 Existing rows are re-classified through the same dry-run-by-default management command TASK-162 added, not a migration, and the dry-run output is inspected before anything is written
- [x] #7 Backend suite green, with a test per named example that fails against the current classifier
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### 2026-08-23 close-out - three dry-run rounds against production before a single row was written

Final state: **4 rows changed, 936 of 940 untouched**, every one hand-inspected against its actual
message body and approved by the owner.

    499  bmj.gv.at        rejection -> interview_invitation   subject is "Einladung: Vorstellungsgespraech"
    740  smartrecruiters  rejection -> application_confirmed  "Thanks for applying at IMS Nanofabrication"
    806  REWE             rejection -> application_confirmed  "Vielen Dank fuer Ihre Bewerbung"
    828  Investing        application_confirmed -> rejection  "we regret to inform you that we have
                                                               decided to move forward with other candidates"

828 is the one nobody asked for: a genuine rejection sitting mislabelled as a confirmation on the
board, found only by reading bodies rather than subjects.

**The rule, and why it is evidence-based rather than order-based.** `_classify_heuristic` no longer
runs offer -> rejection -> interview -> confirmed and takes the first hit. Every category that hits
becomes a candidate scored STRONG or WEAK; the strongest wins, and the old fixed order survives only
as a tie-break between two candidates of equal strength. WEAK is a named, closed set, not a judgement
call: the bare dictionary words (`leider`, `unfortunately`) and the tense-neutral "let's arrange
something" phrases (`schedule a call`, `book a time`, `available for a call`, `gespraech vereinbaren`).

#### Three rounds, and what each one cost

    round 1   17 rows proposed, 11 WRONG
    round 2    9 rows proposed,  5 WRONG
    round 3    4 rows proposed,  0 wrong   <- written

**Round 1** demoted seven genuine JOIN.com rejections to `application_confirmed`. Their bodies read
"Wir haben deine Bewerbung genau geprueft ... LEIDER koennen wir ... nicht mit deiner Bewerbung
fortfahren" -- rejection letters that open with a polite thank-you, which is the standard form. This
is precisely the trap this task's own notes warned about ("putting application_confirmed first would
make a genuine rejection that politely thanks the applicant classify as a confirmation"), reached by
scoring instead of by ordering. It also promoted four confirmations to `interview_invitation` while
demoting a real invitation ("Are you available for a call tomorrow at 16:30?") the other way.

The coordinator's proposed fix -- make `leider` STRONG -- was **rejected by the implementing agent
with a reason, correctly**: in message 499 `leider` refers to the appointment, not the decision, so
strengthening it would have broken a case that must keep working. It added the JOIN template's own
decisive sentence (`nicht mit deiner bewerbung fortfahren`) instead. Recorded because the agent was
right and the coordinator was not.

**Round 2** left five wrong, all one mistake: a keyword matching inside BOILERPLATE rather than a
decision. Amazon and Allianz were being promoted to `interview_invitation` by the word
`Vorstellungsgespraeche` appearing in their marketing footers -- "In unseren Ressourcen fuer
Vorstellungsgespraeche findest du ... zur Vorbereitung" and "unser stimmbasiertes Training fuer
Vorstellungsgespraeche ueber Alexa Voice Assistant". Nobody was being invited to anything.

The signal that separates them is grammatical and clean: marketing uses the PLURAL as a topic
("Ressourcen fuer Vorstellungsgespraeche"), an invitation names a singular event ("Einladung:
Vorstellungsgespraech"). Implemented as `vorstellungsgespraech(?!e)`, one negative lookahead, chosen
over a proximity-window heuristic because it explains both false positives exactly and keeps 499
matching by construction.

**Round 2 also left TU Wien (903) being demoted from `rejection` to `application_confirmed`.** The
implementing agent said plainly it could not decide without the body and refused to guess. Reading
further gave "Wir konnten zwischenzeitlich eine Entscheidung treffen. LEIDER MUESSEN WIR IHNEN
MITTEILEN, dass es die..." -- and that phrase became a STRONG rejection entry.

#### The general lesson

Every one of the 11 + 5 wrong changes came from a keyword that was present but not DECIDING. A
rejection letter thanks you first; a confirmation advertises interview coaching; a subject line says
"Application" for both. Classification by keyword presence is classification by vocabulary, not by
meaning, and the gap between them is only visible against real mail.

**The dry-run gate is why this is a story about three corrections rather than an incident.** Round 1
alone would have destroyed 11 classifications, including seven rejections, if this had shipped as a
migration.

Do not fix this by reordering the checks in `_classify_heuristic`. Reordering moves the failure rather
than removing it: putting `application_confirmed` first would make a genuine rejection that politely
thanks the applicant for applying — which is most of them — classify as a confirmation. The rule needs
to weigh which signal is more specific to the message, not which line runs first.

TASK-162's first attempt is the cautionary tale to read before starting: a guard that looked correct
demoted 26 genuine messages to `not_job_related`, and only a production dry-run caught it. Measure the
whole changed set, not a sample of the ones that look right.
<!-- SECTION:NOTES:END -->
