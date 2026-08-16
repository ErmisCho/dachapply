---
id: TASK-104
title: Absorb the interview coach evaluator and practice sessions into the backend
status: Done
assignee: []
created_date: '2026-08-16 18:38'
labels:
  - product
  - backend
  - interview-coach
dependencies: []
priority: high
ordinal: 105000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision 2026-08-16: absorb https://github.com/ErmisCho/ai-interview-coach-dach into
DACHApply. The coach is a bilingual (DE/EN) interview-answer evaluator — scores clarity, structure
and confidence, suggests a stronger rewrite, tracks progress — as a small FastAPI/Next.js MVP.

The asset is the Python evaluator, not the app shell. The whole backend is five files
(`backend/app/analysis.py`, `schemas.py`, `storage.py`, `main.py`, plus `tests/test_analysis.py`),
with four evaluator modes: `heuristic` (deterministic), `ollama`, `ollama-windows`,
`openai-compatible`, and a fallback to heuristics when the configured model is unreachable unless
`LLM_STRICT=true`. Python-to-Python means the evaluator ports nearly verbatim into a Django
service, following the `cv_generator.py` pattern (local LLM as an owner-machine feature,
deterministic mode everywhere). The Next.js frontend, FastAPI scaffolding, and WSL launcher
scripts are deliberately discarded.

This fills the lifecycle hole the discovery audit named: interviews were the stage living entirely
outside the app. TASK-78 added the date; this adds the preparation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A jobradar service module provides the answer evaluation (clarity/structure/confidence scores, feedback, rewrite) in both German and English, ported from the coach's analysis.py with its tests carried over and passing under uv run pytest -q
- [x] #2 The heuristic mode works everywhere with no LLM configured; the local-LLM modes are env-gated the same way CV generation is, and an unreachable model falls back to heuristics unless strict mode is set
- [x] #3 A PracticeSession model stores question, answer, language, scores, feedback and timestamp, with an optional link to a JobLead, scoped through the same per-user access rules as jobs
- [x] #4 REST endpoints exist to submit an answer for evaluation and to list practice history (per user, newest first), covered by backend tests
- [x] #5 Practice sessions ride the existing data-portability export and account deletion paths
<!-- AC:END -->

## Outcome (2026-08-16, wave 11)

Evaluator ported nearly verbatim into `jobradar/services/interview_coach.py` (541 lines; one
documented change — the coach's private .env loader dropped since settings.py already loads .env).
PracticeSession (migration 0029) is user-owned CASCADE with a SET_NULL job link, deliberately not
the created_by|submitted_for pattern, per TASK-103's lesson. Endpoints at practice/evaluate/ and
practice/history/. Export includes practice_sessions (re-import intentionally not wired — no
natural conflict key; unrecognized keys are ignored on import, verified by existing tests).

MEASURED by the coordinator, not taken from the agent: full suite re-run 288 passed (271 baseline
+ 17 new, including fallback-unless-strict against a real closed port and cross-user access
rejection); port fidelity spot-checked against the coach source (same constants, signatures,
scoring baselines). Live browser: EN answer scored 75/70/88/66, DE answer 76/70/80/78 with German
feedback and rewrite, both heuristic mode. Asian-dad verdict: PERFECT (7/7 PASS).

Known deliberate omissions: no admin registration, no throttle on evaluate (heuristic is cheap;
revisit if an LLM mode ever runs server-side), no re-import of practice sessions.

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Read the coach's analysis.py before porting — the task assumes it is self-contained; if it imports
FastAPI types, split the pure logic from the transport first. Mind TASK-103: account deletion has a
known ownership bug — scope PracticeSession deletion to the session's own user and do not copy the
Q(created_by)|Q(submitted_for) pattern. One agent should take this and TASK-105 in one wave
(one-shot), owning both territories.
<!-- SECTION:NOTES:END -->
