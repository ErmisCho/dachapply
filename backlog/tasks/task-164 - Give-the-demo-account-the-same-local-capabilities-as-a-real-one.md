---
id: TASK-164
title: Give the demo account the same local capabilities as a real one
status: In Progress
assignee:
  - '@pi'
created_date: ''
updated_date: '2026-08-28 13:00'
labels:
  - backend
  - demo
  - multi-user
  - security
dependencies:
  - TASK-151
priority: medium
ordinal: 164000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner instruction, 2026-08-21: *"the demo account should also be able to have the same local
capabilities as a normal account."*

Today `demo@dachapply.com` (created by `services.demo_data.ensure_demo_user`, signed in through the
shortcut at `views.py:388`) can browse the board but cannot reach the mailbox or CV subsystems,
because both gates require staff:

    is_mailbox_owner(user)   authenticated AND user.is_staff        (TASK-151)
    is_cv_owner(user)        staff AND settings.CODEX_CV_ENABLED    (DEBUG-only by deployment)

So every mailbox endpoint — the panel, manual run, unmatched list, attach, draft chat — 404s for the
demo user, and the demo experience silently omits the half of the product those endpoints drive.

**The hard constraint, and the reason this is not a one-line flag change.** The mailbox subsystem is
not multi-tenant in the way the board is. `MailboxMessage` rows are the OWNER's real Gmail —
TASK-117 widened the table to store message bodies, TASK-132 added the owner's own sent mail, and
TASK-136 widened the fetch beyond the inbox. Granting the demo account `is_mailbox_owner` as it
stands would expose the owner's real correspondence, including third-party recruiters' names and
addresses, to anyone who clicks "demo" on a public deployment. That is a privacy incident, not a
feature.

Therefore "the same capabilities" must mean *the same capabilities over demo data*: the demo user
sees a demo mailbox, demo conversations and demo suggestions, generated the same way
`ensure_demo_user` already generates demo job leads. Whether CV generation is included is a separate
question, because it additionally depends on `CODEX_CV_ENABLED` and a LaTeX toolchain that is not in
the container at all (see TASK-99) — hence AC6 below.

## Coordinator resolution of AC6, 2026-08-24 — decided BEFORE dispatch, not after

AC6 deliberately allows either branch as long as the answer is not left ambiguous. It is resolved
here so no agent has to guess and no implementation can drift into it:

**CV generation is EXCLUDED from the demo account.** The reason is not policy, it is that the
capability does not exist where the demo runs: the deployed container has no `pdflatex`, and
`CODEX_CV_ENABLED` defaults to DEBUG-only by design (`settings.py:126`). Demonstrating CV generation
to a demo user on the public deployment is not something an application change can achieve.

The filed task AC6 requires is **TASK-99b**, created on 2026-08-24 when TASK-99 was split. It is
blocked on the infrastructure decision — where a LaTeX toolchain lives — which the owner has not
made, and one of its legitimate outcomes is "keep generation local and say so honestly".

An implementation that includes CV generation for the demo account **fails** this criterion; it is
out of scope, not extra credit.

### Owner decision, 2026-08-24 — supersedes the paragraph above

The owner asked whether demo generation could use their own profile, so they could show it during
interviews. Answer given, and the reasoning matters more than the verdict:

- `demo@dachapply.com` is what **anyone** clicking "Try demo" on the public deployment signs into. A
  demo profile sourced from the owner's account would publish their real name, photograph, employment
  history and `Ermis-Chorinopoulos-Candidate-Evidence.md` to any visitor. That is the same privacy
  incident this task's Description already refuses for the mailbox, reached by a different route.
- It would not work anyway: the container has no `pdflatex`, so a demo-account generation produces
  nothing on the deployed site regardless of whose data backs it.
- For the owner's actual goal — demonstrating the product in an interview — signing in as themselves
  on their own machine already works today and needs nothing built.

**Chosen: the demo account gets a complete, realistic, clearly FICTIONAL candidate profile.** It
demonstrates the capability identically, is safe to expose publicly, and reads better in an interview
than showing a stranger real personal data.

