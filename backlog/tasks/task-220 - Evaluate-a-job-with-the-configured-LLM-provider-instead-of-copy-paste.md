---
id: TASK-220
title: Evaluate a job with the configured LLM provider instead of copy-paste
status: To Do
assignee: []
created_date: '2026-09-08 11:05'
labels:
  - backend
  - frontend
  - llm
  - evaluation
dependencies: []
priority: high
ordinal: 219000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every job currently needs: generate prompt in /prompts, open ChatGPT, paste, copy the JSON back, paste into /import. That loop gates score, priority and to_apply, so it gates the whole pipeline. The README justifies it as avoiding paid LLM API calls, but that rationale no longer holds: cv_generator, cv_tasks, draft_chat, interview_coach and mailbox already call openai/anthropic/codex/ollama, and the mailbox does it unattended on a schedule. The provider abstraction, the model picker and the strict JSON importer all already exist; what is missing is the wire between build_prompt and the provider call. Ollama keeps it free. Filed 2026-09-08.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A job can be evaluated from within the app using the same provider and model layer CV generation uses, with no copy-paste step
- [ ] #2 The model response is validated by the existing strict JSON importer and rejected on the same grounds a pasted response would be
- [ ] #3 The existing prompt-and-paste path still works unchanged as a fallback
- [ ] #4 Evaluating a selection is dry-run by default and reports per job what it would create or update before anything is written
- [ ] #5 A provider or validation failure names the real error and never leaves a job partially updated
- [ ] #6 Synthetic regressions cover an accepted response, a rejected malformed response, and the dry-run preview, without calling a real provider
<!-- AC:END -->
