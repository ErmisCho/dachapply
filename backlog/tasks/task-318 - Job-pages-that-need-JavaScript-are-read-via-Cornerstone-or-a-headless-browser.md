---
id: TASK-318
title: Job pages that need JavaScript are read via Cornerstone or a headless browser
status: Done
assignee: []
created_date: '2026-10-19 17:19'
updated_date: '2026-10-19 17:51'
labels:
  - backend
dependencies: []
priority: high
ordinal: 318000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Live 2026-10-19: oebb.csod.com postings returned no readable text (JavaScript-only), blocking jobs 1845/1847. Measured: the page embeds a public token (csod.context.token) and GET /services/x/job-requisition/v2/requisitions/<id>/jobDetails?cultureId=<n> with that bearer token returns the posting (displayTitle, externalDescription). Owner chose: Cornerstone reader + headless browser fallback; if all fail, Blocked says to paste the text.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 *.csod.com requisition URLs are read through Cornerstone's jobDetails API using the page's public token; the result is the posting title and description as plain text
- [x] #2 Any other page that yields no readable text is rendered in a headless browser (installed Chrome via Playwright channel 'chrome', else a Playwright Chromium if installed, else skipped) with no visible window, a bounded timeout and at most one render at a time
- [x] #3 The headless browser keeps the SSRF guard: every request it makes (navigation, redirects, subresources) to a host the plain fetch would refuse is aborted
- [x] #4 When the posting still cannot be read, the error and the Queue's blocked reason tell the owner to paste the posting text on the job page
- [x] #5 Without Playwright or a browser (e.g. the Azure container) everything behaves as before; no new failure
- [x] #6 Tests cover the Cornerstone path, the headless fallback selection, the SSRF abort and the paste hint, each failing when its logic is removed; CI green
- [x] #7 Verified on localhost: jobs 1845 and 1847 get their posting text and their documents queue
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified on localhost 2026-10-19 (PR #304): Retry on the Queue page read oebb.csod.com requisitions 26278/26276 via Cornerstone (1231/1368 chars); both analysed and queued. Headless Chrome rendered a Workday page with no visible window (agent smoke). playwright is in the dev group, so the Azure image is unchanged.
<!-- SECTION:NOTES:END -->
