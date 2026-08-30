---
id: TASK-203
title: Finish repository and Pi housekeeping
status: In Progress
assignee:
  - '@pi'
created_date: '2026-08-30 07:59'
updated_date: '2026-08-30 12:27'
labels:
  - housekeeping
  - backlog
  - pi
dependencies: []
modified_files:
  - >-
    backlog/tasks/task-99 -
    Per-user-CV-templates-and-server-side-generation-workspace.md
  - >-
    backlog/tasks/task-111 -
    Serve-the-local-app-against-the-remote-database-by-default.md
  - >-
    backlog/tasks/task-204 -
    Serve-the-local-app-against-the-remote-database-by-default.md
  - backlog/tasks/task-203 - Finish-repository-and-Pi-housekeeping.md
priority: low
type: chore
ordinal: 203000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Remove the remaining maintenance warnings and obsolete recovery residue after TASK-202: repair the duplicate TASK-111 identity safely, resolve references that can be disambiguated, remove the orphaned TASK-113 directory without affecting active work, and activate or precisely hand off the already-configured Pi notifier reload.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Backlog doctor reports no duplicate task IDs
- [ ] #2 Addressable task references are disambiguated; intentionally historical text and the malformed CLI-inaccessible wave-plan are explicitly classified
- [ ] #3 The obsolete task-113-actionable-reminders directory is removed without terminating unrelated processes
- [ ] #4 The finish-only notifier configuration is active in the current Pi session, or the one unavoidable interactive command is explicitly identified
- [ ] #5 Released main, the synchronized local runtime, Feedback/SixRobotics.MD, and the TASK-202 recovery archive remain intact
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Create this active housekeeping record, then run Backlog doctor in an isolated main-based worktree so the existing task receives the next free ID. 2. Review and update only unambiguous references through Backlog CLI operations. 3. Identify the exact process holding the orphan TASK-113 path, terminate only that stale process if safe, and remove the directory. 4. Determine whether Pi reload can be invoked from the current tool boundary; activate it if supported, otherwise leave the exact single interactive command. 5. Verify doctor, filesystem, notifier configuration, main/runtime parity, and preserved user/recovery data; merge and close.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Backlog doctor assigned TASK-204 to the local-remote-database task and verified no duplicate IDs remain. TASK-99's live note now references TASK-204; TASK-108 correctly stays TASK-111 (board sorting); TASK-69 retains a literal historical branch name. The legacy wave-plan has no document id/frontmatter, so Backlog CLI cannot update it; TASK-204 now records that explicit historical exception.

Removed the empty orphan TASK-113 directory after elevation terminated only its 13-day-old detached process tree (bash/git/git-remote-https/git-askpass/tail/conhost) identified by exact PID, process name, creation window, and parent chain. No active project/runtime process was touched.

Pi reload boundary: notifier.json is correct (agentFinished enabled; providerError/toolError disabled), and notifier.ts listens for completion on agent_settled. Pi's extension documentation states tools receive ExtensionContext and cannot call ctx.reload(); reload must enter through a command handler, and this active session exposes no reload tool. Therefore the only unavoidable handoff is for the user to enter /reload once; session_start will then reload notifier.json and the patched extension source.

Verification before merge: duplicate task IDs 0; TASK-113 directory absent and all ten stale PIDs absent; notifier JSON/event assertions passed; primary main equals local runtime; Feedback hash and every TASK-202 archive checksum passed.
<!-- SECTION:NOTES:END -->
