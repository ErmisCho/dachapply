---
id: TASK-236
title: Stop storing one-off readjustment briefs as durable CV preferences
status: In Progress
assignee: []
created_date: '2026-09-12 09:44'
updated_date: '2026-09-12 19:20'
labels:
  - backend
  - llm
  - data
dependencies:
  - TASK-225
  - TASK-229
priority: high
ordinal: 235000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-09-12. TASK-229's notes named this and recorded that it was "larger than TASK-229 and is not filed yet".

`cv_tasks._learn_application_preference` appends EVERY readjustment instruction to `UserProfile.learned_application_preferences`, verbatim, forever. The only filter is an exact, case-insensitive duplicate match. `load_candidate_evidence` then injects that field into every future CV prompt under the header "LEARNED ACCOUNT APPLICATION PREFERENCES (newer entries override older ones)".

Measured against the real field 2026-09-12 - counts only, the repository is PUBLIC and these are the owner's career records:

    entries                 47              (43 on 2026-09-11)
    field              103,387 chars        (93,330 on 2026-09-11)
    entry length        67 / 613 / 1,699 / 3,832 / 4,979   (min p25 median p75 max)
    sha256             4781cd3a...

- The 33 entries over 800 chars carry **96.4%** of the field. The 14 at or under 800 - the ones actually shaped like a preference - carry 3.6%.
- **10 entries (21%) cluster inside 91 chars of the maximum**, at 4,888-4,979. `views.py:2043` caps the instruction with `instructions[:5000]`. Those ten are pasted briefs cut off mid-sentence at the wire cap, and they carry **49,533 chars - 47.9% of the field**.
- Repetition is NOT the cause: only 3 of 47 entries are >=90% similar to an earlier one, 2 repeat exactly after normalisation. Size is the cause.
- The field grew **+4 entries and +10,057 chars in the single day** between the TASK-229 measurement and this one.

## What the prompt actually spends its budget on - measured, and it corrected this task

The first version of this description asserted that the ten truncated briefs were eating the TASK-225 budget. **That was wrong, and measuring it is what showed so.** Under the 16,000-char budget the newest 9 of 47 entries reach the prompt, and **none of them is one of the truncated ten** - those are old. The real composition of the 14,549 chars that are sent:

    5 briefs (1,257-3,566 chars)          12,607 chars   86.7% of what is sent
    4 preference-shaped (<=1,000 chars)    1,942 chars   13.3%

So the mechanism is not truncation, it is ordinary mid-size briefs crowding out preferences: **of the 17 preference-shaped entries in the field, only 4 reach the model.** The other 13 are starved out by brief text. Excluding briefs would let all 17 fit inside the existing budget with room to spare (6,483 chars against 16,000).

The truncated ten still matter - they are 47.9% of stored bulk and will surface in the prompt as the newer entries age out - but they are not today's prompt problem, and AC3 exists for correctness of the rule rather than for current impact.

## Why this is the right layer

- TASK-225 bounded the field at READ time because it was 58.9% of the prompt. The bound cannot tell a preference from a brief, so it spends its budget in whatever order the entries arrived.
- TASK-229 found factual claims about past roles living only in this field. A brief pasted for ONE application asserts things about one role; stored durably, it asserts them about every future CV.

Both treat the symptom. This is the write.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 An instruction too long to be a durable preference no longer reaches the CV prompt as one, with the threshold derived from the measured distribution of the real field and stated, not picked round
- [x] #2 Nothing already stored is deleted or rewritten, and no migration touches the field - what changes is what the PROMPT sees, so the change is reversible by configuration alone
- [x] #3 The 10 truncated entries are excluded by a rule that does not depend on a threshold at all - they hit the 5,000-char wire cap at views.py:2043 and are cut mid-sentence
- [x] #4 The share of the prompt's preference block that is pasted-brief rather than preference text is stated BEFORE and AFTER, measured with report_cv_prompt_size against the real field rather than estimated
- [x] #5 Every excluded entry is still visible and recoverable - review_learned_preferences keeps showing them, marked as excluded and with the reason
- [x] #6 The threshold is configurable and the pre-change behaviour stays reachable byte-for-byte, the way CODEX_LEARNED_PREFERENCES_BUDGET<=0 already restores pre-TASK-225 behaviour
- [x] #7 Backend suite green at or above 1162, and a generation sends exactly what it sent before apart from the excluded entries
- [x] #8 The CV popups stop telling the user 'Adjustment learned for future applications.' for an instruction that will not reach the prompt - both the single and the batch popup, since both render that line today
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Branch `task-236-preference-intake`. Sealed rubric at `.claude/.asian-dad/task-236-rubric.json`
(gitignored), written 11:48 -- before the implementation at 12:05-12:09, per TW-001.

No entry text, term or employer appears below or anywhere in this diff: counts, lengths and hashes
only. The field holds the owner's real career records and this repository is public.

## The shape of the fix

Read-time only, in `cv_generator`. `preference_exclusion(line)` returns '' or a short reason;
`preference_entries(raw)` drops the rejected lines and runs BEFORE `bound_learned_preferences`, so an
excluded brief FREES budget instead of spending it. Two settings, both with an off switch:
`CODEX_PREFERENCE_MAX_CHARS` (1,000) and `CODEX_PREFERENCE_SKIP_TRUNCATED` (on). Nothing stored is
edited, and no migration exists.

