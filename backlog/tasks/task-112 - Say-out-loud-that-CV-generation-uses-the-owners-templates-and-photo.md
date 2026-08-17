---
id: TASK-112
title: Say out loud that CV generation uses the owner's templates and photo
status: To Do
assignee: []
created_date: '2026-08-17 16:05'
labels:
  - cv-generation
  - multi-user
  - docs
dependencies: []
priority: medium
ordinal: 112000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`can_generate_cv` can be granted to any account today from Django admin (`backend/jobradar/admin.py:22-31`,
`UserProfileInline`). Whoever is granted it generates CVs built from **the owner's** LaTeX templates and
**the owner's** photograph — `cv_generator.py:699` hardcodes `workspace / 'CVs/Picture.jpg'` and makes it a
required input of every generation, with no user dimension anywhere near it.

Nothing says so. The operator granting the flag sees a bare checkbox: `models.py:71` is
`can_generate_cv = models.BooleanField(default=False)` with no `help_text`, and `UserProfileAdmin`
(`admin.py:516-519`) sets only `list_display`/`search_fields`. A grep of `frontend/src`, `docs/` and
`README.md` for any statement about shared templates or a shared photo returns nothing.

TASK-83 closed with exactly this as an outstanding item — its notes (`task-83…md:64-66`) say the
shared-template and shared-photo limitation "should be said out loud in the UI or docs before the flag is
switched on for anyone", and its own rubric made that a criterion. The flag shipped; the sentence did not.

This is not TASK-99's work. TASK-99 *fixes* the sharing and is deliberately deferred until a second real CV
user exists. This task makes the deferral **safe** in the meantime, by ensuring nobody grants the capability
without knowing what it hands over. A deferral that is merely recorded protects nothing; one whose limitation
is visible at the moment of granting does.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `can_generate_cv` carries a `help_text` naming exactly what a flagged user gets: the owner's LaTeX templates, the owner's photo, and a shared output directory
- [ ] #2 The `help_text` is visible to the operator at the point of granting — verified by loading the admin page for a UserProfile and reading it on screen, not by reading the model definition
- [ ] #3 The same limitation is stated once in a durable place a future maintainer will find — `docs/production-readiness.md` alongside the existing `CODEX_CV_ENABLED=False` guidance, or the CV section of the README
- [ ] #4 The wording names the photo explicitly, not just "templates" — the photo is the part that embarrasses, and "templates" reads as `.tex` files only
- [ ] #5 A migration is generated and applied for the `help_text` change, and `cd backend && uv run pytest -q` still passes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Small task — a `help_text`, a migration, and a paragraph. Filed 2026-08-17 out of the TASK-99 deferral audit
rather than found by a user, which is the good case: the flag is grantable now and the disclosure is missing
now, but nobody has been given the flag yet.

Note for whoever picks this up: a `help_text` change on a `BooleanField` still produces a migration in Django
even though nothing about the column changes. Generate it rather than hand-editing, and do not be surprised
that it is a no-op at the database level.

AC2 exists because a `help_text` that is present in the model but not rendered by the admin form is a
disclosure that nobody reads. `UserProfileInline` is an inline on the User admin — confirm the text actually
appears there, which is where the granting happens, not only on a standalone UserProfile page.

Related: [[TASK-99]] fixes the underlying sharing; [[TASK-83]] is where this was promised.
<!-- SECTION:NOTES:END -->
