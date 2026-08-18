---
id: TASK-114
title: Never draft a reply to a job-board newsletter
status: Done
assignee:
  - '@claude'
labels:
  - bug
  - email
  - backend
  - local-mode
dependencies:
  - TASK-110
priority: high
ordinal: 115000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The mailbox loop drafted polite follow-up replies to **marketing mail from job boards**, and each
draft named a real, unrelated job the owner had applied to. Two observed cases from the owner's live
mailbox:

**XING Premium discount ad → draft about a Broadpin/PROMATIS application**

    From:     XING <info@e-mail.xing.com>   Reply-To: no-reply@e-mail.xing.com
    Subject:  Stay visible diesen Sommer!            ("60 % auf Premium", "Nur noch heute")
    Draft →   "Vielen Dank für die Rückmeldung zu meiner Bewerbung für ERP Consultant -
               Oracle / Finance / Controlling bei Broadpin powered by PROMATIS. ..."

**devjobs.at job-alert blast → draft about a Formunauts application**

    From:     devjobs.at Wunschjob <wunschjob@devjobs.at>
    Subject:  Wir haben den perfekten Job für dich gefunden! 👨‍💻
    Draft →   "Vielen Dank für die Rückmeldung zu meiner Bewerbung für Senior Back End Developer
               Python bei Formunauts. ..."

Neither sender ever wrote to the owner about an application. Both drafts sat in the real Gmail
Drafts folder, threaded onto an advertisement, one keystroke from being sent to a marketing address.

### Root cause — two independent defects, both silent

**1. A tracked job's URL is usually a job *board* listing, not the employer's domain.**
`owned_job_domains()` (mailbox.py:551) maps `urlsplit(job.url).netloc` → JobLead. A lead saved from
`xing.com/jobs/...` or `devjobs.at/jobs/...` therefore registers **the board itself** as "a company I
am in conversation with". `match_job()` (mailbox.py:567) then matches `e-mail.xing.com` to `xing.com`
via its own suffix rule, and `wunschjob@devjobs.at` exactly. The board is not the employer, so this
match is a category error, not a near miss — and it silently attaches an arbitrary one of the
owner's jobs (first-wins in the dict) to every mail the board sends.

**2. `domain_known` alone promotes anything to `recruiter_reply`.**
`_classify_heuristic()` (mailbox.py:465) ends with
`if _hit(lower, RECRUITER_KEYWORDS) or domain_known: return 'recruiter_reply' if domain_known ...`.
So once (1) has matched, an advertisement with no recruiter keywords anywhere in it is classified
`recruiter_reply`, which is in `_DRAFT_WORTHY_CLASSIFICATIONS`, which gets
`_template_polite_follow_up` written to Gmail. The bulk-mail markers that both examples carry
(`List-Unsubscribe`, `Reply-To: no-reply@`, "Benachrichtigungen abbestellen" / "Unsubscribe") are
never looked at — `ImapTransport.fetch_new` does not even request those headers, and
`GmailApiTransport` fetches the full raw message and then ignores them.

The guardrails could not have caught this: they check the draft's *text* for a salary floor and
do-not-disclose phrases (mailbox.py:987). A polite German follow-up to the wrong recipient is
textually perfect. This is a **targeting** failure, and nothing in the pipeline checks targeting.

Related to TASK-110's cold-start incident (112 unwanted drafts) but distinct: that one drafted onto
*real, dead* application threads and was bounded by suppressing the cold start. This one drafts onto
threads that were never applications at all, and will keep happening on every incremental run.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A message carrying bulk/automated-mail markers is never draft-worthy, whatever its classification: at minimum `List-Unsubscribe`, `Precedence: bulk/list/junk`, `Auto-Submitted` other than `no`, and a `From`/`Reply-To` of the `no-reply@`/`noreply@`/`donotreply@` shape. Both transports must actually carry those headers — `ImapTransport.fetch_new` currently requests only FROM/SUBJECT/DATE/MESSAGE-ID/REFERENCES
- [x] #2 A job-board domain never establishes `domain_known` or a `matched_job`: leads whose URL host is a board (xing.com, devjobs.at, linkedin.com, indeed.*, stepstone.*, karriere.at, monster.*, glassdoor.*, jobs.ch, willhaben.at, …) are excluded from `owned_job_domains()`, so board mail is judged on its own content like any other sender
- [x] #3 The two real messages in the description, as fixtures, produce **no** draft — asserted against the fake transport's `appended_drafts` staying empty, not merely against a changed classification
- [x] #4 A genuine recruiter reply from a tracked employer domain still drafts exactly as before (regression guard, so #1/#2 cannot become a silent off switch for the whole feature — the same failure mode TASK-110's `test_run_after_cold_start_drafts_normally` exists to prevent)
- [x] #5 Suppression is visible, not silent: a message skipped for bulk markers is still recorded and classified, and the run digest / `check_mailbox` output says how many drafts were withheld and why, so "0 drafts" is never unexplained (same rule TASK-110 applied to `drafting_skipped`)
- [x] #6 The already-written bad drafts are removed from the owner's Gmail Drafts folder, and the count removed is reported. Deletion is scoped to drafts this app created (`MailboxDraft` rows with `status='written'` whose message came from a bulk/board sender) — never a blanket Drafts wipe
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC1 is the higher-leverage half and should land first: it fixes the class (any marketing mail from
any sender), where AC2 fixes the instance (these particular boards). Both are wanted — a board can
send non-bulk mail, and a non-board can send bulk mail — but if only one ships, ship AC1.

