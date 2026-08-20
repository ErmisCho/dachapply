---
id: TASK-135
title: Show calendar invitations and attachments in the conversation
status: In Progress
assignee: []
labels:
  - backend
  - frontend
  - mailbox
priority: medium
ordinal: 135000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-08-19: *"you should be able to show in this email conversation a Google Calendar
invitation, files, etc attached to their email thread."*

The app stores a message's plain-text body and nothing else. A message whose content is an
invitation or an attachment therefore reads as empty or as boilerplate.

Measured while backfilling bodies, this is not hypothetical. Six real recruiter messages came back
with NO body at all:

    job 36 | Doris Liegenfeld <doris.liegenfeld@ontec...> | AW: Einladung zum Kennenlernen per Microsoft-Teams
    job 36 | Doris Liegenfeld <doris.liegenfeld@ontec...> | Einladung zum Kennenlernen per Microsoft-Teams
    job 36 | ONTEC AG Recruiting Team <no-reply@msg...>   | Your application at ONTEC AG

Those are interview invitations. Their content lives in a `text/calendar` part (and in attachments),
which `_body_text` does not look at, so the owner sees an empty message where a meeting invite should
be. A seventh case is already visible in the log: a Google Calendar notification for *"zooplus would
like to get to know you"*, stored, classified `not_job_related`, and attached to no job.

An interview invitation is the single most important message a job-search tool can show. Right now it
is the one it shows worst.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A message carrying a calendar invitation shows what a person needs: what, when, and with whom — verified against one of the real ONTEC AG "Einladung zum Kennenlernen per Microsoft-Teams" messages, which currently render empty
- [ ] #2 The meeting time is shown in the owner's timezone with the timezone named, because an invitation is exactly the thing that is useless if it is an hour out
- [ ] #3 A message with attachments lists them — filename, type and size — so the owner knows something is there even if the file itself is not fetched
- [ ] #4 Whether attachment CONTENT is stored is a deliberate, recorded decision, not a side effect: storing files means CVs and offer letters land in the same database as message bodies, and this repo has a filed history on that (TASK-69, TASK-90, and TASK-117's reversal). Metadata-only is a legitimate answer; silence is not
- [ ] #5 A message that is only an invitation no longer reads as empty — the six measured cases stop showing "(no body recorded)" or a blank body
- [ ] #6 Nothing is executed or rendered as markup from an attachment or invitation: filenames and calendar fields are shown as text, and a malicious filename cannot inject
- [ ] #7 Backend tests cover parsing a real-shaped `text/calendar` part and an attachment manifest; no test contacts a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`_body_text` walks for `text/plain` only. The parts that matter here are `text/calendar` (the
invitation, an iCalendar VEVENT with DTSTART/SUMMARY/ORGANIZER) and any part with a filename.

There is already an iCalendar parser in this repo — `services/calendar_ics.py` plus the
`_parse_ics_datetime`/`is_busy_at` helpers TASK-115 uses for quiet hours. Reuse them rather than
writing a second one; a VEVENT from a Teams invite is the same shape as one from a calendar feed.

AC4 is the decision that needs an owner, not an implementer. Metadata-only (name, mime type, size)
answers "is there something attached" without putting a CV or an offer letter into the database, and
"Reply in Gmail" already exists as the route to the actual file. Storing content is a bigger step
than TASK-117's body reversal and should be asked for explicitly, not inferred from "files, etc".

Note the Gmail API returns attachment metadata in the message payload's part headers without a
second call; fetching the DATA is a separate `messages.attachments.get` per part. That asymmetry is
what makes metadata-only cheap and content expensive.
<!-- SECTION:NOTES:END -->
