---
id: TASK-83
title: Open CV generation to trusted users via a capability flag
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 16:10'
labels:
  - multi-user
  - cv-generation
  - backend
dependencies:
  - TASK-74
priority: medium
ordinal: 88000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`is_cv_owner` compares the requester's email/username to the single `CODEX_CV_OWNER_EMAIL` env value (backend/jobradar/services/cv_generator.py:284-287, default in backend/config/settings.py:57), and all nine CV endpoints 404 for everyone else (views.py:519, 534, 561, 579, 616, 624, 643, 656, 670). The frontend hides the whole CV UI via `can_generate_cv` from /auth/me (views.py:95, 273).

Separately, output filenames hardcode the owner's name — `Chorinopoulos-Ermis-CV-*` (cv_generator.py:325-336) — so even an enabled second user would ship documents titled with the owner's name. These two ship together because a capability flag without name-derived filenames produces wrong documents.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A per-user capability flag (settable in Django admin) gates the CV endpoints instead of the env email comparison; the owner's access survives via migration or env fallback
- [x] #2 Generated CV and letter filenames derive from the requesting user's name, with the owner's output unchanged for their own account
- [x] #3 can_generate_cv in /auth/me reflects the flag, so the frontend UI appears for enabled users with no frontend change
- [x] #4 Backend tests cover an enabled non-owner reaching the endpoints and a default user still receiving 404
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Blocked by TASK-74 — without per-user evidence the flag only lets a second user generate documents grounded in the owner's history. Templates remain the owner's personal ones until TASK-99; that limitation is acceptable for a trusted friend and should be named in the UI or docs when closing.

### Closing notes (2026-08-16)

`UserProfile.can_generate_cv` (default False) now gates all nine CV endpoints through `is_cv_owner`,
with `CODEX_CV_OWNER_EMAIL` kept as a fallback *and* migration 0027 ticking the flag for that
account — belt and braces, so the owner cannot lose access whichever way the environment is set.

Measured against the running server rather than reasoned from the code:

    flag off  ->  /auth/me can_generate_cv: False,  GET /jobs/<id>/cv-generation/ -> 404
    flag on   ->  /auth/me can_generate_cv: True,   GET /jobs/<id>/cv-generation/ -> 200

AC3 therefore needed no frontend change at all: the existing `can_generate_cv` line already drives
the UI.

AC2 measured by calling the name derivation directly:

    env owner      -> Chorinopoulos-Ermis-CV-Acme-Python-Engineer.tex   (byte-identical to today)
    named user     -> Doe-Jane-CV-Acme-Python-Engineer.tex
    nameless user  -> Sam-Smith-CV-Acme-Python-Engineer.tex             (derived from the email)

The owner branch is keyed on `CODEX_CV_OWNER_EMAIL` *before* any name lookup, so their output is
unconditional — it does not depend on the migration having run or on profile data being present.

**The limitation the task itself flagged, restated at close because it is now reachable by a second
person:** templates remain the owner's personal LaTeX files and photo until TASK-99. An enabled
second user generates from *their own* evidence (TASK-74) into the owner's templates, in a **shared**
`CODEX_CV_WORKSPACE` where accounts are separated only by the filename prefix. Acceptable for a
trusted friend, as the task says — but it should be said out loud in the UI or docs before the flag
is switched on for anyone.

Not verified: real document generation. There is no model CLI or pdflatex on this machine, so
filename derivation is proven at the unit level and by asserting the requesting user's id reaches
`generate_cv_package`, not by producing a PDF.

Also fixed in passing, and worth knowing: several CV lookups (`latest_generated_sources`,
`latest_generated_artifacts`, `generation_preview`) were not user-scoped. With one CV user that was
invisible; with a capability flag it would have shown one user another's generated artifacts.
<!-- SECTION:NOTES:END -->
