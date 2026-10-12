---
id: TASK-278
title: >-
  CV adjust: free-form literal edits apply in seconds, reliably, without full
  regeneration
status: In Progress
assignee: []
created_date: '2026-10-12 12:03'
updated_date: '2026-10-12 14:33'
labels:
  - cv
  - performance
dependencies: []
priority: high
ordinal: 274000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-10-12: 'would it be possible that the local llm can just replace in a few seconds or instantly if the format is not exactly like this? Exact OLD:/NEW: blocks and bounded from:/with: blocks skip AI; other instructions use full optimization' and 'I want that flexibility but also the replacement should be also reliable'. Today (views.py revise endpoint) only exact OLD:/NEW: and from:/with: blocks take the no-AI route (exact_revision_plan, TASK-214/215, ~200ms); any other wording runs a full model regeneration of the whole TeX. Add a middle route for literal edits written in free form: (1) common phrasings parsed deterministically, (2) otherwise an installed local model only translates the instruction into {old,new} pairs that then go through the same exact-match machinery; anything not provably literal falls back to full optimization unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Deterministic phrasings bypass every model and apply like OLD:/NEW: blocks: at least 'replace "X" with "Y"', 'change "X" to "Y"', 'X -> Y' / 'X → Y' (quoted or unquoted single line), case-insensitive keywords, several per message; server time under 1s measured on the owner's real CV
- [ ] #2 Other instructions first go to an installed local model (ollama or LM Studio) that returns only a structured list of {old,new} edits or 'not literal'; it never returns a whole document. If no local model is installed or it errors/times out, the request falls back to full optimization with no user-visible failure
- [ ] #3 Reliability gate, applied to every edit from either route before anything is written: each old matches exactly once across the selected documents; every byte outside the replaced spans is identical to the source; the edited documents compile; page limits (CV max 2 pages, letter max 1) still hold. Any failure discards ALL edits of that request (never a partial apply) and falls back to full optimization
- [ ] #4 No invented content: every word an edit adds (present in new but not in old) appears in the owner's instruction text; otherwise the edit set is rejected and the request falls back. A test shows a model proposing an unrequested word is refused
- [ ] #5 Mixed instructions (a literal edit plus a semantic one such as 'and make the summary more concise') never apply the literal part alone; the whole request goes to full optimization
- [ ] #6 The task result lists each applied edit as old -> new and states which route ran (exact, deterministic, local-model, full optimization), so the owner can see exactly what changed
- [ ] #7 A committed evaluation set of at least 25 instructions (literal phrasings, ambiguous references, semantic requests, mixed, unrequested-content traps) run against the owner's local model: zero wrong edits applied (precision 100%), and the share handled without full optimization is measured and reported, not estimated
- [ ] #8 Local-model route latency measured on the owner's machine with the installed model: median and max over the evaluation set's literal cases reported; target median 10s or less
- [ ] #9 Existing exact OLD:/NEW: and from:/with: behaviour and its tests are unchanged; backend pytest, frontend npm test and tsc pass; verified end-to-end on the owner's localhost with one deterministic and one local-model edit
- [ ] #10 With only the CV (or only the letter) ticked, OLD/NEW and from:/with: blocks found only in the unticked document are applied there (ticked document wins a block both contain); the run stays instant without AI and the report says the unticked document was updated
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Backend only (the UI already renders report.main_changes). New module services/literal_edits.py: deterministic phrase parser -> pairs; local-model translator -> pairs or not-literal; shared reliability gate (unique match via the exact_revision_plan machinery, byte-identity outside spans, no-invented-words, mixed detection). views.py revise endpoint: exact -> deterministic -> local model -> full optimization. Compile gate (compiles + page limits) runs before anything is persisted; failure discards all edits and starts the normal full-optimization task. Eval set (>=25) committed with a fixture CV; latency and coverage measured on the owner's installed local model; real CV used only locally, never committed.
<!-- SECTION:PLAN:END -->
