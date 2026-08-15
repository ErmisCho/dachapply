---
id: TASK-66
title: Recalibrate TASK-61.3 AC5 revision-speed threshold against measured data
status: Done
assignee:
  - '@claude'
created_date: '2026-08-15 14:10'
updated_date: '2026-08-15 14:30'
labels:
  - cv-generation
  - performance
  - chore
dependencies: []
priority: medium
ordinal: 71000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-61.3 AC5 required a representative simple revision to reach Ready within 30 seconds. Eight live runs against a real provider show that threshold is unreachable, and that it was never an app-side target in the first place.

The 30s figure was written before any live measurement existed, on the assumption that the prompt size was the bottleneck. TASK-61.3 duly cut the revision prompt from 48,301 to 1,159 characters (97.6%). The measurements show the prompt was not the bottleneck: the model still reads the source TeX and reasons about the edit, so the provider round-trip alone is 50-162 seconds depending on model, effort and speed.

Relaxing an acceptance criterion deserves a record, hence this task rather than a silent edit.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The revised threshold is derived from recorded measurements, not estimated
- [x] #2 The restated criterion separates app-side cost, which the project controls, from provider round-trip time, which it does not
- [x] #3 TASK-61.3 AC5 can be checked off against evidence in cv-benchmarks.jsonl
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Eight live runs on 2026-08-15 (job 1051, seeded demo data), recorded in C:/latex/.dachapply-cache/cv-benchmarks.jsonl. Seven succeeded; the eighth failure is covered separately below.

    route       eff/spd         scope       total     model    app-side
    generation  medium/normal   cv+letter   109.0s    102.8s      6.02s
    revision    medium/normal   cv+letter   166.4s    161.9s      4.24s
    revision    low/fast        cv+letter    67.3s     62.5s      4.49s
    revision    low/fast        cv only      53.8s     50.5s      3.06s
    revision    low/normal      cv only      60.2s     57.1s      2.74s   (gpt-5.4-mini)
    revision    medium/fast     cv+letter   119.9s    115.5s      4.12s
    revision    medium/fast     cv only      96.0s     93.2s      2.56s

App-side cost - preparing, LaTeX compile, saving - is 2.56s to 6.02s across every run. The model call is 50.5s to 161.9s. The fastest configuration reachable at all was 53.8s, still 79% above the old 30s target, and the mini model was not faster than gpt-5.5. No app-side change reaches 30 seconds.

AC5 restated as two measurable halves: end-to-end within 150s at the UI default (medium effort, fast speed, since gpt-5.5 reports a fast tier), where the worst observed default run was 119.9s; and app-side overhead outside the model call under 10s, where the worst observed was 6.02s. The second half is the part the project actually controls, and it is the one worth defending in future changes.

Context worth keeping: the original complaint behind TASK-61.3 was that simple edits took 5-7 minutes (300-420s). At the default configuration a simple revision now takes 96-120s, a 3-4x improvement, and the prompt reduction is what delivered it. The goal was met; only the number written down was wrong.

Two defects surfaced by the same runs, fixed under TASK-61.3 rather than here:
- Revisions failed after ~5 minutes with "server closed the connection unexpectedly". _learn_application_preference issues the first query after the model call, and Neon's pooler had dropped the idle connection while CONN_MAX_AGE=600 left Django treating it as fresh. Generation never hit it because empty instructions return before any query.
- _task_timing's revision_factor was 0.55, assuming a smaller prompt meant a faster call. Measured, revisions are ~1.6x slower than generations at identical settings; estimates were ~2x optimistic, which was TASK-61.2's original complaint. Recalibrated against these runs to within 7%.
<!-- SECTION:NOTES:END -->