## AC4 -- measured with report_cv_prompt_size against the real field, both sides

    BEFORE (CODEX_PREFERENCE_MAX_CHARS=0, CODEX_PREFERENCE_SKIP_TRUNCATED=0 -- the escape hatch)
      IN FORCE: the character budget     9 of 47 entries    14,549 chars    18.8% of the prompt
        brief-shaped  (>1,000 chars)     5 entries          12,599 chars    86.6% of the block
        preference    (<=1,000 chars)    4 entries           1,942 chars    13.4%

    AFTER (defaults)
      IN FORCE: the character budget    17 of 47 entries     6,499 chars     9.4% of the prompt
        brief-shaped  (>1,000 chars)     0 entries               0 chars     0.0% of the block
        preference    (<=1,000 chars)   17 entries           6,483 chars   100.0%

All 17 preference-shaped entries now reach the model, against 4 before; the block costs 6,499 chars
instead of 14,549 while carrying more of what it is for. (6,483 is the sum of entry lengths, 6,499
the bounded string including the newlines that join them.)

## AC2 -- the stored field is untouched

`sha256 4781cd3a...`, 103,387 chars, 47 entries -- identical before and after every report and review
run above, and the same hash this task recorded when it was filed. No migration, no backfill; the
only write to the field is still the pre-existing append in `_learn_application_preference`.

## AC3 -- the truncation rule does not depend on a threshold, verified by removing the threshold

Real field, length rule disabled and then set absurdly high:

    CODEX_PREFERENCE_MAX_CHARS=0        excluded 10 entries, 49,533 chars
    CODEX_PREFERENCE_MAX_CHARS=999999   excluded 10 entries, 49,533 chars  (the same 10)

Those are the ten this task was filed about. Raising the threshold never readmits them.

### A defect found in review and fixed -- the rule had a blind spot exactly where it mattered

The first implementation measured the distance to the cap on the whole STORED LINE. But
`views.py:2043` caps the INSTRUCTION, and `cv_tasks` adds the `- [scope] ` prefix afterwards, so a
brief pasted as one single-spaced paragraph -- nothing for `' '.join(x.split())` to collapse --
stores PAST the cap, not under it. Measured slack: **-7 / -11 / -16** for scopes `CV`, `Letter` and
`CV + letter`. The `0 <=` test then stopped seeing precisely the entries the rule exists to catch,
and the length rule hid it by excluding them for a different reason -- which is the threshold
dependence AC3 forbids.

Fixed by measuring the entry BODY, which is what was capped. No new constant was needed.
`test_a_brief_with_no_whitespace_to_collapse_is_still_seen_as_truncated` pins all three scopes.

### Known ceiling, stated rather than tuned away

`TRUNCATION_ALLOWANCE` is a window over how much the text collapsed, and that scales with whitespace
density, not length. Measured: a brief pasted with blank lines and indentation collapses by 348 and
falls OUT of the 250 window, so the length rule catches it instead of the truncation rule. The window
was NOT re-tuned to cover it -- that would be fitting a constant to invented data. The honest upgrade
is recording truncation at WRITE time, where `len(instructions) > 5000` is known for certain.

## A second defect found in review and fixed -- the measuring instrument itself

`report_cv_prompt_size --learned` built its row labelled **IN FORCE: the character budget** from the
RAW field, so after this change it printed the pre-change answer: `9 / 14,549` in that section
against `17 / 6,499` in the main table of the same run. AC4 is measured with this artifact, so the
artifact had to be right first. The test that should have caught it used 60 short entries, where both
paths return the same string and it cannot fail; the replacement carries a brief and ends with an
assertion that the fixture really does separate the two paths.

## AC5 / AC6 / AC7 / AC8

- **AC5** `review_learned_preferences` prints `ENTRIES 1-47 of 47`: nothing vanishes. 17 reaching /
  30 excluded (6,483 / 96,858 chars), each excluded entry marked and carrying its reason --
  **20 `a pasted brief`, 10 `cut off at the 5,000-char input cap`**. `--prompt reaching|excluded`
  pages through either half.
- **AC6** the escape hatch reproduces the pre-change prompt BYTE FOR BYTE, not equivalently: the
  built string hashes identically to the literal pre-change call site, and `preference_entries`
  returns the *same object* when nothing is excluded.
- **AC7** backend suite **1181 passed** (floor 1162; 1178 before the 3 tests added here).
- **AC8** both popups go through one `LearnedPreferenceNote` with two call sites, so neither can
  drift from the other -- the repo memory about a claim fixed on one surface being read as covering
  another. An excluded entry now reads *"Adjustment applied to this job only, not reused for future
  applications."* 6 tests cover both popups in both directions; frontend typecheck clean, 256 tests.

## What this does NOT do

The write path is unchanged: `_learn_application_preference` still appends every readjustment, so the
field keeps growing at the ~10k chars/day this task measured. This filters what the PROMPT sees,
which is what AC2 requires and what makes the change reversible by configuration alone. Trimming the
stored field is the owner's call and is not attempted here.
<!-- SECTION:NOTES:END -->