Consequence for AC6, which the paragraph above got wrong: demo CV **data** is now IN scope as
fictional `CvAsset` rows (the per-user model TASK-99a introduces), while server-side **generation**
stays out and remains TASK-99b's blocked question. So AC6 is satisfied by: fictional templates and a
fictional photograph seeded for the demo user by `ensure_demo_user`, and a recorded statement that
generation itself does not run where the demo is deployed.

Under no circumstances may the demo profile read from `CODEX_CV_WORKSPACE`, the owner's `CvAsset`
rows, or the owner's candidate-evidence file. A test should fail if it does.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Signed in as the demo account, the mailbox panel, the unmatched list and the attach action all work rather than 404 — verified in a browser, naming each endpoint exercised
- [x] #2 The demo account can see NO row of the owner's real mail. Proven by a test that seeds an owner message and asserts the demo user's every mailbox endpoint returns zero rows referencing it — asserted on response content, not on a permission flag
- [x] #3 Demo mailbox content is generated for the demo user the same way its job leads already are (`ensure_demo_user`), is clearly synthetic, and contains no real third-party names or addresses
- [x] #4 Nothing the demo account does can reach a real mail transport: no Gmail API call, no draft written to the owner's Gmail Drafts, no manual run against real credentials — verified by test, since a live call would otherwise only show up as a production surprise
- [x] #5 The demo account remains non-staff; capability comes from an explicit demo-scoped rule rather than from granting `is_staff`, so no future `is_staff` check anywhere silently widens for it
- [x] #6 CV generation is either included and demonstrated, or explicitly excluded with the reason recorded here and its own filed task — it depends on `CODEX_CV_ENABLED` and a LaTeX toolchain absent from the container (TASK-99), so it must not be left ambiguous
- [x] #7 The owner's own experience is unchanged — their mailbox endpoints behave exactly as before, verified by the existing suite plus one live check
- [x] #8 Backend suite green; frontend typecheck and tests green
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Trace every mailbox endpoint and data ownership boundary. 2. Seed clearly fictional demo mailbox/CV assets scoped only to the non-staff demo user and prevent all real Gmail transport. 3. Verify mailbox panel, unmatched, attach, privacy isolation, owner behavior, and full gates.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Filed 2026-08-21 alongside TASK-163 on the owner's instruction ("file both, build the mail-relevance
one first"), so this one is deliberately not started yet.

The scoping assumption stated to the owner and not contradicted: the demo account gets demo mailbox
data, never the owner's. If the intent was instead a read-only view of the owner's real mail, that is
a materially different task with a privacy decision attached and should be re-filed rather than
folded in here.

Wave 3: demo login now seeds three synthetic mailbox messages, one suggestion, fictional candidate evidence, CV/letter templates and a placeholder photo. Demo mailbox queries are prefix-scoped; non-demo mailbox queries exclude demo rows. Demo run/reply/AI/calendar paths short-circuit before Gmail, Google Calendar, or Codex. Privacy tests seed owner message/suggestion/draft content and exercise run, status, suggestion, unmatched, message, attach, reply, job-mailbox, draft edit/chat and decision endpoints without disclosure.

Wave 4 verification: browser exercised /api/mailbox-suggestions/, /api/mailbox-runs/, /api/mailbox-runs/status/, /api/mailbox-runs/local-ai-review/, /api/mailbox-messages/unmatched/ and POST /api/mailbox-messages/{id}/attach/; the unmatched row disappeared after attach. Owner live HTTP checks returned 200 for runs/status/unmatched with zero synthetic markers. Demo rows use reserved UIDs 2000000000-2000000002 while the real resume marker remains 1173; real health/history/cold-start queries exclude demo rows. Full gates: 1014 backend and 187 frontend tests, production build, 0 npm audit findings. Asian Dad: PERFECT.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added an isolated fictional mailbox and fictional per-user CV assets to the non-staff public demo, with every real transport short-circuited and all owner mail/history/resume markers excluded. Browser, privacy/transport tests, live owner checks, and full backend/frontend gates passed; server generation remains honestly local-only under TASK-99B.
<!-- SECTION:FINAL_SUMMARY:END -->
