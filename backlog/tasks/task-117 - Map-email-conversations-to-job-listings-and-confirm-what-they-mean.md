---
id: TASK-117
title: Map email conversations to job listings and confirm what they mean
status: Done
assignee:
  - '@claude'
labels:
  - product
  - mailbox
  - backend
  - frontend
  - privacy
dependencies:
  - TASK-109
  - TASK-110
  - TASK-114
priority: high
ordinal: 117000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The mailbox check already reads mail, classifies it, matches it to a job by sender domain, drafts a
reply and proposes a pipeline change. Every one of those things is invisible from the board. A
rejection arrives, the app knows it is a rejection, knows which job it is about, and the job still
sits at "applied" until the owner walks to `/mailbox` and looks.

Owner decision 2026-08-18: bring the email to the job, on the dashboard, and let the owner settle it
in one place — **see the mail, see what the app made of it, see the reply it drafted, and agree or
not**. Agreeing is what moves the job.

Concretely, one panel at the top of the dashboard, and one indicator on the job's own board row:

    ┌─ Email needing your decision ─────────────────────────────────┐
    │ hr@acme.test · 18.08.2026 09:12                               │
    │ "Einladung zum Gespräch"                                      │
    │ Sehr geehrter Herr Chorinopoulos, gerne möchten wir Sie …     │
    │                                                               │
    │ The app read this as: an interview invitation                 │
    │ Proposed: status → Interview, interview date → 25.08. 14:00   │
    │ Drafted reply (in Gmail Drafts): "Vielen Dank für die …"      │
    │                                                               │
    │            [ Yes, apply this to Acme — Engineer ]  [ No ]     │
    └───────────────────────────────────────────────────────────────┘

`MailboxSuggestion` is already exactly this primitive — created by `build_suggestions()`, applied
**only** by `apply_suggestion()` on explicit confirmation (`services/mailbox.py:806`), never
automatically. `/mailbox` already renders it. This task does not invent a confirmation flow; it moves
that flow to where the owner already is and joins it to the job it is about.

### What is missing today, and why each gap matters

**1. The email itself is not stored, so "see the mail" is unbuildable.** `MailboxMessage` keeps
sender, subject, date and classification. The body is read off the wire, used to classify, and
dropped — stated in the model docstring (`models.py:319`), in `RawMessage.body_text`
(`mailbox.py:82`), and asserted by `test_run_check_never_stores_the_message_body`
(`test_mailbox.py:430`). Judging "is this really a rejection?" from a subject line is exactly the
kind of guess that produced TASK-114's drafts.

**2. There is no per-job route to any of it.** `MailboxMessage` and `MailboxDraft` have no viewset.
They surface only nested under `/api/mailbox-suggestions/` or inside `/api/mailbox-runs/`, which is
gated on `is_cv_owner` and is not job-scoped. A job cannot ask what mail it has.

**3. Mail from a recruiter at any other domain matches nothing at all.** `match_job()` compares the
sender domain to the job's URL host and nothing else (`mailbox.py:677`, no company-name fallback by
design). An agency, a personal Gmail address, or an employer mailing from a different domain than
the one the listing was saved from produces `matched_job = None`, no suggestion, and no trace on the
board. Silently. The panel would show the owner an empty list and imply nothing happened.

**4. The job's history never says why it moved.** `apply_suggestion` writes the payload to the job
and nothing else. Three weeks later the job says "rejected" with no record that an email said so.

### The privacy decision, recorded rather than slipped in

Storing the body reverses a choice the implementer made and hardened into a docstring and a test. It
was never an acceptance criterion — TASK-109 says "minimal metadata" nowhere; the docstring
attributes it to "task's minimal-metadata requirement" and no such requirement exists in the task.
So this is not a criterion being weakened, it is an implementation default being overturned by the
person whose mail it is. Recorded here because a reader of that test will otherwise think the
reversal was an accident.

