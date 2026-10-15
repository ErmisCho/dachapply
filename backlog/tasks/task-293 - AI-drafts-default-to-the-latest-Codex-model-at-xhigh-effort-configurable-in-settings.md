---
id: TASK-293
title: >-
  AI drafts default to the latest Codex model at xhigh effort, configurable in
  settings
status: Done
assignee: []
created_date: '2026-10-14 09:02'
updated_date: '2026-10-15 09:58'
labels: []
dependencies: []
ordinal: 294000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-14): AI email drafts (reply drafts and follow-up drafts) should be created with the latest Codex model and xhigh reasoning by default, with the default model and effort configurable somewhere (profile settings).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Profile settings has a 'Draft model' and 'Draft effort' choice fed by the dynamic model list (TASK on model discovery); default = newest Codex model and xhigh where supported
- [x] #2 Reply drafts written during the mailbox check and follow-up drafts use that default unless changed in the popup
- [x] #3 If the configured model disappears, the newest available one is used and the setting says so
- [x] #4 Tests cover the default resolution and the fallback
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-15: #255, #257, #261. Settings > Drafts shows Default newest Codex (GPT-6.1-Sol) @ xhigh; follow-up draft generated with it; checkbox layout fixed. Not yet done in the browser: change the setting and regenerate (needs owner OK to change a setting).

2026-10-15: Settings -> GPT-6-Luna@high saved, the next follow-up draft used gpt-6-luna@high, then reset to default (gpt-6.1-sol@xhigh).
<!-- SECTION:NOTES:END -->