AC1 belongs in `maybe_draft_reply()` or in the classifier's return, **not** at the call site in
`run_check()` — the drafting decision has one entry point today and it should stay that way.

AC6 needs `users.drafts.delete` (Gmail API) or an IMAP STORE `\Deleted` + EXPUNGE on the Drafts
folder. Note the module's standing guarantee is about *sending*, not deleting — adding delete does
not weaken "this app never sends mail", but the docstring at mailbox.py:1 should say so explicitly
rather than leave a reader to infer it. `MailboxDraft` does not currently store the Gmail draft id
returned by `users.drafts.create`, so either persist it going forward or match on
thread id + subject for the existing rows.
<!-- SECTION:NOTES:END -->

## Outcome (2026-08-18)

Shipped in `backend/jobradar/services/mailbox.py`:

- `bulk_mail_reason(raw)` — the pipeline's first **targeting** check. `List-Unsubscribe`,
  `Precedence: bulk/list/junk`, `Auto-Submitted` != `no` (RFC 3834), or a no-reply `From`/`Reply-To`
  means no draft. Called at the top of `maybe_draft_reply()`, before generation, so it is one gate on
  the one entry point rather than a condition at the call site.
- `RawMessage` carries those four headers; `ImapTransport.fetch_new` now asks for
  `REPLY-TO LIST-UNSUBSCRIBE PRECEDENCE AUTO-SUBMITTED` (it previously requested five headers and
  none of them could have caught this), and the Gmail path reads them off the raw message it was
  already fetching. One `_bulk_headers(parsed)` helper serves both.
- `JOB_BOARD_DOMAINS` + `is_job_board()`; `owned_job_domains()` skips board hosts, so a lead saved
  off xing.com or devjobs.at contributes no domain and the board's mail is judged on its own content.
- `purge_app_drafts(transport, dry_run)` + `manage.py purge_app_drafts [--yes]`, and
  `GmailApiTransport.list_drafts/delete_draft`.

MEASURED: 444 backend tests pass (117 in `test_mailbox.py`, 14 of them new). Both real messages, as
fixtures, produce an empty `appended_drafts`; a genuine `hr@acme.test` recruiter reply still drafts
(`draft_written_count == 1`), which is the guard against the fix becoming an off switch.

AC5 needed no new surface: a refused draft is a `MailboxDraft` row with `status='blocked'` and its
reason, so it already counts into `run.draft_blocked_count`, prints in `check_mailbox`'s summary line
and shows in the `/mailbox` digest — the same path TASK-110's guardrail blocks use.

AC6, run live against the owner's real mailbox: **112 drafts deleted**, and a re-run reports
"No drafts in Gmail match anything this app recorded writing." Identification is exact body text
against the `MailboxDraft` log, not a template signature — Gmail's `drafts.delete` is permanent with
no Trash, so a hand-written draft must be unmatchable by construction. The deleted list is
overwhelmingly XING/devjobs marketing ("Nur bis morgen: Bis zu 60 % Rabatt auf Premium",
"Du warst schon so nah dran, Ermis"), which is the same defect this task describes, at scale.

Two things worth keeping visible:

- The 112 came from TASK-110's cold-start incident and were *already known unwanted*; deleting them
  was the owner's call, taken explicitly. This task's own defect and that one produced the same
  drafts because a first run over the whole mailbox is mostly newsletters.
- `purge_app_drafts` is OAuth-only (`ponytail:` note in the command). IMAP draft deletion
  (`STORE \Deleted` + `EXPUNGE`) is not implemented because the owner's account runs on OAuth.
