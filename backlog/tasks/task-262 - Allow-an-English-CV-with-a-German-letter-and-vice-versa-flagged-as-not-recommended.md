---
id: TASK-262
title: >-
  Allow an English CV with a German letter (and vice versa), flagged as not
  recommended
status: To Do
assignee: []
created_date: '2026-10-05 11:43'
labels: []
dependencies: []
priority: medium
ordinal: 260000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Letter options are currently tied to the CV language. Owner wants to pick e.g. English CV + German Anschreiben, single and bulk generation, with a visible 'not recommended' hint when CV and letter languages differ.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 In single-job and bulk generation, the Letter dropdown offers letters of every language, not only the CV's language
- [ ] #2 Same-language letters are listed first; cross-language options are labelled '(not recommended)' and a warning shows under the selector when a mismatched pair is selected
- [ ] #3 Generating with a mismatched pair succeeds and produces the chosen-language letter (backend test with en CV + de letter)
- [ ] #4 Default selection is unchanged: the CV language's first letter
<!-- AC:END -->
