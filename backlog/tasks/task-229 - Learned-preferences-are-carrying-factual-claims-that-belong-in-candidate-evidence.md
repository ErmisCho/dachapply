---
id: TASK-229
title: >-
  Learned preferences are carrying factual claims that belong in candidate
  evidence
status: To Do
assignee: []
created_date: '2026-09-10 12:06'
updated_date: '2026-09-11 06:23'
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
- [ ] #3 A readjustment instruction that asserts a FACT is distinguishable from one that asserts a STYLE preference, or the task records why that distinction cannot be drawn automatically and what the owner does instead
- [ ] #4 After the move, the same job generated at the TASK-225 bound and generated unbounded no longer disagree about any factual claim - verified by re-running the AC4 comparison, not by argument
- [ ] #5 Contradictory entries are surfaced to the owner rather than silently resolved by recency
<!-- AC:END -->

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
<!-- SECTION:NOTES:END -->
