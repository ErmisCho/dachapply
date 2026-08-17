---
id: TASK-112
title: Say out loud that CV generation uses the owner's templates and photo
status: Done
assignee: []
created_date: '2026-08-17 16:05'
updated_date: '2026-08-17 19:00'
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
- [x] #1 `can_generate_cv` carries a `help_text` naming exactly what a flagged user gets: the owner's LaTeX templates, the owner's photo, and a shared output directory
- [x] #2 The `help_text` is visible to the operator at the point of granting — verified by loading the admin page for a UserProfile and reading it on screen, not by reading the model definition
- [x] #3 The same limitation is stated once in a durable place a future maintainer will find — `docs/production-readiness.md` alongside the existing `CODEX_CV_ENABLED=False` guidance, or the CV section of the README
- [x] #4 The wording names the photo explicitly, not just "templates" — the photo is the part that embarrasses, and "templates" reads as `.tex` files only
- [x] #5 A migration is generated and applied for the `help_text` change, and `cd backend && uv run pytest -q` still passes
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

---

**Closing note (2026-08-17 19:00):**

Added `help_text` to `UserProfile.can_generate_cv` (`backend/jobradar/models.py:71`):

> "Generates CVs and cover letters from the site owner's private LaTeX templates and the owner's
> own photograph, and writes them into a shared output directory on the server -- not this
> account's own templates or photo."

Grounded in `services/cv_generator.py`: `picture_source=workspace / 'CVs/Picture.jpg'` (line 699,
required whenever `create_cv` is set, no per-user path anywhere near it) and
`persist_generated_files` (lines 439-441, writes into `workspace/'CVs'` and `workspace/'output'`,
the same directories for every flagged account).

Migration: generated with `DJANGO_SETTINGS_MODULE=config.settings_test uv run manage.py
makemigrations jobradar` -> `backend/jobradar/migrations/0034_alter_userprofile_can_generate_cv.py`
(an `AlterField`, no column change). `makemigrations --check --dry-run` afterwards reported "No
changes detected", so there is no drift. Not run through `manage.py migrate` against this machine's
own `DATABASE_URL` -- per TASK-100 that value resolves to the production Neon database from the
repo-root `.env`, and the settings guard refuses to run migrate commands against it without
`DACHAPPLY_ALLOW_PROD_DB=1`, which is out of scope for a disclosure-only change. The migration is
applied automatically both by pytest (every test run builds a fresh test database from the full
migration history -- proven by the suite below passing) and by the deploy container's
`migrate --noinput` step (`docs/production-readiness.md` section 2) on the next push to `main`.

AC2 (does the text actually render where the flag is granted, not just exist on the model): added
`backend/jobradar/tests/test_admin_cv_disclosure.py`. It logs a superuser in through the real
`/admin/login/` view (`Client.force_login()` alone sets the wrong session cookie here --
`config.middleware.SplitAdminSessionMiddleware` keys `admin_sessionid` off the request path, so a
plain `force_login()` authenticates the app session, not the admin one, and the change page 302s
back to the login form), then GETs `/admin/auth/user/<pk>/change/` -- the `UserProfileInline` page,
not a standalone `UserProfile` admin page -- and asserts the three required substrings are present
in the rendered HTML: `"the site owner's private LaTeX templates"`, `'photograph'`, `'shared output
directory'`. Ran alone: `1 passed in 11.70s`.

Doc: added one paragraph to `docs/production-readiness.md` section 3 ("Optional owner-only Codex CV
generation"), right after the existing `CODEX_CV_ENABLED=False` guidance, naming the owner's
templates, the owner's photograph, and the shared output directory, and pointing at TASK-99 for the
real fix. Not duplicated in README.md (grepped for `can_generate_cv` / shared-photo language there
first -- no existing statement, so this is the one place per AC3).

Full suite: `cd backend && uv run pytest -q` -> `419 passed in 872.57s` (418 pre-existing + the new
AC2 test). No CV-generation code (`cv_generator.py`) was touched -- this is a disclosure-only
change, model help_text + migration + docs + one admin-rendering test.

All five ACs are proven, not asserted: #1/#4 by reading the help_text string above, #2 by the
passing admin-render test, #3 by the doc diff and the README grep showing no duplicate, #5 by the
migration/`--check` output and the full pytest tail.
<!-- SECTION:NOTES:END -->
