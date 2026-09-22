---
id: TASK-244
title: Error text is invisible in the CV window in dark mode
status: To Do
assignee: []
created_date: '2026-09-21 17:00'
labels:
  - frontend
  - ux
  - accessibility
dependencies: []
priority: high
type: bug
ordinal: 243000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-09-21 while verifying TASK-243, and measured in a browser rather than inferred.

frontend/src/App.tsx:608 renders the compact CV generator popup with 'bg-white text-slate-900' and NO dark: variant, so in dark mode the window stays a white island while the document carries the .dark class. Every .dark rule inside it then styles content for a dark background that is not there.

Measured, ErrorBox in exactly that situation: index.css:14 sets .dark .field-error-message{color:#fecdd3}, which against the window's white gives a contrast ratio of **1.41:1**. AA wants 4.5:1. In practice an error message in that window is close to unreadable in dark mode - and errors are the messages that matter most.

This predates TASK-243 and is not caused by it. It is the reason TASK-243's status messages kept an opaque tone fill instead of going fully transparent: a message that must be legible on BOTH a white island and a dark page has to bring its own background, since no single text colour clears 4.5:1 against both. Fix the surface and that constraint disappears.

Worth checking the same pattern elsewhere while in there: any component with a hardcoded bg-white and no dark variant has the same defect waiting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 In dark mode, an error shown inside the CV generation window is legible - measured contrast at or above 4.5:1 against the surface it actually sits on, not against the surface it was designed for
- [ ] #2 The fix addresses the surface rather than the text: the window gets a dark variant like the rest of the app, instead of each message being patched to survive a white background
- [ ] #3 Every message kind in that window is re-measured after the change - error, success and info, compact and full - in both modes
- [ ] #4 Once the surface is dark in dark mode, the status-message tone fills are re-evaluated: they were kept opaque in TASK-243 only because the window is white, and the task records whether they can now go transparent
<!-- AC:END -->
