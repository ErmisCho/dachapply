---
id: TASK-275
title: >-
  Azure deploys only on owner request; no scheduled jobs touch Azure; mailbox
  check runs locally
status: Done
assignee: []
created_date: '2026-10-09 09:17'
updated_date: '2026-10-09 12:09'
labels:
  - ci
  - cost
dependencies: []
ordinal: 272000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-10-09: Azure Container Apps costs ~0.22 EUR/day because the 30-min uptime monitor keeps waking the scale-to-zero app, and every merge to main redeploys. Owner wants the scheduled services to run locally and nothing pushed to Azure unless they say so.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 deploy-container-apps.yml: build-and-push and deploy jobs run only on workflow_dispatch; push to main and pull_request still run the test job
- [x] #2 uptime-monitor.yml has no schedule trigger (workflow_dispatch only)
- [x] #3 mailbox-check.yml has no schedule trigger (workflow_dispatch only)
- [ ] #4 An hourly local Windows scheduled task runs check_mailbox --force from the runtime worktree, registered by a committed script, and one manual run of it records a MailboxRun
- [x] #5 task-workflow.md and README no longer claim that merging to main deploys; they name the manual deploy command
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC4 superseded, not met: owner asked (2026-10-09) for automatic jobs to run only while the local app runs, so TASK-276 replaced the Windows scheduled task with an in-app loop; the script was never registered and is deleted. Merge run for #215 showed build-and-push skipped (no deploy). Azure cost was already 0.00/day since TASK-257 (Oct 1); measured via Cost Management query.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Deploys are workflow_dispatch only; uptime and mailbox workflows have no schedule.
<!-- SECTION:FINAL_SUMMARY:END -->
