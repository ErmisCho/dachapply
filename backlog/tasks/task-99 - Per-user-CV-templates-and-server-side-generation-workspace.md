---
id: TASK-99
title: Per-user CV templates and a server-side generation workspace
status: To Do
assignee: []
created_date: '2026-08-16 00:43'
labels:
  - multi-user
  - cv-generation
  - backend
dependencies:
  - TASK-74
  - TASK-83
priority: low
ordinal: 104000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The last increment of multi-user CV generation, filed now so the plan is not lost, deliberately deferred until a second CV user actually exists.

Today the LaTeX templates and the CV photo are the owner's personal files resolved from a machine-local workspace (backend/jobradar/services/cv_generator.py:103-118 and the hardcoded `CVs/Picture.jpg` at cv_generator.py:699; `C:\latex` default at backend/config/settings.py:123), generation serializes on a global compile lock (cv_generator.py:32), and `CODEX_CV_ENABLED` defaults to DEBUG-only (settings.py:117) — so CV generation is local-only by design. TASK-74 (per-user evidence) and TASK-83 (capability flag + filenames) deliver most of the multi-user value on the owner's machine first; this task is what remains for generation to run on the server for anyone.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A second (non-owner) user can generate a CV package with no files from the owner's machine involved
- [ ] #2 Templates **and the CV photo** are stored and selected per user
- [ ] #3 Concurrent generations by different users do not serialize on a global lock
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Do not start this before TASK-74 and TASK-83 are done and a real second CV user is asking — the server-side workspace (LaTeX toolchain in the container, per-user temp dirs, output storage) is the expensive part and is worthless until then.

### 2026-08-17 — deferral audited and confirmed defensible; two wording defects fixed

Audited rather than rubber-stamped, because a deferred task with no owner and no review date is how
real work rots. The deferral holds: TASK-74 and TASK-83 are both Done, so the only remaining gate is
the human trigger, and the expensive part is genuinely worthless with one user. The trigger is stated
in this file rather than only in the wave plan, so the task cannot be picked up by mistake.

**AC2 was reworded to name the photo, and that is a tightening, not a relaxation.** `cv_generator.py:699`
hardcodes the picture and makes it a hard requirement of every generation, for every user:

    picture_source = workspace / 'CVs/Picture.jpg'
    required = ([cv_source, picture_source] if create_cv else []) + ...

There is no user dimension anywhere near it, and the same path is used again on the recompile route.
AC2 previously said only "templates are stored and selected per user" — which an implementer could
satisfy literally, shipping per-user `.tex` files while still putting the owner's face on every other
user's CV. TASK-83's closing notes already flagged that templates "and photo" stay shared until this
task; the AC just never absorbed it. Adding it makes the criterion harder to satisfy, so TW-005's
"reword through its own filed task" paper trail is not triggered — that rule guards against silent
*weakening*.

**AC3 is deliberately left as-is, and here is the hazard it carries.** The lock is real, not
speculative — `cv_generator.py:32` `_LATEX_LOCK=Lock()`, taken at `:504` under a comment naming the
reason: TeX Live shares Windows caches, so two concurrent `pdflatex` passes clash. Two things a future
implementer must know:

- **AC3 as written is satisfied by deleting line 32**, which reintroduces exactly the clash the lock
  exists to prevent. The AC names a *mechanism to remove* rather than a *property to hold*. Do not
  read it literally; the property wanted is "two users' compiles run in separate working directories
  and neither waits on the other".
- **The lock is per-process, so it is already not globally exclusive.** `Dockerfile:18` sets
  `WEB_CONCURRENCY=2`; two gunicorn workers each hold their own `_LATEX_LOCK`. Same caveat class the
  codebase already records for the alert cooldown.

AC3's wording is not changed here: unlike AC2 that would be a change of substance, and substance is
the owner's call, not an agent's. It is recorded so the trap is visible at implementation time.

Also corrected: the four code citations in the description had drifted (TASK-111 inserted
`settings.py:61-83` and pushed everything down). Every claim they supported is still true.

**Verified still local-only by four independent gates**, so the deferral is safe as well as recorded:
no `texlive`/`codex`/`claude` in the image (`Dockerfile:11-29`), `CODEX_CV_ENABLED` defaults to DEBUG
(`settings.py:117`), `CODEX_CV_WORKSPACE` empty when not DEBUG (`settings.py:123`), and
`can_generate_cv` is gated behind the flag in `is_cv_owner` (`cv_generator.py:312`).

The one thing this audit did *not* find a home for is filed as its own task — see TASK-112.
<!-- SECTION:NOTES:END -->
