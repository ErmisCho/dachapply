---
id: TASK-354
title: Stop every request downloading the whole profile
status: Done
assignee: []
created_date: '2026-11-06 14:30'
labels:
  - performance
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner approved after measurement on 2026-11-06: Neon network transfer reached 81% of 5 GB by the 6th. The profile row is about 186 KB, 176 KB of it learned_application_preferences. 761 of 779 requests loaded the whole row, and 537 of those were the navbar queue poll, which runs every 30 s per open tab, hidden or not.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Polled and per-request paths (queue, active, CV task status, stats, board list, auth) read no large profile text column: learned_application_preferences, candidate_profile, candidate_evidence and the prompt templates.
- [x] #2 A queue poll reads at least 90% fewer bytes from the database than before, with a 176 KB preference seeded.
- [x] #3 Features that need the large fields still get them whole: the Profile page reads and saves them, generation and prompts receive them, and adding a learned preference loses nothing.
- [x] #4 A tab that is hidden stops polling the queue, and it refreshes promptly when shown again.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Queue poll: 199,498 bytes read before, 592 after, on a seeded 176 KB preference. The profile tests also pass on a real Postgres 18 container, including the select_for_update path. Hidden tab measured in a real browser with the app's own visibility handler: 0 queue requests in 80 s hidden, 1 on showing it, against one every 30 s when visible. The hidden state was signalled by overriding document.hidden, because Chrome keeps automated tabs visible.
<!-- SECTION:NOTES:END -->