What changes: recruiter email bodies (5000-char cap, the same cap the wire read already applies)
land in the same database the Azure deployment reads. That is a real widening, and the owner took it
knowingly on 2026-08-18, for the reason above: a classification you cannot check is a classification
you cannot trust. This repo's history with personal data (TASK-69, TASK-90) is why it is written down
instead of assumed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The received email body is persisted: `MailboxMessage` gains a body field populated by BOTH transports (IMAP and Gmail API), capped at the 5000 chars the wire read already applies. `test_run_check_never_stores_the_message_body` is REPLACED by a test asserting the body is stored and capped — not deleted — and the model docstring records that the owner reversed the minimal-metadata default on 2026-08-18 and why, so the next reader does not "fix" it back
- [x] #2 A job can be asked what mail it has: an endpoint returns, for one job, its mailbox messages (sender, subject, received_at, classification, body) with each message's draft (status, block reason, subject, body) and its pending suggestions. Scoped by the same `accessible_jobs` rule the job itself uses — verified by a test where a second user asking for someone else's job gets a 404, not a body
- [x] #3 A dashboard panel shows every pending suggestion with everything needed to decide: the email (sender, subject, date, body), the classification in plain words, what would change on the job, and the drafted reply if one exists. It renders FIRST for an owner who already has a saved panel order — the existing reducer appends unknown ids last (`App.tsx:150`), so this must be measured in a browser against a pre-seeded `dachapply_dashboard_panel_order`, not argued from the code
- [x] #4 Confirming applies the change AND leaves a trace: the existing suggestion payload is applied through `apply_suggestion` exactly as today, and an `ApplicationNote` of the existing `recruiter_message` type is written naming the sender, subject and date of the mail that caused it. Dismissing writes neither — asserted on the job row and the note count after each
- [x] #5 A job with a pending suggestion shows an indicator in its board row, in BOTH the desktop table and the mobile card, opening the same overview. It is a real `<button aria-expanded>` in the tab order with a >=44px target: click, tap and Enter open it, Escape closes it, and hover opens it as a pointer-only extra. Hover-only is a defect this repo has already filed and fixed twice (TASK-81 AC3, TASK-102) — verified by keyboard and at 360px, not by reading the JSX
- [x] #6 Mail that matched no job can be attached to one by hand from the panel, and attaching runs the same suggestion generation a domain match would — so a recruiter writing from an agency or a personal address reaches the board instead of vanishing. Verified by a test whose sender domain matches nothing, which after attaching produces the same suggestions as the domain-matched case
- [x] #7 The body widens no one's access: verified against real API responses that a user who cannot see a job cannot read its mail through any route, and that `/api/mailbox-runs/` stays owner-gated as it is today
- [x] #8 Backend tests cover the stored body, the per-job endpoint and its scoping, the note on confirm, and the manual attach path; `npx tsc --noEmit` and `npm test` are clean; no test touches a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Filed 2026-08-18 from the owner's description, after two discovery passes over the backend and the
frontend. Three of the four owner decisions in it were taken explicitly when the gaps were put to
them: store the full body (not an excerpt), include manual attach (not defer it), and write the note
on confirm.

**AC5 is where this task is most likely to go wrong.** The request was literally "a notification icon,
and when hovering over to be able to open the window". Hover as an *extra* is fine and already exists
here — `MatchGapPopup` (`App.tsx:88`) previews on hover and pins on click, with a 120 ms close grace
so the pointer can travel into the panel. Hover as the *only* route is a filed defect: TASK-102
records `hidden group-hover:flex` making the panel controls unreachable by touch and keyboard because
`display:none` takes them out of the tab order, and TASK-81 AC3 records the match-gap popup being
measured before and after. Copy `MatchGapPopup` wholesale rather than writing a ninth dismissal
pattern; `useDismiss(open, close, 'panel')` is the right kind because the popup is portalled to
`<body>` and the row is rendered twice (mobile card + desktop table), which is exactly the two
conditions `App.tsx:21` names.

**AC3's "at the top" is not the array position.** `panelOrder`'s initialiser puts saved ids first and
appends anything the saved list does not know, so a new id lands LAST for every existing user and
first only for someone with no saved order. Splicing an unknown id to index 0 is the fix; measuring
it with a pre-seeded `localStorage` value is the proof.

**Do not build a second confirmation path.** `apply_suggestion` is the only writer of a mail-driven
job change and is deliberately the only one (`mailbox.py:806`, `AC3` of TASK-109). The panel calls
`POST /api/mailbox-suggestions/{id}/confirm/`, which already applies the payload server-side; the
board just needs its `jobs` refreshed afterwards, since the response is the suggestion, not the job.
Every job mutation on the board goes through `patchJob` (TASK-95) — a raw `api('/jobs/…',{PATCH})` in
`Dashboard` is a regression of a closed task.

**AC6 needs a writable `matched_job`, which does not exist.** `MailboxMessage` is documented
append-only and no view exposes PATCH. Attaching is therefore a new explicit action rather than a
generic PATCH — keep the model's append-only guarantee true for everything except this one
owner-initiated field, and say so in the docstring, or the next reader will find the docstring lying.

**Threading is out of scope, deliberately.** Gmail's `thread_id` and the message's `References` are
transient and dropped (`mailbox.py:81`, `mailbox.py:85`), and `MailboxDraft` stores no Gmail draft id,
which is why `purge_app_drafts` has to match on body text. "Conversation" here means "the messages
whose `matched_job` is this job, newest first" — a per-job list, not a threaded exchange. Deep-linking
a draft into Gmail needs the ids persisted first and is its own task if it is ever wanted.

