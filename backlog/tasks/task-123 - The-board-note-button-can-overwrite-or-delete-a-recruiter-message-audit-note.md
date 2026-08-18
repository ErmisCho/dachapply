---
id: TASK-123
title: The board note button can overwrite or delete a recruiter-message audit note
status: Done
assignee:
  - '@claude'
labels:
  - frontend
  - bug
  - data-loss
dependencies:
  - TASK-117
priority: high
ordinal: 123000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while scoping TASK-120. A latent sharp edge in the board's note button became a live data-loss
path when TASK-117 started writing notes automatically.

`openNoteModal` (`App.tsx`) loads a job's notes and picks one:

    const note = (notes||[]).find((n:any)=>n.note_type==='general') || (notes||[])[0]

Notes come back newest-first (`ApplicationNote.Meta.ordering = ['-created_at']`). So when a job has
**no** `general` note, the modal silently adopts whatever the newest note happens to be. Then
`saveNoteModal` does one of two things to it:

    PATCH /notes/{id}/  {note: text, note_type:'general'}     // if there is text
    DELETE /notes/{id}/                                        // if the box was cleared

Before TASK-117 this was mostly harmless — notes were owner-typed, and picking the newest one was a
reasonable guess. TASK-117 AC4 made `apply_suggestion` write an `ApplicationNote` with
`note_type='recruiter_message'` on **every confirmed suggestion**, naming the sender, subject and
date of the mail that moved the job. That note is the job's audit trail: it is the answer to "why
does this say rejected?".

So the sequence is now ordinary rather than exotic:

1. A rejection arrives; the owner confirms it in the Email decisions panel.
2. `apply_suggestion` writes `Applied from an email from no-reply-recruiting@broadpin.test, subject
   "Ihre Bewerbung bei Broadpin", received 18.08.2026 14:09.`
3. The owner clicks `notes` on that job's board row to jot something down.
4. The modal opens showing that audit sentence as if it were their own note. Saving rewrites it to
   `note_type:'general'`; clearing it deletes the record outright.

The audit note is destroyed by a UI that never intended to touch it, and nothing warns anyone.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The board's note button never loads, rewrites, retypes or deletes a note it did not create. Concretely: with a job whose only note is a `recruiter_message` one, opening the modal shows an empty new note, and saving creates a second note instead of mutating the first — asserted against the API, not the DOM
- [x] #2 Clearing the box deletes only a `general` note the modal itself is editing; it can never issue `DELETE /notes/{id}/` for a note of another type
- [x] #3 A note's type is never silently changed. `PATCH … {note_type:'general'}` on a row that was not already `general` is the specific defect — the type is either preserved or the row is left alone
- [x] #4 Existing behaviour for the ordinary case is unchanged: a job with a `general` note still opens it, edits in place, and deletes on clear — regression-guarded, so the fix does not turn the quick note into an append-only list by accident
- [x] #5 Any audit note already rewritten to `general` by this bug is identified and reported rather than assumed absent — the owner has confirmed suggestions in production since TASK-117 deployed, so the count may not be zero. If none are found, say so with the query that was run
- [x] #6 `npx tsc --noEmit` and `npm test` clean; the note-selection rule is a pure function in `appUtils.ts` with a test covering the no-general-note case, since that is the branch that failed
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The one-line reading of the fix is to drop the `|| (notes||[])[0]` fallback, so the modal only ever
edits a genuine `general` note and otherwise creates one. That is almost certainly right, and it is
worth checking what the fallback was for before deleting it: it predates typed notes being written
by anything other than a human, so it most likely existed so that a note created before `note_type`
mattered would still open.

AC5 needs a real query against production data, not a shrug. `ApplicationNote` rows with
`note_type='general'` whose text matches the `Applied from an email from …` shape that
`apply_suggestion` writes are the candidates — that sentence is a fixed template, which makes them
findable. Do not mass-edit anything; report the count and let the owner decide.

Related: TASK-120 puts these notes on screen beside the email history, which makes both the value of
the audit note and the severity of losing it obvious. Landing this first is the safer order.
<!-- SECTION:NOTES:END -->

## Outcome (2026-08-18)

`selectGeneralNote` (pure, in `appUtils.ts`, with a test for the no-general-note branch) replaces
`notes.find(n => n.note_type === 'general') || notes[0]`. `saveNoteModal` needed no change: with
`noteId` only ever set from a genuine `general` note, its existing PATCH/DELETE can no longer reach
an audit note.

MEASURED against the API, on a job whose ONLY note was a `recruiter_message` audit note:

- **AC1** — the modal opened **empty** (`textareaIsEmpty: true`), and saving created a **second**
  note: `[{id:2, general, "My own note about Broadpin"}, {id:1, recruiter_message, "Applied from an
  email from no-reply-recruiting@..."}]`. The audit note survived with its type intact.
- **AC4** — reopening on the same job then loaded the `general` note, and editing it kept the count
  at 2 and changed row `id:2` in place. The ordinary path is unregressed.

**AC5, run against the production database** (read-only count, `DACHAPPLY_ALLOW_PROD_DB=1`):

    ApplicationNote.objects.filter(note__startswith='Applied from an email from ')
      total notes: 15
      audit-shaped notes: 0
      audit text but note_type='general': 0

**Zero damaged notes.** TASK-117 reached production only hours earlier and no suggestion had been
confirmed there yet, so the bug was found before it destroyed anything. Reported with the query
rather than assumed.

`npx tsc --noEmit` clean, 52 frontend tests.
