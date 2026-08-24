---
id: TASK-99b
title: Server-side CV generation for a non-owner
status: To Do
assignee: []
labels:
  - backend
  - multi-user
  - cv-generation
  - infrastructure
dependencies:
  - TASK-99a
priority: low
ordinal: 99200
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split out of TASK-99 on 2026-08-24 by owner decision. TASK-99a ships the per-user storage half, which
works anywhere. This is the half that cannot be built until an infrastructure question is answered.

CV generation is local-only **by design**, not by accident:

- the deployed container has no `codex`, no `claude` and no `pdflatex` (recorded in CLAUDE.md and in
  the deploy notes)
- `CODEX_CV_ENABLED` defaults to DEBUG-only (`settings.py:117`), so the capability is off in
  production on purpose
- generation serializes on a global compile lock (`cv_generator.py:32`), which is correct for one
  user on one machine and wrong for concurrent users

So a second user cannot generate a CV on the server, and no amount of application code changes that.
Someone has to decide **where the toolchain lives** first.

**This task is blocked on that decision, and is filed rather than attempted.** The options are not
equivalent and the choice has cost and security consequences:

- put `pdflatex` (and an LLM CLI, or an API call replacing it) in the container image
- run a worker on the owner's machine that the deployed site queues work to
- keep generation local forever and make the deployed site say so honestly

The third is a legitimate answer. TASK-99's own description called this "deliberately deferred until a
second CV user actually exists" — and there is still exactly one CV user.

**Do not start this task by writing code.** Start it by answering the question above with the owner.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The infrastructure decision is made and written down with its cost — image size, build time, secrets, and what runs where — before any implementation
- [ ] #2 A second (non-owner) user can generate a CV package with no files and no processes from the owner's machine involved
- [ ] #3 Concurrent generations by different users do not serialize on a global lock, proven by a test that fails against the current `cv_generator.py:32` lock
- [ ] #4 The LLM step's cost and failure mode are stated: what happens when it is unavailable, and whether a user can trigger unbounded spend
- [ ] #5 Verified in the environment it actually runs in — if that is production, a real generation there; if it stays local, the task says so and closes rather than pretending
- [ ] #6 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
There is exactly one CV user today. The honest sequencing is to leave this blocked until a second one
exists, rather than build a queue, a worker and a container toolchain for a hypothetical.

If the answer turns out to be "keep it local", this task closes as **won't do** with that reasoning
recorded, and the deployed site should say plainly that CV generation runs on the owner's machine
rather than failing silently — which is a small, real piece of work worth doing on its own.

Whatever is chosen must not weaken TASK-99a's per-user isolation: a shared server workspace that lets
one user's template or photo reach another's output would be a worse defect than the one being fixed.
<!-- SECTION:NOTES:END -->
