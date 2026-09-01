# TASK-210 feedback navigation and email-action root cause

## Symptoms

- Clicking Sponsorhive — CTO in Feedback deadlines takes roughly three seconds before locating the board row.
- The row has no adjacent email/conversation action.

## Evidence

`goToFeedbackJob()` always resets filters and awaits the full `GET /jobs/?board=1` load before it checks whether `[data-job-row="1079"]` is already mounted. The pane and board are on the same page, so this turns the common visible-row case into an unnecessary network round trip.

Read-only production measurement found Sponsorhive — CTO as job 1079 (`status=interview`, `feedback_due_date=2026-08-26`) with 0 matched mailbox messages, 0 drafts, 0 pending suggestions, 0 stored contact email addresses, 0 writes, and 0 Gmail calls. Therefore an exact email/recipient cannot honestly be invented for that row.

The existing owner-scoped `GET /jobs/{id}/mailbox/`, `JobMailboxConversationCard`, `MailboxThreadGroup`, reply controls, exact Gmail links, draft controls, and suggestion decisions already implement the requested conversation. The missing work is exposing that path from Feedback deadlines, not building another mailbox UI.

## Root causes

1. Navigation checks for the row only after an unconditional full-board reload.
2. `FeedbackDueRow` has no mailbox action even though the reusable conversation path already exists.
3. Sponsorhive has no captured email identity; only an honestly labelled account-scoped Gmail search can be offered as fallback.

## Resolution

- `locateFeedbackJob()` first scrolls a visible mounted row and only invokes the existing filter-reset/full-board reload when no visible row exists.
- Every feedback row now exposes one adjacent 44×44 accessible email button.
- Opening the button performs one owner-scoped `GET /jobs/{id}/mailbox/` and mounts the existing chat conversation card with reply, exact-Gmail, draft, and pending-decision controls.
- Feedback rows include a Gmail search URL derived from the authenticated user's email and company. Zero-message rows state that no conversation or recipient is known; they never fabricate an address.

Verification: Sponsorhive mounted navigation measured 0.5 ms with 0 jobs requests and 0 mailbox requests. Its email action measured one mailbox request, 0 jobs requests, a 44×44 button, explicit no-recipient copy, and account-scoped Gmail search. A synthetic two-message conversation rendered received/owner messages chronologically with two exact-Gmail controls, two reply controls, a Gmail draft, and a pending decision after one mailbox request. The filtered-out browser path issued exactly one reset jobs request and left the target marker. Final gates: 1,045 backend tests, 206 frontend tests, TypeScript/Vite build, Django checks, migration check, npm audit (0 vulnerabilities), diff check, and no-send/delete scan all passed.
