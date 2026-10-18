---
id: TASK-305
title: 'Fetched posting text is the job ad, not the whole careers page'
status: To Do
assignee: []
created_date: '2026-10-18 08:19'
labels:
  - backend
dependencies: []
priority: high
ordinal: 306000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-18 (PORR, job 1544): 'Use fetched' stored 6976 chars of the whole page: site menu (Jobbörse, Initiativbewerbung, Lehre ...), country picker, share buttons (Teilen auf LinkedIn/XING/WhatsApp). The Structured version then filed that menu under Benefits. fetch_posting_text (services/posting_fetch.py) flattens the whole HTML. The PORR page carries a schema.org JobPosting JSON-LD block (measured). Prefer it; fall back to the page text when absent.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 When the page has a JSON-LD JobPosting with a description, the fetched text is built from it: title, then the description in the posting's own words and headings, then pay (baseSalary) and location lines when present; no site navigation or share-button text
- [ ] #2 Pages without JobPosting JSON-LD keep today's behaviour
- [ ] #3 Test with a saved-HTML fixture shaped like the PORR page (menu + share buttons + JobPosting) proves the clutter is gone and Deine Aufgaben / Dein Profil survive; the test fails when the JSON-LD path is removed
- [ ] #4 Measured on the real PORR URL: refetched text has no 'Teilen auf' and no 'Jobbörse' lines, and the Structured version shows Responsibilities and Requirements, not menu items
<!-- AC:END -->
