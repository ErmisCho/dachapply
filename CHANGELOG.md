# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Reply and reply-all can now be composed from the conversation itself: every message carries a
  Reply control that shows exactly who will receive the draft before it is saved, with To and Cc
  editable in place; the saved Gmail draft contains exactly what was shown.
- Mail sent through a multi-tenant ATS (Ashby, JOIN, ...) is matched to the right job by the company
  name in the sender's display name — the one place the ATS names its client — with ambiguity never
  guessed, and a dry-run-by-default `manage.py rematch_ats_display_name_messages` for mail stored
  before the rule existed.
- A conversation is now the whole thread, and it has both sides. The app fetches your own sent mail
  alongside what arrives, so a conversation shows what you wrote as well as what the company wrote,
  laid out as an email thread you can read top to bottom instead of a pile of separate messages. One
  conversation carries one draft and one decision, not one per message.
- Calendar invitations and attachments are shown inside the conversation: what the meeting is, when
  it starts and ends, where, and who organised it, plus each attachment's name, type and size.
- Replies and reply-all can be written from the app and are saved into Gmail Drafts, addressed the
  way the message you are answering implies — for a message you sent yourself, "reply" follows its
  To, and reply-all adds its Cc.
- How far back the app keeps mail is yours to set: a lookback window in months on the settings page,
  six by default. Mail is only tracked for jobs still worth acting on, so a job you have closed out
  stops generating suggestions and drafts rather than only hiding them.
- The board opens in attention order — New first, then the rest in pipeline order with closed
  statuses last — and a multi-column sort you choose is remembered between sessions.
- A feedback-deadline pane on the dashboard: the jobs you are waiting to hear back on, overdue ones
  first, each with a way to jump to the job, record that you followed up, or move the date.
- A job's email history and its notes are visible where the decision is made: every message matched
  to that job with its classification, a link that opens the conversation in Gmail, and every note
  with its type, so a note the app wrote to record why a job moved is distinguishable from one you
  typed.
- Drafted replies can be edited in the app and saved back to Gmail Drafts. The salary-floor and
  do-not-disclose guardrails run again on the edited text, so an edit cannot get past a rule the
  template itself could not.
- Email decisions on the dashboard. When a recruiter, a rejection or an interview invitation arrives,
  the board shows it first: the email itself, what the app made of it, what would change on the job,
  and the reply it drafted into Gmail Drafts. Agreeing applies the change and records on the job
  which email caused it; declining changes nothing. The job's own row carries an indicator that
  opens the same overview by click, tap, keyboard or hover.
- Mail that matches no tracked job — an agency, a personal address, an employer writing from a
  different domain than the listing — can be attached to a job by hand, and then behaves exactly as
  a matched one.
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
- The board can be sorted by status, in pipeline order, and by up to three columns at once: click a
  column header to cycle it through ascending, descending and off, and a second column is added as a
  tie-breaker rather than replacing the first. The active columns show their direction and their
  precedence. Sorting this way needs no modifier key, so it works by keyboard and by tap.
- On phones and tablets, where the sortable column headers do not exist, the sort menu now offers
  "status" and "status, then fit score", and shows which sort is active.

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

- Text inside a conversation can actually be selected and copied again. The panel's drag-to-reorder
  makes the browser mark everything inside it unselectable; the conversation card now opts back in.
- The per-job email-history popup no longer scrolls sideways: its rows now shrink to the popup's
  width instead of forcing a 640px-wide line into a 380px panel.
- The saved board sort is genuinely applied when the board loads with no explicit sort — the same
  order now appears on another device, as the settings page always claimed.
- The message-body backfill no longer reports the same attachment-only messages as "filled" on
  every run, and a new --calendar-missing mode recovers calendar invitations for messages whose
  bodies were stored before calendar support existed.
- The board renders each job once instead of twice. The desktop table and the mobile cards were both
  fully present in the DOM at every screen size with CSS hiding one — 84% of the page was the same
  jobs twice; now only the rendering that fits the screen is mounted, and selection and sort survive
  crossing the breakpoint.
- The board table scrolls sideways inside its own card again instead of stretching the whole page —
  a leftover style override was cancelling the card's scroll behaviour on both axes.
- `manage.py purge_app_drafts` recognises its own drafts again despite the leading dot mail
  transport adds to some lines (RFC 5321 dot-stuffing); a draft you edited by hand still never
  matches and is never deleted.
- The dashboard no longer freezes the machine it is opened on. The mailbox panel fetched a
  conversation for every card on mount; it now fetches once for the panel. Measured on the same
  board: the unmatched endpoint 13,006 ms to 785 ms, the panel 22,543 DOM nodes to 237, requests on
  load 11 to 3, slowest request 10,479 ms to 1,084 ms.
- Mail that never reached the inbox — filed, archived or auto-sorted away by a Gmail rule — is no
  longer invisible to the app, and `manage.py backfill_historical_mail` brings in what was missed
  before the widened fetch existed.
- The chat bubbles no longer push the page sideways, and text inside a conversation can be selected
  and copied again — the panel's drag-to-reorder was swallowing the selection.
- One email now shows as one entry in Email decisions. Previously an email that proposed two changes
  was printed twice, in full, with two identical-looking buttons that did different things. Each
  proposal keeps its own accept/decline, and there is a single action to accept them all.
- The board's note button can no longer overwrite or delete the note the app writes to record which
  email moved a job. It only ever edits a note you wrote yourself.
- The dashboard no longer scrolls sideways on a phone. Wide panels — the conversion funnel,
  application pace, source effectiveness, upcoming interviews and email decisions — are now full
  width below 768px instead of being squeezed into half a column, and the two tables that still
  cannot fit scroll inside their own panel rather than dragging the whole page with them.
- The mailbox check no longer drafts replies to job-board newsletters and automated blasts. A
  message carrying bulk markers (an unsubscribe link, `Precedence: bulk`, `Auto-Submitted`, or a
  no-reply sender) is never replied to, and a job board's own domain no longer counts as a company
  you are in conversation with. Refused drafts are counted and explained rather than skipped
  silently, and `manage.py purge_app_drafts` removes drafts this app already wrote.
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
