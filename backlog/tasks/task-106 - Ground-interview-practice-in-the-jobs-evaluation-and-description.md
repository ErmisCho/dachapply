---
id: TASK-106
title: Ground interview practice in the job's evaluation and description
status: Done
assignee: []
created_date: '2026-08-16 18:38'
labels:
  - product
  - interview-coach
  - backend
  - frontend
dependencies:
  - TASK-104
  - TASK-105
priority: high
ordinal: 107000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The differentiator of the absorption — the feature neither app has alone. Generic practice
(TASK-104/105) evaluates any answer; grounded practice uses what DACHApply already knows about a
specific job: the stored description/original source text, the evaluation's gaps and weak skills,
and the user's candidate profile.

Concretely: practicing for a job whose evaluation flagged "Kubernetes: weak fit" should produce
questions that probe Kubernetes, and feedback that knows what the role asks for — turning the
evaluation's gap list from a static warning into interview preparation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Job-linked practice sessions can generate suggested interview questions derived from the job's description and its evaluation's gaps/weak skills, in the user's chosen language
- [x] #2 Evaluation feedback for job-linked sessions incorporates the job context (visible difference against an unlinked session on the same answer, demonstrated in the closing notes)
- [x] #3 A job with no evaluation degrades gracefully to generic practice with a clear notice
- [x] #4 Question generation works in heuristic mode (template-based from the gap list) so the feature exists without any LLM configured
- [x] #5 Backend tests cover grounded question generation from a fixture evaluation
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
This is the second wave of the absorption — deliberately separate from the one-shot so its
verification (including a German-language pass judged by the coordinator) is not rushed inside the
port. The gap list already exists structured on JobEvaluation; heuristic question templates over it
are the lazy floor, LLM-generated questions the env-gated ceiling — same two-tier shape as AC2 of
TASK-104.
<!-- SECTION:NOTES:END -->

## Outcome (2026-08-16, wave 12)

suggest_questions() + grounding feedback line in interview_coach.py, practice/questions/ endpoint,
SuggestedQuestions UI with click-to-fill. Heuristic templates from JobEvaluation.missing_skills +
main_gaps; LLM enhance rides the existing fallback-unless-strict shape.

MEASURED by the coordinator on the live stack: grounded=true with Kubernetes/Terraform questions in
EN and DE for an evaluated job; grounded=false with the notice "This job has no evaluation yet --
showing generic practice questions instead." plus 5 generic questions for an unevaluated one;
identical answer produced 4 feedback lines unlinked vs 5 linked, the extra line naming the job's
gaps; clicking a suggested question fills the question input. Suite 298 passed (coordinator
re-run, +10), tsc clean, npm 33/33. Asian-dad verdict: PERFECT (7/7 PASS).

Polish note (not an AC): the grounding line concatenates skills and sentence-fragment gaps in one
list ("Kubernetes, Terraform, No production Kubernetes experience") -- reads slightly awkward;
worth a phrasing pass if it ever bothers the owner.
