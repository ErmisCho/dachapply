---
id: TASK-260
title: >-
  Job text from the ChatGPT import should be a structured extract in the
  posting's own words
status: Done
assignee: []
created_date: '2026-10-02 05:58'
labels:
  - backend
  - ux
dependencies: []
priority: medium
ordinal: 258000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-10-02 with screenshot (Mercor job): the accepted job text reads 'A complete verbatim reproduction of the external posting is not provided. The role asks...' followed by a 3-sentence summary. Cause: prompt_builder.py default templates (combined :62, enrichment :78, bulk links :94) instruct ChatGPT to 'copy the complete job posting verbatim ... Never summarize'; ChatGPT declines a full copy and its refusal plus a summary is stored as original_source_text. Owner wants instead: a very short overview, then required experience, preferred qualifications, tasks, pay etc., kept as close to the posting's real wording as possible, with no meta-commentary.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every default prompt template that fills original_source_text asks for a structured extract instead of a full verbatim copy, and none still instructs copying the complete posting verbatim
- [x] #2 The extract is ordered: Overview (at most 2 sentences), Required experience, Preferred qualifications, Tasks/responsibilities, Pay/compensation, then location/work mode and other details (benefits, process); a section the posting does not have is omitted, never invented
- [x] #3 The prompt requires the posting's own wording, bullet points and original language (no translation or paraphrase beyond the overview), excludes page clutter such as navigation, hiring counters and unrelated links, and forbids commentary about what is or is not reproduced
- [x] #4 A user whose saved custom prompt template still contains the old verbatim instruction also gets the new instruction, without the stored template being rewritten by a migration
- [x] #5 Tests pin the new instruction in every affected template and the custom-template case, and fail when the old wording is restored
- [x] #6 Owner confirms on one real ChatGPT import that the stored text has the requested sections in the posting's wording and no refusal sentence
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- One shared constant `ORIGINAL_SOURCE_TEXT_RULES` in `backend/jobradar/services/prompt_builder.py`, concatenated into the three templates that fill original_source_text (combined, enrichment, bulk links). The evaluation template never asked for original_source_text and is unchanged. The wording asks for "the posting's requirements and details, quoted in the posting's own words" under ordered headings, and avoids "verbatim" and "complete posting", which is the phrasing that triggered the refusal.
- Schema hint: COMBINED/ENRICHMENT/BULK_LINKS schemas said `"complete original job text without truncation"`. All three now use one `SOURCE_TEXT_SCHEMA_FIELD` that points at the rules. Custom templates pull `{schema}` at build time, so they get the new hint too.
- Custom templates (AC4): `_render_template` runs `_upgrade_old_source_text_instruction` first. It is a regex that swaps the shipped old sentences (both the "Open the/each job URL when available and copy ..." form and the bulk "Copy ..." form, plus the "Never translate ... original_source_text." sentence) for the new rules, at build time only. There is no migration, and the stored template is not rewritten (a test asserts this). A hand-reworded variant of the old sentence is not matched.
- Real path traced: frontend `/prompts/combined/` (dashboard openPrompt, quick prompt after add, job-detail calibration), `/prompts/enrich/`, `/prompts/bulk-links/` reach views.py generate_combined_prompt / generate_enrichment_prompt / generate_bulk_links_prompt. Each one calls build_*_prompt with `profile.<kind>_prompt_template`, which goes through `_render_template`. The dashboard's localStorage "prompt prefs" only edit the open modal once and are never reapplied to a later prompt, so the server is the only build path.
- Tests (backend/jobradar/tests/test_api.py): `test_every_source_text_prompt_asks_for_a_structured_extract_not_a_verbatim_copy` and `test_saved_custom_template_with_the_old_verbatim_sentence_gets_the_new_instruction`. Revert checks, each run with the change undone on its own: old wording back in the default templates fails the first test; old schema text fails both; dropping the build-time upgrade fails the custom-template test.
- Full suite: `1260 passed, 526 warnings in 451.66s`.
- AC6 (a real ChatGPT import) is the owner's to confirm.

AC6 confirmed by the owner on 2026-10-07 ("task 260 works now") after a real ChatGPT import.
<!-- SECTION:NOTES:END -->
