---
id: TASK-260
title: >-
  Job text from the ChatGPT import should be a structured extract in the
  posting's own words
status: To Do
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
- [ ] #1 Every default prompt template that fills original_source_text asks for a structured extract instead of a full verbatim copy, and none still instructs copying the complete posting verbatim
- [ ] #2 The extract is ordered: Overview (at most 2 sentences), Required experience, Preferred qualifications, Tasks/responsibilities, Pay/compensation, then location/work mode and other details (benefits, process); a section the posting does not have is omitted, never invented
- [ ] #3 The prompt requires the posting's own wording, bullet points and original language (no translation or paraphrase beyond the overview), excludes page clutter such as navigation, hiring counters and unrelated links, and forbids commentary about what is or is not reproduced
- [ ] #4 A user whose saved custom prompt template still contains the old verbatim instruction also gets the new instruction, without the stored template being rewritten by a migration
- [ ] #5 Tests pin the new instruction in every affected template and the custom-template case, and fail when the old wording is restored
- [ ] #6 Owner confirms on one real ChatGPT import that the stored text has the requested sections in the posting's wording and no refusal sentence
<!-- AC:END -->
