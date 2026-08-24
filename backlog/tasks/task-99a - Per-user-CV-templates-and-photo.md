---
id: TASK-99a
title: Per-user CV templates and photo
status: To Do
assignee: []
labels:
  - backend
  - multi-user
  - cv-generation
dependencies:
  - TASK-74
  - TASK-83
priority: medium
ordinal: 99100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split out of TASK-99 on 2026-08-24 by owner decision. This is the half that works on any deployment;
server-side generation is TASK-99b and is blocked on an infrastructure question.

Today the LaTeX templates and the CV photo are the owner's personal files, resolved from a
machine-local workspace: `cv_generator.py:103-118` walks a directory that only exists on the owner's
machine, `cv_generator.py:699` hardcodes `CVs/Picture.jpg`, and `settings.py:123` defaults the
workspace to `C:\latex`. So "which template" and "whose photo" are answered by the filesystem of one
laptop rather than by the user asking.

That is the part that has nothing to do with whether a LaTeX toolchain exists. Storing templates and a
photo per user, and selecting them per user, is storage and selection — it works identically on the
owner's machine and on the deployed site, and it is what TASK-99's AC2 asked for.

**Scope boundary, stated because it is the whole reason for the split:** this task does NOT make
generation run on the server, and does not touch the global compile lock. A second user with their own
template and photo still cannot generate in the container, because there is no `pdflatex` there. That
is TASK-99b's problem and must not be smuggled in here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Templates are stored per user and selected per user — no template is resolved from a path that only exists on one machine
- [ ] #2 The CV photo is stored and selected per user; the hardcoded `CVs/Picture.jpg` is gone, and what a user with no photo gets is stated
- [ ] #3 The owner's existing templates and photo keep working with no manual migration step, or a dry-run-by-default management command moves them and is measured before and after
- [ ] #4 A second user's template and photo are never reachable by the first — proven by a test that fails if the lookup is widened
- [ ] #5 Generation on the owner's own machine still produces the same output it does today, verified end to end rather than by unit test — this is the one path that actually runs
- [ ] #6 No behaviour depends on `CODEX_CV_ENABLED` being true, since it is DEBUG-only by design; state what a user sees where generation is unavailable
- [ ] #7 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TASK-74 already delivered per-user candidate evidence and TASK-83 the capability flag and filenames,
so the per-user shape exists to follow — read those before inventing a new one.

`Ermis-Chorinopoulos-Candidate-Evidence.md` is personal data, deliberately untracked, and must never
be committed nor depended on by a test (CLAUDE.md). The same rule applies to whatever this task does
with the photo: a fixture photo is a fixture, not the owner's.

AC5 matters more than it looks. CV generation is the one subsystem that cannot be verified in
production at all, so the owner's machine is the only place its output is real. A green unit test
proving a path resolves is not evidence that a PDF still comes out.
<!-- SECTION:NOTES:END -->
