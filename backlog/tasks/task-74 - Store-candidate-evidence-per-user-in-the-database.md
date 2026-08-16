---
id: TASK-74
title: Store candidate evidence per user in the database
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 15:25'
labels:
  - multi-user
  - cv-generation
  - backend
dependencies: []
priority: high
ordinal: 79000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`load_candidate_evidence` reads one global file path (backend/jobradar/services/cv_generator.py:257-269) defaulting to `Ermis-Chorinopoulos-Candidate-Evidence.md` at the repo root (backend/config/settings.py:64) — the owner's personal document, present only on the owner's machine and empty in production.

This is the single biggest blocker to anyone else generating a CV, and to CV generation ever running server-side: the input that grounds every generated document is a host-local personal file.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 UserProfile gains a candidate_evidence text field, editable from account settings (paste is sufficient; no file-upload machinery)
- [x] #2 CV generation uses the requesting user's stored evidence; the file path remains only as the owner's fallback when their field is empty
- [x] #3 Candidate evidence is included in the full data export and removed by account deletion (rides the existing user_data_portability and delete paths)
- [x] #4 Backend tests cover generation sourcing evidence from the profile field
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TextField + the existing profile PATCH endpoint + a textarea in ProfileSettings. The evidence file format is already free-form markdown, so pasting the same content into a DB field changes nothing downstream. Prerequisite for TASK-83 and TASK-99.

### Closing notes (2026-08-16)

`UserProfile.candidate_evidence` (TextField), read and written through the existing
`GET|PATCH /api/profile/` — no upload machinery, as the task required.

**AC2's fallback order verified in the code and by test:** the requesting user's stored evidence
wins; `CODEX_CANDIDATE_EVIDENCE_PATH` is consulted only when their field is empty. Both production
call sites in `views.py` pass `cv_profile.candidate_evidence`. The owner's existing file-based setup
keeps working untouched.

**An extra privacy leak was found while tracing this and fixed.** `load_candidate_evidence` cached
the compact evidence into a **workspace-global** `.dachapply-cache/candidate-evidence-compact.md`.
Harmless while one person generated CVs; with per-user evidence it would hand user A's personal
document to whoever generated next. Stored evidence is now never snapshotted, and only the
file-sourced path still is.

**AC3 is a privacy criterion, so it was verified in both directions rather than by adding a field
name to a list** — if export misses it the user cannot get their data out, and if deletion misses it
their data outlives their account. Measured on a scratch database with a unique marker:

    export contains the evidence marker: True
    after account deletion -> profile rows left: 0 | rows still holding the evidence: 0

The export/import round-trip trap from earlier in this run also holds: re-importing an untouched
export reports the profile as skipped, not changed, because `_parse_value` asks the model what the
field is instead of guessing from its name.

**AC1's textarea** (built by the parallel frontend agent) verified as a round trip: a labelled
20-row textarea in profile settings, saved, confirmed through `GET /api/profile/`, and still present
after a reload.

For TASK-83 (later wave): a non-owner enabled by the capability flag will generate from their own
evidence with no further change to `load_candidate_evidence`. Still owner-specific and out of scope
here: `_target_names` hardcodes `Chorinopoulos-Ermis-*` filenames.
<!-- SECTION:NOTES:END -->
