---
id: TASK-229
title: >-
  Learned preferences are carrying factual claims that belong in candidate
  evidence
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-10 12:06'
updated_date: '2026-09-23 19:13'
labels:
  - backend
  - llm
  - data
dependencies:
  - TASK-225
priority: high
ordinal: 228000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-09-10 by TASK-225 AC4, which compared one job generated with the full preference blob against the same job generated under the new 16,000-char bound.

The two CVs were 98.1% identical. Three lines differed. Two of them - the headline and the professional summary - also differ between two runs of the IDENTICAL unbounded prompt (a control run measured 97.6% similarity, 13 diff lines, varying in the same summary region), so those are the model, not the bound.

The third is not explained that way. One experience bullet described what a past employer role involved one way in the unbounded run and a materially different way in the bounded one. The control run did not touch that bullet at all, so this difference is attributable to the bound in a way the other two are not.

Where those two descriptions come from is the finding, and it is a data-placement problem, not a bounding problem. Measured over the real field, by term search and counts only:

- The terms behind the bounded wording appear ONLY in entries the bound dropped (2 terms, 4 occurrences between them).
- The terms behind the unbounded wording appear in entries the bound kept.
- `UserProfile.candidate_evidence` - the AUTHORITATIVE CANDIDATE EVIDENCE block of the prompt, which the whole pipeline treats as ground truth - contains NONE of these terms. Zero occurrences of every one of them.

So claims about what the owner actually did in a past role are living in an append-only readjustment log rather than in the evidence that is supposed to be authoritative. Two consequences, neither of them created by TASK-225:

1. Any bound on that field - and the field HAD to be bounded, it was 59% of the CV prompt - can change what the CV asserts about a past role.
2. Even unbounded, two entries can contradict each other, and the prompt only tells the model that newer entries override older ones. That is a tie-break rule, not a truth rule. Nothing reconciles either entry against the evidence.

No term, phrase or employer is named in this task on purpose: the repository is PUBLIC and these are the owner real career records. Everything above is a count or a category, and the underlying strings stay in the database where they belong.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 It is established which factual claims currently live only in learned_application_preferences and not in candidate_evidence - by measurement over the real field, reported as counts and categories rather than as quoted personal content
- [ ] #2 The claims that are true are moved into candidate_evidence, where the pipeline already treats them as authoritative, with the owner confirming each one rather than a model deciding
- [x] #3 A readjustment instruction that asserts a FACT is distinguishable from one that asserts a STYLE preference, or the task records why that distinction cannot be drawn automatically and what the owner does instead
- [ ] #4 After the move, the same job generated at the TASK-225 bound and generated unbounded no longer disagree about any factual claim - verified by re-running the AC4 comparison, not by argument
- [x] #5 Contradictory entries are surfaced to the owner rather than silently resolved by recency
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Generate the existing read-only owner review against the current production field and active local evidence source, keeping personal content outside the public repository.
2. Have the owner confirm which prompt-reaching factual claims are true and add only those claims to the authoritative candidate evidence file.
3. Re-run the same job with bounded and unbounded learned preferences, plus an identical-prompt control, and compare every factual line.
4. Run required gates and the sealed Asian Dad evaluation.
5. Commit/push/squash-merge the evidence-only task record, then mark Done in a post-merge administrative change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## AC1 measured, 2026-09-11 -- counts and categories only

Run against the real field. **Note which evidence source this compares against**, because the first
attempt got it wrong and the correction is the interesting part:

`UserProfile.candidate_evidence` is **empty (0 chars)** for this account. `load_candidate_evidence`
therefore falls through to the configured FILE (`CODEX_CANDIDATE_EVIDENCE_PATH`), which supplies
33,737 chars after compaction. The code already documents this -- "it is empty in production and
exists on nobody else machine" -- so it is not a new finding, but it is a trap for this measurement:
comparing against the empty profile field reports 100% uncorroborated, which is an artifact, not a
result. The numbers below compare against the source the pipeline actually reads.

    distinctive terms (capitalised words / acronyms) in the preference field : 713
      corroborated somewhere in the evidence : 332   (47%)
      absent from the evidence entirely      : 381   (53%)
        still sent under the 16,000-char bound : 59
        only in entries the bound drops        : 322

**This is a heuristic, not claim extraction, and 381 is an upper bound rather than a count.** A
capitalised term absent from the evidence may be a company name from a posting, a technology named as
a target, or ordinary prose -- not necessarily an unsupported claim about the owner. What the number
does establish is the shape of the problem: roughly half of the distinctive vocabulary the CV prompt
carries in its preference block has nothing behind it in the authoritative evidence, and the large
majority of that half sits in entries the bound now drops.

No term, entry or employer is named: the repository is public and these are the owner career records.

## What AC2-AC5 still need

They are owner judgement, not measurement. AC2 requires the owner confirming each claim before it
moves into `candidate_evidence`, and AC3 asks whether a fact-asserting entry can be told apart from a
style-asserting one automatically -- on this evidence it probably cannot, since both are free text
written into the same field by the same control. The honest next step is a review list the owner ticks,
not a classifier.

## AC3 and AC5 closed 2026-09-11 with `manage.py review_learned_preferences`

