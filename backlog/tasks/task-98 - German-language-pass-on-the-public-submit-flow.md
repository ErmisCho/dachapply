---
id: TASK-98
title: German-language pass on the public submit flow
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 15:25'
labels:
  - frontend
  - i18n
  - ux
dependencies: []
priority: low
ordinal: 103000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The audience is Austria/Germany, but the app is hardcoded English throughout: `lang="en"` (frontend/index.html:2) and every string inline — including the entire /public-submit flow (App.tsx:107), which is exactly the page German-speaking friends without an account actually use.

Stance, decided here so it is on record: full i18n extraction is large and unwarranted for a single-owner tool — the owner-facing app intentionally stays English. Only the one public-facing flow gets German.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 /public-submit, including its validation, success, and error states, is available in German (German-first or a simple toggle)
- [x] #2 The document lang attribute matches the displayed language on that page
- [x] #3 The English-elsewhere stance is recorded in the closing notes so future i18n asks route through a new task, not silent scope growth
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Hardcoded German strings for one page (a strings object with two keys per message) beat an i18n framework — YAGNI holds until a second locale or a second page needs it.

### Closing notes (2026-08-16)

German lives in one `submitDe` object in `appUtils.ts` — no i18n framework, no locale switcher, no
extraction from any other page.

**AC3, the stance, recorded here as the task asks:** full i18n extraction stays unwarranted for a
single-owner tool. The owner-facing app is deliberately English. Only `/public-submit` is German.
A future request to translate more should open its own task rather than growing this one — the
module comment in `appUtils.ts` says the same thing so the next reader does not "finish the job".

**AC2 measured, including the case that usually breaks it** — a client-side route change rather than
a reload:

    /public-submit   documentElement.lang = "de", title "Jobangebot einreichen — DACHApply"
    then click to /  documentElement.lang = "en"
    /add             documentElement.lang = "en", h1 "Add job"

`index.html` stays `lang="en"`; the public form flips it on mount and restores it on unmount, with
`publicMode` in the dependency array because react-router reuses the same component instance for
`/public-submit -> /add`, so the cleanup would not otherwise run. Nav and footer carry `lang="en"`
so a screen reader does not read "Bookmarklet" and "Privacy" with a German voice.

**AC1 covers the states, not just the labels** — verified by driving each one:

    validation  "Bitte füge mindestens einen Job-Link oder eine Beschreibung ein."
                with zero network requests, and aria-invalid on the links textarea
    success     Gesendet / Zusammenfassung / Angelegt / "Unbekannte Firma"
                and no English leak (no "Unknown company", no "Untitled role")
    401         "Deine Sitzung ist abgelaufen. Bitte melde dich erneut an…"
    429         "Zu viele Einreichungen. Bitte versuche es in 47 Sekunden erneut."
    offline     "Keine Verbindung zum Server. Bitte prüfe deine Internetverbindung…"

The validation state is new: every field on the endpoint is optional, so an empty form previously
POSTed successfully and created a nameless "Unknown company" row.

**A defect was found in the error mapping and fixed at close.** The throttle patterns matched DRF's
*default* wording (`"Request was throttled. Expected available in N seconds."`), which this app never
sends — `jobradar/throttles.py` returns `{detail: 'Rate limit exceeded. Try again later.',
available_in_seconds: N}`, and `messageText()` passes on only `detail`, so the seconds never reached
the mapper at all. The unit test passed while asserting a string that cannot occur, and a real 429
fell through to the generic message. This matters because `/public-submit` carries a 20/hour IP
limit, so throttling is one of the likeliest errors there. The app's real message is now mapped,
`available_in_seconds` is threaded through as an argument, and a test pins the real shape.

**Context that does not change this task but must not be lost:** `/public-submit` is still behind
`RequireAuth`, so the anonymous friend this page was translated for cannot currently reach it. That
is TASK-101's decision, deliberately not made here, and the route wrapper was left untouched.
<!-- SECTION:NOTES:END -->
