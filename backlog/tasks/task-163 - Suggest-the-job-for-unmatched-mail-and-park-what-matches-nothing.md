---
id: TASK-163
title: Suggest the job for unmatched mail, and park what matches nothing
status: Done
assignee: []
labels:
  - backend
  - frontend
  - mailbox
  - ux
dependencies:
  - TASK-161
priority: high
ordinal: 163000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-21, after TASK-161 shipped: *"I haven't found a single email that was relevant to a
position that I should also track down, and why have 321 emails to go through — or even 20 — if they
don't belong to the job listings I am tracking?"*

TASK-161 ranked the panel by consequence. That was necessary and insufficient: it sorted the list
without changing the fact that most of the list cannot be acted on at all. Measured against
production, 2026-08-21, using the app's own `owned_job_domains` / `is_ats_host` / `is_job_board`
rules rather than a naive domain comparison:

    reason a row is unmatched                                   rows
    a domain the app could have matched                            0
    a tracked company NAME appears in the subject/body           117
    sent via a shared ATS host (domain deliberately ignored)      66
    sent via a job board (deliberately ignored)                   51
    nothing tracked recognisable at all                           87
                                                                 ---
                                                                 321

    identifiable to a tracked job:  117 (36%)
    identifiable to nothing:        204 (64%)

    of TASK-161's 41 high-consequence rows:  11 relate to a tracked job, 30 do not.

**Nothing here is a matcher bug.** Zero rows carry a domain `owned_job_domains` would have accepted.
The matcher refuses ATS hosts, job boards, and any domain claimed by more than one tracked job, and
that refusal is correct — TASK-137 exists because one `jobs.ashbyhq.com` listing silently became
"the" Ashby company and swallowed every other employer's Ashby-sent mail.

The problem is what the panel then asks of the owner. For the 117 identifiable rows it asks them to
find the right job in a 78-entry dropdown when the company name is sitting in the subject line. For
the 204 unidentifiable ones it offers an action — attach to a tracked job — that has no correct
answer, because the mail is about an application that was never on the board.

The machinery to fix the first half already exists and is simply not applied here:
`_company_name_tokens` and `_match_by_ats_display_name` (TASK-140) already tokenize a company name
and an ATS display name to the same token set, scoped to where the domain is known useless. This
task extends that reasoning to the message's own subject/body for the unmatched list, as a
*suggestion the owner confirms*, never a silent auto-match.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each unmatched row whose text names a tracked company shows that job as a pre-filled suggestion the owner confirms with one action, instead of an empty "Attach to job…" dropdown; the dropdown remains available to override the suggestion
- [x] #2 A suggestion is never applied automatically — `matched_job` is still only ever written by an explicit owner action, preserving TASK-117's "the one deliberate exception to append-only" guarantee
- [x] #3 The suggestion reuses the existing token machinery (`_company_name_tokens` and the TASK-140 subset rule) rather than a second, parallel name-matching implementation; if a genuinely new rule is needed, the task notes state why the existing one could not be reused
- [x] #4 Measured precision against production: state how many of the 117 identifiable rows get a suggestion, and — by inspecting a stated sample by hand — how many of those suggestions name the RIGHT job. A wrong suggestion is worse than none, because it invites a one-click mistake
- [x] #5 Rows that match nothing tracked (measured today at 204) are not shown in the default view, with their count stated and a control to reveal them, in the same spirit as TASK-161 AC4
- [x] #6 The 204 are not merely hidden: the panel offers the one honest action for mail about an untracked application — creating a job lead from the message — or the task notes state explicitly why that was deferred and to which filed task
- [x] #7 The default panel is measurably smaller and more actionable than TASK-161 left it: state rows-before and rows-after, and how many of the shown rows carry a suggestion
- [x] #8 TASK-161's ordering and recency behaviour still hold — high-consequence rows still rank first and are still never hidden by age, verified after this change rather than assumed
- [x] #9 The endpoint's TASK-142/TASK-161 performance properties are preserved, verified by query count and payload size against production, not by reading the code
- [x] #10 Backend suite green; frontend typecheck and tests green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### 2026-08-21 close-out - measured against production across four rounds

The first implementation passed 830 backend tests, 109 frontend tests and a clean typecheck, and was
UNUSABLE. Every defect below was invisible to the suite because each depended on the owner's real
data. This is the record of what measurement caught that green tests did not.

    round 1   suggestions fired on 8 of 321 rows; 2 of 5 inspected were WRONG; 38 of the 41
              high-consequence rows were parked, undoing TASK-161 hours after it shipped.
    round 2   fixes 1-3. 41 of 41 high rows restored, panel 97 -> 49, but precision 5 of 12:
              seven XING job-alert digests each suggested a different random tracked company.
    round 3   fix 4. precision 5 of 5.
    round 4   coordinator's own two changes (below).

**FIX 1 - recall.** Matching read `body_preview`, the 301-char Substr annotation. Company names sit
deeper than 301 chars, so the matcher almost never fired. The agent's instinct to avoid touching the
deferred `body_text` was right and was kept: a SECOND bounded annotation `match_text =
Substr('body_text', 1, 2000)` is used for matching only and is never serialized (asserted by test).

