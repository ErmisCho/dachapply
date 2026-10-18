---
id: TASK-308
title: Preparation analyses missing application requirements itself
status: To Do
assignee: []
created_date: '2026-10-18 08:43'
labels:
  - backend
dependencies: []
priority: high
ordinal: 309000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-18: PORR (job 1544) in To apply stops at 'Application requirements are not analysed yet. Analyse the job, then move it to To apply again or press Prepare.' Requirements only come from a pasted ChatGPT evaluation (json_importer); jobs evaluated before TASK-280.1 have none, so preparation never starts for them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 When prepare() finds no application_requirements, it runs the requirements analysis itself with the CV default model (cv_default_choice, run_structured_model) on the stored posting text using the existing APPLICATION_REQUIREMENTS_RULES/schema, stores the result through normalize_application_requirements (source analysis), then continues preparation
- [ ] #2 The analysis runs off the request thread; the job page shows 'Analysing application requirements' while it runs and a specific error if it fails (no silent stop)
- [ ] #3 Owner-edited requirements are never overwritten; a job with requirements behaves as before
- [ ] #4 Backend tests with a fake model: missing -> analysed -> variants queued; model failure -> visible reason; falsified
- [ ] #5 Verified on PORR 1544: preparation reaches running variants
<!-- AC:END -->
