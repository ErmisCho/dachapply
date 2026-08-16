# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Offer, accepted and withdrawn statuses, so the end of the funnel is representable.
- Interview date and note per job, with an "Upcoming interviews" dashboard panel, soonest first.
- Apply-by deadlines, with badges that distinguish a passed deadline from an approaching one.
- Stale marking for new/reviewed/to-apply leads left untouched past a documented threshold.
- Board sorting by fit score, newest and feedback due, plus a work-mode filter.
- Funnel conversion and per-source effectiveness panels on the dashboard.
- Follow-ups can be created from a job's detail page; the "Due follow-ups" count links to the list.
- Optional daily email digest of due follow-ups and overdue feedback, with a profile toggle.
- Candidate evidence is stored per user and editable in settings, instead of one file on one machine.
- CV generation can be opened to a trusted user with a per-user capability flag; generated filenames
  derive from the requesting user's name.
- Invite codes are owned by a user and can be minted and revoked from account settings; submissions
  made with a code land on that user's board.
- Email confirmation at registration, required before friend requests and minting invite codes.
- Per-route browser tab titles.
- German throughout the public job-submission flow, including its validation, success and error states.
- Nightly database backups to private storage, with guards that refuse to upload an empty dump.
- Production error alerting, off until an alert address is configured.
- A panel options menu on every dashboard panel, so reordering and hiding a panel work by keyboard
  and by tap — previously they appeared only on mouse hover and had no other route.

### Changed

- Application pace and "applications sent" are counted from a permanent application date, so a
  rejection no longer counts as an application and an application that reached interview no longer
  disappears from the total.
- Board rows can be selected with the keyboard, and inline date edits update instantly instead of
  reloading the whole board.
- Menus and dialogs close on Escape and on an outside click, and return focus to whatever opened
  them; the analyze picker, batch source preview and match/gap popup work by tap and keyboard rather
  than hover only.
- The jobs list response is roughly half its previous size; full job text is fetched on demand.
- Navigating between pages no longer re-checks the session or flashes a loading screen.
- The public job-submission page is reachable without an account: a friend with an invite code can
  submit a job link without signing up, which is what invite codes were for.

### Fixed

- New accounts no longer inherit the previous owner's candidate profile, so evaluations are no
  longer scored against a stranger.
- Someone who submits a job for a friend no longer keeps access to that friend's later evaluations,
  notes and follow-ups.
- Password rules are now actually enforced when registering, changing a password and completing a
  reset.
- Rate limits hold at their configured value instead of being multiplied by the number of server
  processes, and completing a password reset is rate limited.
- Registering no longer reveals whether a given email address already has an account.
- Failed friend accepts, follow-up completions, clipboard copies and inline date edits report the
  error instead of failing silently.
- Form fields on the add and public-submit pages show values restored from a draft or filled in by
  the bookmarklet, instead of submitting data the user cannot see.
- Every form control has a label for screen readers, and skill match state is readable without
  relying on colour.
- Exporting your data no longer includes another person's notes, and re-importing an unmodified
  export no longer reports false conflicts.
- Deleting your account no longer deletes jobs you had submitted for someone else, nor that
  person's evaluations, notes and follow-ups on them.

### Security

- Removed three real recruiter contact addresses that had been pasted from a live job posting into
  a test fixture that never read them.
- Local `manage.py` commands now refuse to run against a `DATABASE_URL` loaded from the repo-root
  `.env` file unless `DACHAPPLY_ALLOW_PROD_DB=1` is set for that command, so a local migration
  cannot silently reach the production database. Values injected by the container or exported in a
  shell are unaffected.

## [0.1.0] — 2026-07-20

### Added

- Initial Session Orchestrator bootstrap.
