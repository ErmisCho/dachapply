---
id: TASK-387
title: 'Claim guard against unsupported certificates, language levels and tools'
status: To Do
assignee: []
created_date: '2026-11-18 22:38'
updated_date: '2026-11-18 22:51'
labels: []
dependencies: []
priority: high
ordinal: 388000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Deterministic check after generation and after every Adjust: certificates, language levels and tool/technology names in the generated TeX that do not occur in the candidate evidence are flagged (e.g. Goethe-Zertifikat B2 when evidence says otherwise). Evidence: adjustments.jsonl 2026-10-21..11-18, 130 Adjusts over 34 jobs (median 3 ready Adjusts/job); audits in jobs/6526c3ef/tmp (optimization-audit.md, ux-audit.md). Owner approved 2026-11-18.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A pure function returns the unsupported tokens for (generated text, candidate evidence); unit tests cover a certificate, a CEFR language level (A1..C2) and a tool absent from evidence, plus a case with all supported (empty result)
- [ ] #2 Generation and Adjust task reports show the flagged items; flagged items are fed to the self-review pass when it runs
- [ ] #3 No false positive for words present in the evidence in another case or with LaTeX escapes (e.g. C\# vs C#)
- [ ] #4 Guard failure never fails a run
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dropped 2026-11-18 (owner decision). Measured on 212 real generated documents in C:/latex (CVs + output): the technology check flagged 212/212 (TeX stripping glued words, section headers counted); language-level flags were mostly 'C1-Kurs'. Root cause of the Goethe-B2 Adjusts was a stale evidence file (it still said 'Goethe-Zertifikat B2, C1 course in progress'; 36 Goethe OLD/NEW edits corrected it) - evidence file updated the same day. Honesty is enforced by the TASK-385 self-review prompt instead. ACs intentionally unchecked.
<!-- SECTION:NOTES:END -->
