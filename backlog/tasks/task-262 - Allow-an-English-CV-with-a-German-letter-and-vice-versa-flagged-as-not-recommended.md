---
id: TASK-262
title: >-
  Allow an English CV with a German letter (and vice versa), flagged as not
  recommended
status: To Do
assignee: []
created_date: '2026-10-05 11:43'
updated_date: '2026-10-05 13:18'
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
- [x] #1 In single-job and bulk generation, the Letter dropdown offers letters of every language, not only the CV's language
- [x] #2 Same-language letters are listed first; cross-language options are labelled '(not recommended)' and a warning shows under the selector when a mismatched pair is selected
- [x] #3 Generating with a mismatched pair succeeds and produces the chosen-language letter (backend test with en CV + de letter)
- [x] #4 Default selection is unchanged: the CV language's first letter
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified 2026-10-05 on a branch server (127.0.0.1:8010, scratch sqlite + scratch CV workspace, real Codex low-effort generation of 2 jobs): single popup and bulk rows list all letters, same-language first, others '(not recommended)', amber warning shown; real generation en CV + Anschreiben produced an English CV ('\section{Experience}') and a German letter ('Sehr geehrte Damen und Herren').
<!-- SECTION:NOTES:END -->
