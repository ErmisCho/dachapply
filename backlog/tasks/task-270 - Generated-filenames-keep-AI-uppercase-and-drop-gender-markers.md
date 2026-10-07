---
id: TASK-270
title: Generated filenames keep AI uppercase and drop gender markers
status: Done
assignee: []
created_date: '2026-10-07 10:00'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 267000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-10-07: a generated file is named `Chorinopoulos-Ermis-CV-Accenture-Ai-Engineer-For-Generative-Ai-All-Genders`. Wanted: `...-Accenture-AI-Engineer-For-Generative-AI`. "AI is always AI and not Ai or ai", and "if the gender preference is stated in the title, it doesn't need to be in the filename".

Cause: `_target_slug` in backend/jobradar/services/cv_generator.py capitalizes every slug part (`ai` -> `Ai`), and its gender regex only strips letter-slash forms like `m/w/d` or `gn` at the very end, so `(All Genders)` survives.

Scope: names of newly generated CV, letter and package files only. Existing files on disk are not renamed. Stored job titles are not changed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Company "Accenture", title "AI Engineer for Generative AI (All Genders)" gives CV name `<Applicant>-CV-Accenture-AI-Engineer-For-Generative-AI.tex`, and the letter and package names use the same target part
- [x] #2 The token AI is always `AI` in the filename, whatever its case in the title (ai, Ai, AI), and inside compounds that the title writes with AI (e.g. GenAI stays GenAI). A word that only contains the letters "ai" (e.g. Mainz, Training) is not changed
- [x] #3 Gender markers are removed wherever they appear in the title, in common English and German forms: (all genders), all genders, (m/w/d), (w/m/d), (m/f/d), (f/m/x), (d/f/m), (m/w/x), (gn), (gn*), (alle Geschlechter), and `*in`-style markers. A trailing separator left behind (" - ", "|", ",") is removed too
- [x] #4 Existing behaviour is kept: the TÜV/TUV special case, the 90-character cap, collision suffixes (-2, -3), and lookup of files generated earlier under the old names
- [x] #5 Parametrized tests cover AC1–AC3 and fail when the change is reverted; the full backend suite is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- `_GENDER_MARKER` in cv_generator.py removes gender markers anywhere in the title before slugify runs:
  - bracketed and bare forms: (all genders), (alle Geschlechter), (gn), (gn*), and letter-slash runs such as m/w/d, f/m/x and d/f/m;
  - `*in`, `:in`, `_in`, `/in` and `*innen` word endings;
  - a trailing bare `gn`.
  slugify drops the separator a marker leaves behind.
- Casing after slugify:
  - A part that is exactly `ai` becomes `AI`.
  - A mixed-case word written with AI in the title keeps it (GenAI, OpenAI).
  - Mainz, Training and Maintenance are unchanged.
  - The broken `T?V` replace was removed, because slugify already gives `tuv`, which is restored as TUV.
- Old names stay findable: `_previous_target_slug` keeps the old slug for lookup in `latest_generated_sources`. The package cache key went from v6 to v7, because a cache hit would otherwise return the zip with the old filenames. On Windows, an old `-Ai-` file and a new `-AI-` file count as the same file, so `_unique_destination` adds `-2` and never overwrites.
- Coordinator check, calling the functions directly:
  - Accenture / "AI Engineer for Generative AI (All Genders)" gives `Chorinopoulos-Ermis-CV-Accenture-AI-Engineer-For-Generative-AI.tex`, and the letter name uses the same target part.
  - "ai lead" and "Ai Lead" give AI-Lead.
  - "(w/m/d) - Berlin" gives Senior-Engineer-Berlin.
  - "(gn) | Remote" gives AI-Developer-Remote.
  - "Werkstudent:in KI" gives Werkstudent-Ki.
  - "Engineer in Vienna" is unchanged.
- Out of scope and unchanged: other acronyms are still capitalized as slug parts (RAG gives Rag, KI gives Ki), and a slash joins words (Data/Infra gives Datainfra).
- Tests: test_filename_slug.py has 34 tests; reverting `_target_slug` fails 17 of them. The full local suite has 4 test_api failures, which are environmental: this machine's Codex model cache no longer lists gpt-5.5, and they fail on HEAD too. CI is the gate.
<!-- SECTION:NOTES:END -->
