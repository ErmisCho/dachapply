---
id: TASK-192
title: Record which base template produced each generated CV and letter
status: In Progress
assignee:
  - '@pi'
created_date: ''
updated_date: '2026-08-27 18:09'
labels:
  - backend
  - cv-generation
dependencies:
  - TASK-99a
  - TASK-189
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/management/commands/report_cv_template_usage.py
  - backend/jobradar/tests/test_api.py
  - backend/jobradar/tests/test_cv_assets.py
priority: medium
ordinal: 192000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-25: *"whenever you create a CV motivationletter, you keep note of the filename used. if
more than 1 is used, keep them, but also keep a note of all of the bases used only once."*

**Today nothing records it, and the record cannot be reconstructed afterwards.** Measured on
2026-08-25:

- A generation runs through `cv_tasks._run`, whose state lives in a module-level in-memory dict
  (`_tasks`) that is pruned on a timer. `cv_key` and `letter_key` are passed in, used, and discarded.
  Nothing reaches the database — there is no `CvGenerationTask` model, and `cv_generator.py` writes no
  `ApplicationNote`.
- The generated file itself does not carry it. `Chorinopoulos-Ermis-CV-Formunauts-Senior-Back-End-Developer-Python.tex`
  opens with `% Formunauts Senior Back End Developer Python CV (English)` — company, role and language,
  but never the base it was rewritten from.
- So for the **16 generated CVs and 5 generated letters** already in the workspace, which base produced
  each is **unrecoverable**. This task can only start recording from now on; say so rather than
  implying the history can be rebuilt.

**Why it matters more than it looks.** There are **12 bases**, not one:

```
CVs/English - AI Engineer (base)_v_1.2 / _v_1.3 / _v_1.4 / _v_1.5 .tex
CVs/German  - AI Engineer (base)_v_1.2 / _v_1.3 / _v_1.5 .tex
Motivation_letter.tex   Motivationsschreiben.tex   Bewerbungsschreiben.tex
Anschreiben.tex         Cover_letter.tex
```

TASK-99a's importer picks the **newest** version, which is why it took `_v_1.5` and not the `_v_1.3`
the old hardcoded constant named. Older versions were live at some point, so past applications were
almost certainly built from bases that are no longer selected — and there is no way to tell which
application came from which. If an employer asks about a CV, or a base turns out to have a defect,
the blast radius is currently unknowable.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every generation records the base template filename(s) it used, durably — surviving a process restart, unlike the current in-memory task dict
- [x] #2 When a generation uses more than one base (a CV base and a letter base, or several letters), ALL of them are recorded, not just the first
- [x] #3 The record includes the base's version as it appears in the filename (`_v_1.5`), not a version-stripped key, so a later version change is distinguishable
- [x] #4 The record is reachable from the job it belongs to, so "which base produced this application" is answerable per job without reading the workspace
- [x] #5 A report lists every base and how many generations used it, and names the bases used exactly once
- [x] #6 Stated explicitly: the 16 existing generated CVs and 5 letters cannot be attributed retrospectively, and nothing in the implementation pretends otherwise
- [x] #7 Nothing personal is written anywhere new — a filename and a count only, no template content, no candidate evidence, per TASK-189
- [x] #8 Backend suite green
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Trace fresh, cached, revised, letter-only, failed, and restarted generation paths; confirm the smallest durable job-linked record.
2. Capture every actually used CvAsset filename and persist it only after successful generation, preserving full versioned names and revision lineage.
3. Add report_cv_template_usage to count each recorded base and identify bases used exactly once; do not backfill unrecoverable historical files.
4. Add focused regression coverage for multi-base/versioned filenames, restart durability, success-only persistence, reporting, and privacy; run backend suite and frontend build.
5. Finalize through Backlog CLI and run the sealed Asian Dad evaluation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**One clause of the request has two readings, and the owner should confirm which before AC5 is
built.** *"but also keep a note of all of the bases used only once"* could mean:

- **(a)** a report of bases used exactly ONCE across all generations — i.e. which templates are
  one-offs, so rarely-used ones can be pruned or consolidated. This is the reading AC5 is written
  from, because it is the one that is not already covered by AC2.
- **(b)** simply "record the base even when only one was used", which AC1 and AC2 already cover and
  which would make the clause redundant.

Reading (a) is assumed. It is cheap to satisfy either way once AC1 exists, so this is not a blocker —
but AC5's wording should be corrected through its own note if (b) was meant.

`generate_cv_package` already receives `cv_key` and `letter_key` and resolves them to `CvAsset`
instances carrying `filename` — so the data exists at the moment of generation and only needs
somewhere to go. Prefer the smallest durable home that answers AC4; a new model is not obviously
required if an `ApplicationNote` of a dedicated `note_type` will do, and that path already carries
provenance for TASK-166's created leads.

Do not store the template body. AC7 exists because TASK-189 deliberately kept the owner's templates
and photograph out of the database; recording *which file* was used must not become a route to
putting the file itself there.

Implemented with the existing job-linked ApplicationNote model (`cv_change` plus a machine-readable provenance prefix), so no schema or migration was added. Each successful task stores normalized CV/letter filename lineage; failed and cancelled tasks do not. Cache metadata is versioned to retain the actual package lineage, and revisions inherit lineage from their parent task or the latest durable job note after restart.

Added `report_cv_template_usage`, which counts a filename once per generation, lists exactly-once bases separately, skips malformed user-edited provenance safely, and explicitly states that the pre-existing 16 CVs and 5 letters cannot be reconstructed. Notes contain only document-type keys and filenames; no template body, candidate evidence, or creator identity is stored.

Validation: focused provenance tests 5 passed; backend full suite 992 passed; frontend `npm run build` passed after installing lockfile dependencies in the isolated worktree. First-gate failures were root-caused in `.orchestrator/debug/task-192-2026-08-27-feature-1-{1,2}.md` before fixes.

Completion-policy correction: implementation is committed, pushed, fully tested (992 backend tests plus frontend build), and Asian Dad verdict is PERFECT. Task remains In Progress until its branch is squash-merged into main; a post-merge completion change will set Done.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Recorded exact versioned CV and letter base filenames durably on each successful generation, preserved lineage through cache hits and revisions, and added a job-linked aggregate usage/exactly-once report. Verified with 992 backend tests and a successful frontend production build.
<!-- SECTION:FINAL_SUMMARY:END -->
