---
id: TASK-57
title: Run application-generation agents in parallel with cancellation
status: Done
assignee:
  - '@pi'
created_date: '2026-08-12 17:19'
updated_date: '2026-08-12 17:32'
labels: []
dependencies: []
ordinal: 58000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Batch CV and motivation-letter generation currently uses one serial worker. Run each selected job as an independent asynchronous AI generation agent, and let the owner cancel any queued or active generation before completion.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Selected jobs start as independent background generation agents and can make progress concurrently
- [x] #2 Each active single-job, batch-row, and readjustment task exposes a Cancel action until it reaches a terminal state
- [x] #3 Cancellation stops the active model or LaTeX subprocess, marks only that task cancelled, and does not save or learn unfinished output
- [x] #4 Task status, aggregate batch progress, authorization, and ETA remain correct for ready, failed, and cancelled tasks
- [x] #5 Focused cancellation/concurrency tests, the full backend suite, and the frontend production build pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Replace the serial queue with one daemon-backed task agent per application and update parallel ETA/status semantics. 2. Add cooperative cancellation from task state through model/LaTeX subprocess termination, with no persistence or learning after cancellation. 3. Add an owner-only cancel endpoint and per-task Cancel controls in single, batch, and readjustment flows. 4. Add focused concurrency/cancellation tests, run full checks, restart localhost, and verify live cancellation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Replaced the serial worker with one independent daemon-backed CLI agent per application task, so batch jobs enter model generation concurrently. Added cooperative cancellation through task state, model/LaTeX Popen polling, Windows child-process-tree termination, a user-scoped cancel API, and Cancel controls for single generation, each batch row, and readjustments. Cancelled work is terminal with zero ETA and cannot be downloaded, persisted, copied, or learned. Live verification started two gpt-5.6-sol agents simultaneously, cancelled the first while the second remained running, then cancelled the second; both reached cancelled, zero matching Codex processes remained, health stayed 200/database ok, and server logs contained no errors. Validation: 7 focused tests passed; full backend suite passed (129 tests); frontend production build passed; makemigrations --check, py_compile, and diff check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Application packages now run as independent parallel AI agents. Every active single, batch, and readjustment task can be cancelled independently, including termination of model/LaTeX child processes and prevention of unfinished output persistence or learning. Verified live and with 129 backend tests plus the frontend build.
<!-- SECTION:FINAL_SUMMARY:END -->
