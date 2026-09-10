---
id: TASK-226
title: Reach the local server from other devices on the home network
status: To Do
assignee: []
created_date: '2026-09-10 11:48'
labels:
  - backend
  - infrastructure
dependencies: []
priority: high
ordinal: 225000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request, 2026-09-10: other devices on the home network should be able to open this server.

Today they cannot. scripts/dachapply-local-runtime.cmd line 49 starts the backend as `python manage.py runserver 127.0.0.1:8000`, which binds loopback only, so nothing outside the host machine can reach it at all. Two settings would block it even after the bind is widened: ALLOWED_HOSTS defaults to `localhost,127.0.0.1,testserver` (settings.py:192) and CSRF_TRUSTED_ORIGINS to the localhost/127.0.0.1 forms (settings.py:193), so a request to `http://<lan-ip>:8000/` would be refused by host validation and a login POST would fail CSRF even if it were not.

This has a real exposure to state rather than gloss over: the local runtime runs with DEBUG=True and, unlike the deployed container, it points at the PRODUCTION database. Widening the bind puts the owner real board, real mailbox data and real CV workspace on the local network behind nothing but the Django login. Whatever is decided, the task should say what is now reachable and what is protecting it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A second physical device on the same network loads the board at http://<host-lan-ip>:8000/ and completes a login - verified from that device, not from a second browser on the host, and not inferred from a successful bind
- [ ] #2 The bind address is configurable rather than hard-coded, and loopback-only stays the default for anyone who does not opt in
- [ ] #3 ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS accept the host LAN address, evidenced by a login POST succeeding from the second device rather than by reading the settings
- [ ] #4 Any host firewall rule the change needs is written down as the exact command that creates it, and the whole setup still works after a reboot of the host
- [ ] #5 The task records what became reachable on the network and what protects it, given the local runtime runs DEBUG=True against the production database
<!-- AC:END -->