One read-only command, dry by construction -- no `save()`, no migration, no provider. The stored field
is byte-identical after a run, checked by sha256 against the real field (`75727ac6...`, 93,330 chars,
before and after) as well as by test.

### AC3 -- and it is the SECOND branch of that criterion, honestly

The criterion allows either "fact and style are distinguishable" or "the task records why that cannot
be drawn automatically and what the owner does instead". **It is the second.** Measured over the real
43 entries:

| label | entries | rule |
|---|---|---|
| likely-STYLE | **5** | writing verbs only; no uncorroborated term, no date, no measured quantity |
| likely-FACT | **1** | at least one of those, and no writing verb at all |
| unclear | **37** | both kinds of signal (35) or neither (2) |

**35 of 43 entries carry BOTH kinds of signal**, and that is the finding rather than a defect in the
rule. At a median of 1,521 chars an entry is not a preference at all -- it is a whole pasted
application brief that says "replace this headline", "preserve these bullets" and "do not add AWS" in
one breath. A style instruction and a factual claim live in the same entry, so no entry-level
classifier can be right, and one that looked confident would be worse than none because the owner
would act on it.

So the command prints the **signals**, never a bare verdict: which writing verbs an entry contains,
which of its distinctive terms appear nowhere in the evidence, which dates and measured quantities it
carries. Its own header states that the label has no measured accuracy and has never been checked
against a labelled sample, because no labelled sample exists. What the owner does instead is split
those 35 by hand -- which is AC2, and is why AC2 is still open.

### AC5 -- contradictions, with duplicates excluded

Of 43 entries compared pairwise: **6 pairs dropped as duplicates** (>=90% difflib similarity, the same
rule `report_cv_prompt_size --learned` already uses), and a pair naming the same size for the same
thing is read as agreement however opposite its verbs look. **16 candidate pairs remain**, each
printed with the reason it was flagged, for example:

- `#12 vs #20 -- opposed on inclusion: #12 says delete, #20 says keep`
- `#5 vs #6   -- the same thing is given two different sizes`

Each is labelled a CANDIDATE with "read both and decide, the rule cannot" -- surfaced to the owner,
which is what the criterion asks, rather than resolved by recency.

### Flags

    manage.py review_learned_preferences [--user U] [--limit N] [--start N]
                                         [--label all|fact|style|unclear] [--chars N]

`--start` and `--limit` exist so 43 long entries can be worked through in sittings. Note `--chars 0`
means *unlimited*, not *none*.

### Worth the owner attention, beyond this task

Entries 1-3 are all successive briefs for the **same single application**. They are one-off
instructions -- edit this file, preserve that section, split that document -- not durable preferences
about how CVs should be written. That is a question about whether
`_learn_application_preference` should be storing them at all, which is larger than TASK-229 and is
not filed yet.

### Still open

**AC2 and AC4 remain unchecked and are the owners**: which of the claims are true, and therefore what
moves into candidate evidence, is a judgement no rule here can make. AC4 (re-run the before/after
comparison once the move is done) cannot start until AC2 has.

## AC5 measured again 2026-09-21: none of the contradictions can reach a CV

The owner asked for the contradictory pairs to be reviewed. Before handing over a list, the pairs
were filtered against the entries that actually reach the CV prompt -- which TASK-236 changed after
this task was written, and which nothing here had re-measured since.

    manage.py review_learned_preferences --chars 0            -> 47 entries, 103,387 chars stored
                                                                 19 candidate pairs (6 dropped as
                                                                 >=90% duplicates)
    manage.py review_learned_preferences --prompt reaching    -> 17 entries reach the prompt:
                                                                 #1 #4 #13 #14 #15 #16 #17 #20 #22
                                                                 #25 #27 #28 #32 #34 #39 #40 #42 #43

Cross-checking every one of the 19 pairs against that set: **not one pair has both of its entries
reaching the prompt.** Each flagged pair involves at least one entry TASK-236 filters out as a
one-off readjustment brief rather than a durable preference. Seven of the nineteen involve entry #12
alone, which is a single 'PATCH THE CURRENT FREQUENTIS CV ONLY' brief.

So the contradictions are real and they are inert: they cannot change a generated CV while that
filter stands. Reviewing them by hand now would be insurance against the filter changing, not a fix
for anything live -- and the owner chose, on that evidence, to record it and move on.

**What this does NOT close.** AC5 asked for contradictions to be surfaced rather than silently
resolved by recency, and the command does that; this note adds which of them matter. AC2 and AC4 are
untouched and remain the substantive work: which factual claims are true, and therefore what moves
into candidate_evidence. That is still owner judgement, and it is still open.

**A caveat worth keeping.** The filter is the thing making these inert. If TASK-236's notion of a
durable preference is ever widened, the 19 pairs become live in the same moment, and nothing would
announce that. Re-run the two commands above rather than trusting this note.

2026-09-23 refresh: the production field now has 19 prompt-reaching entries (#4, #13-17, #20, #22, #25, #27-28, #32, #34, #39-40, #42-43, #53, #56): 1 likely-FACT, 13 unclear, 5 likely-STYLE. The full private review was written outside the repository to `%LOCALAPPDATA%\dachapply\TASK-229-owner-review.txt`; no personal content was copied into Backlog or command output.
<!-- SECTION:NOTES:END -->