**FIX 2 - single-token company names.** `_company_name_tokens` strips legal forms, so 34 of the 82
tracked jobs reduce to ONE token: `Post AG -> {post}`, `Nejo -> {nejo}`, `Hays -> {hays}`. A single
common token is a subset of almost any text. Both wrong suggestions came from `Post AG` matching
newsletters containing the word "post":

    "The 3 Candidates I Always Rejected as a Bar Raiser at Amazon"  ->  Post AG - Senior AI Engineer

A single-token company must now match the SENDER (address or display name), not free text.
Multi-token companies may still match the body, because two or more tokens co-occurring is already
strong evidence. This mirrors `_match_by_ats_display_name`, which trusts a display name precisely
because it is structured rather than free text.

**FIX 3 - parking scope.** Parking every suggestion-less row hid 38 of the 41 rejections and
interview invitations. Rank-0 rows are now never parked, exactly as they are never hidden by the
recency window -- the same asymmetry, for the same reason.

**FIX 4 - job boards, not ATSes.** The seven remaining wrong suggestions were all XING job-alert
digests ("5 neue Stellenangebote fur 'python in Vienna'"). The matcher was working correctly: the
digest really does contain "STRABAG", because it is advertising a STRABAG vacancy. The INFERENCE was
wrong. A job-board sender now gets no suggestion at all, reusing the existing `is_job_board()` --
deliberately NOT extended to ATS hosts, because ATS mail is single-application correspondence naming
the real employer, which is exactly what this feature should catch. Boards send digests; ATSes send
correspondence. No domain was added to any list: `xing.com` was already in `JOB_BOARD_DOMAINS` and
`is_job_board()` matches by suffix, so `mail.xing.com` already resolved.

#### Final measurements, production

    AC4  precision       5 suggestions, 5 correct by hand inspection (100%):
                           jobs@formunauts.at   "Invite for 1. Interview"        -> Formunauts
                           interview thread     "Vorstellungsgesprach - Elastic" -> EBCONT (BMJ)  x2
                           flo@northscope.at    "Re: Application - Senior Python"-> Northscope
                           PIDSO display name   "We received your application"   -> PIDSO
    AC7  panel size      321 -> 97 (TASK-161) -> 42 by default; 55 parked, 224 age-hidden.
                         5 of the shown rows carry a suggestion.
    AC8  TASK-161 held   41 of 41 high-consequence rows shown, positions 0-40, first low at 41.
    AC9  performance     17 queries, 51,770-byte payload, 0 queries selecting full body_text,
                         1 draft query, 1 joblead query (bulk, not per row). match_text absent
                         from every serialized row.
    AC12 reachability    both reveals -> 321 rows == the whole panel; default is a strict subset.
    AC10 suites          backend 834 passed; frontend tsc clean, 109 passed.

#### Recall is modest, and the 117 figure in this task's own description was wrong

Only 5 of 321 rows receive a suggestion, not the ~117 this task predicted. That 117 came from a
COORDINATOR estimate using a loose ad-hoc tokenizer (any word over 2 characters, minus a hand-written
stoplist) -- precisely the kind of rule that produced the `Post AG` false positives once implemented
properly. The estimate was unsound, not the implementation. Stated here rather than quietly dropped,
because a task that predicts a number and then ships a different one should say so.

The honest summary: **the parking did the heavy lifting, not the suggestions.** 321 -> 42 rows is what
answers the owner's complaint; the 5 suggestions are a bonus on top. Raising recall means loosening
the token rule, which is exactly what cost precision in rounds 1-3, so it is deliberately not
attempted here. If recall becomes the priority, the sound direction is more STRUCTURE (thread ids,
ATS reference numbers, reply-to chains), not fuzzier text matching.

#### Two coordinator changes on top of the agent's work

**1. The frontend now tolerates both response shapes.** TASK-161 changed this endpoint from a bare
list to `{results, ...}`, and that white-screened the owner's local dev box with
`Kt.slice is not a function` -- their backend had been pulled, their bundle had not been rebuilt, and
old code called `.slice()` on an object. Production never sees this because both halves ship in one
image; a local checkout updates them independently. `Array.isArray(u)?u:(u.results||[])` makes the
mismatch degrade instead of white-screen.

**2. A row carrying a suggestion counts toward the visible-row floor.** TASK-161's floor covered the
41 high-consequence rows, which left the 5th suggested row behind a "Show more" click while 41 rows
WITHOUT a suggestion were visible -- exactly backwards for a task whose point is the suggestions.

#### Rig lesson, second occurrence

A `runserver --noreload` process kept serving the previous `index.html` after `npm run build`, so the
browser loaded a bundle hash that no longer existed. This is the SAME trap recorded in TASK-161's
notes and it cost time twice. Compare the hash the server returns against the hash in
`frontend/dist/index.html` before concluding anything about the code; if they differ, restart on a
fresh port rather than trusting a restart to rebind.

Do not "fix" this by widening `owned_job_domains` to accept ATS or board hosts. That is the bug
TASK-137 fixed, and its docstring explains why counting claimants is the general rule. The correct
shape here is a *suggestion surfaced to the owner*, which is allowed to be wrong sometimes, kept
strictly separate from *matching*, which is not.
<!-- SECTION:NOTES:END -->
