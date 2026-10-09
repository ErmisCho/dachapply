---
id: TASK-275
title: >-
  Azure deploys only on owner request; no scheduled jobs touch Azure; mailbox
  check runs locally
status: To Do
assignee: []
created_date: '2026-10-09 09:17'
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
- [ ] #1 deploy-container-apps.yml: build-and-push and deploy jobs run only on workflow_dispatch; push to main and pull_request still run the test job
- [ ] #2 uptime-monitor.yml has no schedule trigger (workflow_dispatch only)
- [ ] #3 mailbox-check.yml has no schedule trigger (workflow_dispatch only)
- [ ] #4 An hourly local Windows scheduled task runs check_mailbox --force from the runtime worktree, registered by a committed script, and one manual run of it records a MailboxRun
- [ ] #5 task-workflow.md and README no longer claim that merging to main deploys; they name the manual deploy command
<!-- AC:END -->