**File territory.** The frontend is one 264 KB `App.tsx` — the panel, the row indicator and the popup
all live in it, so they are one agent's work, not three. The backend splits cleanly: model+migration,
service, views/serializers, tests.
<!-- SECTION:NOTES:END -->

## Outcome (2026-08-18)

Built by three agents in one wave over disjoint file territories (model+service, API, frontend), then
verified by the coordinator. Backend **483 tests pass**, `npx tsc --noEmit` clean, **46 frontend
tests pass**.

**Backend.** `MailboxMessage.body_text` (migration `0036`), written in `run_check` from
`RawMessage.body_text` with the 5000-char cap re-applied at the write so the column cannot exceed it
even if a transport changes. `test_run_check_never_stores_the_message_body` was replaced by
`test_run_check_stores_the_message_body` plus a cap test, and the model docstring now records the
reversal, its reason and a "do not fix this back" note. `apply_suggestion(suggestion, user=None)`
writes one `ApplicationNote(note_type='recruiter_message')` inside the same `transaction.atomic()`;
`dismiss_suggestion` still writes nothing. `attach_message_to_job(message, job, user=None)` reuses
`build_suggestions` and re-derives `interview_at` from the stored body via the existing
`_extract_datetime` heuristic, and is idempotent on a same-job re-attach.

**API.** `GET /api/jobs/{pk}/mailbox/` rides `JobLeadViewSet.get_object()` so `accessible_jobs`
scoping is inherited rather than reimplemented; `GET /api/mailbox-messages/unmatched/` and
`POST /api/mailbox-messages/{pk}/attach/` sit on an `is_cv_owner`-gated viewset exposing those two
actions only, so the model stays append-only apart from the one owner-initiated `matched_job` write.
Re-pointing a message to a different job is refused (400) rather than done silently.

**MEASURED in a real browser**, against a throwaway sqlite database and a seeded owner — not against
production, and not argued from JSX:

- **AC3.** With `dachapply_dashboard_panel_order` pre-seeded to the nine pre-existing ids and no
  `mailbox_review` in it, the rendered DOM order begins `["Email decisions", "Total", …]`. The naive
  reducer would have appended it last; `initPanelOrder` splices an unknown id to the front.
- **AC5.** A real `Tab` keypress from the row's `notes` button lands on the indicator
  (`aria-label="Email decision needed for Acme GmbH"`); `Enter` sets `aria-expanded=true` and opens
  the portalled overview; `Escape` closes it and returns focus to the trigger. A real mouse hover
  also opens it (`:hover` matched, `aria-expanded=true`) — so hover works *and* is not the only
  route. Trigger measures 44x44 in the desktop table and 50x44 in the mobile card. Both renderings
  carry it, gated by `lg:hidden`/`hidden lg:table-cell` as the rest of the board is.
- **AC4.** Confirming the Broadpin rejection through the panel moved the job to `rejected`, cleared
  `feedback_due_date`, marked the suggestion `confirmed`, and wrote exactly one note:
  `Applied from an email from no-reply-recruiting@broadpin.test, subject "Ihre Bewerbung bei
  Broadpin", received 18.08.2026 14:09.` Dismissing the Formunauts suggestion left the job at
  `applied` with its feedback clock intact and the note count still 1.
- **AC6.** An agency message (`julia.k@personalberatung-wien.test`, matching no tracked domain) was
  attached to Formunauts from the panel; `matched_job` was set and a `feedback_clear` suggestion
  appeared — the same suggestion a domain match produces for a `recruiter_reply` on a job with a
  running feedback clock.

### One defect found by measuring, and where it went

At a 356px viewport the dashboard scrolled sideways: `documentElement.scrollWidth` 443px. Cause is
NOT this panel's markup — `.dashboard-panel-wide` sets no `grid-column`, so every wide panel is one
of two columns below 768px (measured: all ten panels 148px), and Source effectiveness's table has a
252px intrinsic width that escapes the viewport whenever column parity puts it on the right. Adding a
panel at the front flips that parity.

Fixed here only for this panel — `data-panel` on the panel wrapper plus one scoped
`@media (max-width:767px)` rule — because an email body in 148px is unreadable regardless. Re-measured
after: panel 308px, `scrollWidth` 340px against a 356px viewport, no overflow, still first. The
underlying half-width-wide-panel defect is filed as **TASK-118** rather than fixed as a drive-by,
since widening the other four wide panels changes shipped work nobody asked to change.

### Known corner cut

The attach picker lists the board's currently-loaded jobs rather than fetching every job the owner
has, so a job excluded by an active board filter is not offered as an attach target. All four seeded
jobs appeared in the verification run. Left as-is (the brief allowed a plain `<select>`); it needs a
dedicated unfiltered fetch if it ever bites.
