---
id: TASK-61.2
title: Show truthful CV generation steps and time estimates
status: To Do
assignee: []
created_date: '2026-08-13 19:30'
labels:
  - cv-generation
  - ux
  - progress
dependencies: []
parent_task_id: TASK-61
priority: high
ordinal: 64000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace the opaque percentage-only CV/letter generation indicator with specific live phases and a completed-step count. Include preparation, model work, validation or repair, each requested TeX/PDF artifact, packaging, and cache/recompile paths. Correct the consistently optimistic remaining-time estimate using the actual route and selected provider/model settings.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The UI displays the current phase and completed/total steps throughout generation, revision, cache restoration, and PDF-only recompilation
- [ ] #2 CV and letter compilation are separate visible steps, and the UI explicitly reports when each requested PDF has compiled
- [ ] #3 Skipped artifacts and cache hits adjust the total step count instead of leaving phantom steps
- [ ] #4 Remaining-time estimates account for operation type, provider, model, effort, speed, cache state, and elapsed phase time
- [ ] #5 The estimate does not reach zero or claim imminent completion while model work or compilation is still active
- [ ] #6 Automated tests cover the event-to-progress mapping and a live benchmark records estimated versus actual duration
<!-- AC:END -->
