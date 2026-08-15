---
id: TASK-10
title: Future browser extension or bookmarklet spike
status: Done
assignee:
  - '@claude'
created_date: '2026-06-20 09:51'
updated_date: '2026-06-20 09:54'
labels:
  - P2
  - idea
  - browser-extension
  - phase-3
milestone: m-3
dependencies:
  - TASK-5
  - TASK-7
priority: low
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Explore a faster way to save jobs from external job boards after core beta feedback is collected.
<!-- SECTION:DESCRIPTION:END -->

## Spike outcome (2026-08-15)

RECOMMENDATION: bookmarklet first. It is roughly an afternoon against several days, needs no store
review, and the app already exposes the endpoint it would post to. Revisit an extension only if the
bookmarklet proves that auto-extracting fields is worth real effort.

### Effort comparison

| | Bookmarklet | Browser extension |
|---|---|---|
| Build | One `javascript:` URL, no toolchain | manifest v3, background/content scripts, bundling |
| Install | Drag to bookmarks bar | Store submission and review, or permanent developer mode |
| Updates | Re-drag the link; users silently keep old versions | Auto-update through the store |
| Browser support | Every desktop browser; unusable on mobile Safari/Chrome | Per-browser manifests, Chrome and Firefox differ |
| Page access | Only what runs at click time, same-origin rules apply | Content scripts, persistent DOM access per site |
| Auth to dachapply | Session cookie if the tab is same-site, otherwise invite code | Same, plus it can hold a stored token |
| Cross-origin POST | Needs CORS/CSRF handling from the job board's origin | Background script sidesteps page CORS |
| Realistic effort | Hours | Days, plus ongoing store maintenance |

The decisive asymmetry is maintenance, not build cost: an extension must be kept alive against
manifest changes and store policy, indefinitely, for a single user.

### Minimum viable save-job workflow

The endpoint already exists: `POST /api/public/submit/` (`jobradar/urls.py`, `views.public_submit`).
It accepts an authenticated session, or an `invite_code` when anonymous, so a bookmarklet needs no
new backend surface.

1. User is on a job posting and clicks the bookmarklet.
2. It captures `window.location.href`, `document.title`, and the selected text if any.
3. It opens `/public-submit?url=...&title=...` in a new tab rather than POSTing cross-origin. This
   sidesteps CORS and CSRF entirely, and keeps the user in a page where they can review before
   saving - which matters because auto-scraped titles are frequently wrong.
4. The existing public-submit form pre-fills from those query parameters; the user confirms.

Deliberately NOT in scope: parsing salary, location or description from arbitrary job boards. Every
board differs, the parsers rot, and TASK-6's import flow already covers structured bulk entry.
URL plus title is the 90% case for "save this before I lose the tab".

The only frontend work is reading `url` and `title` query parameters on the public-submit route.
No backend change.

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Compare bookmarklet vs browser extension effort
- [x] #2 Document minimum viable save-job workflow
- [x] #3 No implementation until higher-priority beta tasks are done
<!-- AC:END -->
