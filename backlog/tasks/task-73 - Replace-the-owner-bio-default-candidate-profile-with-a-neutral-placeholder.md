---
id: TASK-73
title: Replace the owner-bio default candidate profile with a neutral placeholder
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 15:25'
labels:
  - multi-user
  - backend
  - product
dependencies: []
priority: high
ordinal: 78000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`DEFAULT_CANDIDATE_PROFILE` is the owner's personal bio (backend/jobradar/models.py:21 — verified 2026-08-16: "Software Engineer based in Vienna…"). It is the field default for every new UserProfile (models.py:27), is backfilled whenever a profile is empty (services/prompt_builder.py:144-148), and is the anonymous fallback (prompt_builder.py:152-154).

Consequence: any registrant who skips onboarding gets every job evaluated by ChatGPT against the owner's persona — Vienna-based Python backend engineer with B2 German — and receives silently wrong fit scores, recommendations, and gap lists. This is the single most damaging default for "other users running their own search".
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 New accounts do not inherit the owner's bio: prompt generation for a user with no candidate profile either refuses with a clear "complete your profile first" message or embeds an obviously-placeholder neutral text that cannot be mistaken for a real profile
- [x] #2 Existing profiles are untouched — a data migration pins the current text explicitly onto rows that hold it today (the owner's account keeps working unchanged)
- [x] #3 The UI nudges profile completion at the point of prompt generation when the profile is empty or placeholder
- [x] #4 Backend tests cover prompt generation for a profile-less user
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Refusing ("complete your profile") is more honest than a neutral placeholder — a placeholder still produces evaluations scored against nobody. Migration: set candidate_profile = DEFAULT_CANDIDATE_PROFILE explicitly where it is currently empty-and-defaulted or equal to the default, then change the field default to ''.

### Closing notes (2026-08-16)

**The ticket listed three leak paths. There were five.** The two it missed were both real:

4. `serializers.validate_candidate_profile` returned the owner's bio for any blank save — so a user
   could not empty their own profile even deliberately. Verified after the fix: `PATCH
   {"candidate_profile": ""}` now returns `''` (0 chars) and the bio does not come back.
5. `exporters.chatgpt_brief` embedded the bio in the generated markdown brief. It now prints
   `(no candidate profile saved - add one in Settings before using this brief)`.

Plus the three named ones: the field default (now `''`), the empty-profile backfill in
`user_profile_settings`, and the anonymous fallback in `build_candidate_profile_text`. A grep for
`DEFAULT_CANDIDATE_PROFILE` and for the bio's own words now hits only migrations 0010 and 0025
(self-contained history) and the one test that reads the constant from 0025. No runtime path
reaches it.

The refusal lives at the single `_profile()` chokepoint that all four `build_*_prompt` functions
route through, so a fifth prompt endpoint inherits the guard rather than having to remember it.

**AC1 verified end to end against a genuinely clean account** (this is worth spelling out, because
the first attempt produced a false alarm): a user created *before* the restart had already been
backfilled by the old code, so its prompt still contained the bio and looked like a live leak. On a
user created after the restart:

    POST /api/prompts/generate/  ->  400
    {"code":"candidate_profile_required",
     "detail":"Add your candidate profile in Settings before generating a prompt. Prompts are
               scored against your profile, and an empty one would score every job against nobody."}

Refusal, not a placeholder — which is the honest choice the task argued for, since a placeholder
still produces evaluations scored against nobody.

**AC2** is satisfied and its limits are stated. The migration writes back exactly the bytes it
matched, so on a healthy database it changes zero rows' content — Django materialises field defaults
at INSERT, never in the DDL, so every legacy row already stored the text verbatim. It is a genuine
guard only for a row inserted against a database-level default (old SQLite table rebuilds). Empty
rows are deliberately **not** backfilled; that would be the leak rather than the fix. Confirmed on
the scratch database: the owner's existing profile still holds its 855 characters after migrating.

**AC3 needed no new frontend code, and that is the right outcome.** The refusal's `detail` flows
through the app's existing error affordance, so at the point of prompt generation an empty-profile
user sees the message above, on a page that already carries a Settings link — measured in a browser.
A machine-readable `code: "candidate_profile_required"` and `GET /api/auth/me/ ->
candidate_profile_missing: true` are also exposed for a richer nudge later; matching on `code`
rather than message text is what a future frontend should do.
<!-- SECTION:NOTES:END -->
