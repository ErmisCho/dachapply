---
id: TASK-348
title: Generate all cover letter options in the queue and pick which TeX to copy
status: Done
assignee: []
created_date: '2026-11-05 19:19'
labels:
  - frontend
  - backend
dependencies: []
priority: high
ordinal: 347000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report: sometimes the wrong cover letter gets generated. Generate every applicable letter option for a job at once while it is in the queue, then let the owner choose from a dropdown which generated TeX file to copy into ChatGPT as a prompt for adjustment.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A queued job generates every applicable letter option in one run, not only the one the app guessed
- [x] #2 After generation a dropdown lists every generated TeX file by a readable name, with the recommended one preselected
- [x] #3 Copying uses the selected file as the ChatGPT adjustment prompt
- [x] #4 Changing the dropdown never regenerates a document or calls a model
- [x] #5 If one option fails the others stay usable and the failure shows inline
- [x] #6 Time estimates and queue progress stay honest for the extra letters
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
A wanted full letter is now prepared once per stored letter template of its language. The recommended template keeps `letter-<lang>`; the others are `letter-<lang>-<template>`. The real account has 3 German templates and 1 English, so a German letter job now makes 3 letters and costs 3 model runs instead of 1. Short messages stay one per language.

The job page has a dropdown of the ready TeX files with Copy TeX beside it. Copy reuses `export/?as=tex&key=`.

Verified on this branch's real runtime with a disposable sqlite database and workspace; only the model call was faked. Not exercised: a real model or real pdflatex in the browser run, and letters running at the same time (concurrency is 1 by default).
<!-- SECTION:NOTES:END -->
