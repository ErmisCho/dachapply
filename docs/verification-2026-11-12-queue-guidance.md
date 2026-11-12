# Queue guidance and test-email isolation — 2026-11-12

## Scope

- TASK-374 carries the screenshot fix originally tracked as uncommitted TASK-373 in the original checkout. Work was isolated with owner approval; that checkout and its session lock were not modified.
- TASK-364 isolates inherited owner alert recipients in test settings only.
- No production deployment, owner text edits, paid model calls or default-model changes.

## Measured checks

- Pre-fix queue regressions: **14 backend failures / 6 passes**, and **1 frontend failure / 30 passes**, for the intended missing flag/action mismatch.
- Initial focused backend suites: **101 passed**. Frontend: **521 passed**, production build/typecheck passed.
- Visible Chrome against disposable SQLite/workspace and the built frontend: active cloud fit and cloud requirements rows expose **zero** cloud-retry buttons; the local-capable fit row exposes **one**.
- Both Choose job text links reached the existing chooser and focused its section. Measured section top: **380 px** in both flows. Accepted and fetched texts remained unchanged until the explicit choice; both Keep current and Use fetched saved exactly the selected text. **Zero browser exceptions**.
- Browser testing caught async CV-panel expansion moving the target below the viewport. A resize observer maintains the anchor only while the target retains focus; it stops interfering once the user chooses/edits elsewhere.
- Inherited-email reproduction with safe fixture address: the existing digest-send test failed before isolation. Test settings now default ADMINS to empty; explicit alert-test recipients and production settings remain unchanged.
- First full suite: **2 failed / 2,138 passed**. One was a real idle-poll query regression (three instead of two); fixed by reading the account fallback only for an active unregistered analysis. The other was a Windows process-kill timing failure; unchanged test passed in the independent worktree, and an owned subprocess kill completed in **0.85 s**.
- After that correction: **56 focused tests passed**, including the two-query poll, analysis lanes/time limits, inherited-email digest test and all error-alerting tests.
- Read-only Codex review: no actionable findings for the queue/email diff; reviewer independently ran all **31 queue frontend tests** but disclosed backend/browser checks were not independently verified.

## Verification boundaries

The browser exercised the actual frontend, Django routes and explicit text-saving paths. Its provider/model choices and background preparation were fixture-controlled. Existing backend integration tests exercise both choices through real preparation with a fake generator. Raw private screenshots/logs remain outside git in the system temporary directory.

Final full-suite and CI results are pending; this document does not claim either task complete yet.
