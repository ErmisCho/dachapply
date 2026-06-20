---
id: TASK-2
title: Configure password reset email
status: In Progress
assignee:
  - '@agent'
created_date: '2026-06-20 09:50'
updated_date: '2026-06-20 13:41'
labels:
  - P0
  - auth
  - email
  - ux
  - phase-1
milestone: m-1
dependencies: []
modified_files:
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: high
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Users need a safe recovery path if they forget their password.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 SMTP provider is configured through environment variables
- [x] #2 Password reset request sends an email successfully
- [ ] #3 Reset link works end-to-end on the deployed domain
- [x] #4 Email errors are logged without exposing credentials
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add branded HTML password reset email with a clear reset button and plain-text fallback.
2. Improve frontend password reset request feedback with inbox/spam guidance while preserving account-enumeration-safe wording.
3. Improve reset confirmation UX for success and invalid/expired links, including a clear login/request-new-link path.
4. Add/update tests for email content and frontend reset UI behavior.
5. Run focused backend/frontend checks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented provider-aware password reset email configuration: Brevo for Azure/production, local SMTP for real local delivery, and explicit console mode for local testing. Normalized Gmail app-password spacing before SMTP auth. Polished the password reset subject/body and verified generic error logging still avoids credentials/tokens. User confirmed local password reset email delivery works. Full backend validation before push passed: cd backend && DATABASE_URL= python -m pytest (88 passed). Deployed-domain reset-link verification remains pending for Azure.

User reports password reset through Azure URL still does not deliver after adding Brevo app-setting names. Next diagnosis should use Azure Log Stream/Kudu shell and Brevo transactional logs to determine whether Azure is running latest code, Brevo settings are loaded, the user exists in the deployed DATABASE_URL, or Brevo is rejecting SMTP due to sender/SMTP-key/IP authorization.

Azure Container App log stream shows the reset email is printed to stdout, which means the deployed revision is using Django console EmailBackend rather than Brevo SMTP. Next config fix: set EMAIL_PROVIDER=brevo in the active revision and remove/override any EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend setting, then restart/create a new revision.

Azure revision dachapply--0000022 now uses SMTP/Brevo instead of console backend, but Brevo rejects authentication with SMTPAuthenticationError 525: Unauthorized IP address. This confirms the remaining blocker is Brevo IP authorization/static outbound egress for Azure Container Apps, not Django email configuration.

Implemented user-friendly password reset improvements: branded HTML email with button and fallback link, safer/more helpful reset-request inbox/spam guidance, forgot-mode deep link support, and improved reset-confirm UI with confirm-password, success state, login CTA, and invalid/expired-link recovery actions. Validation passed: cd backend && DATABASE_URL= python -m pytest (88 passed); cd frontend && npm run build (passed).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-06-20 09:59
---
Added EMAIL_TIMEOUT config, documented SMTP env vars, and changed password reset delivery failures to log a generic user_id-only error while returning the same public response. Added tests for reset flow and failure handling. Real SMTP/domain verification remains platform-dependent.
---

created: 2026-06-20 10:26
---
Brevo SMTP test attempted locally. Django used smtp-relay.brevo.com with configured SMTP backend, but Brevo rejected authentication with SMTPAuthenticationError 525: Unauthorized IP address. Email delivery not verified yet; Brevo account/IP authorization must be fixed first.
---

created: 2026-06-20 12:06
---
Added email provider auto-selection. EMAIL_PROVIDER=auto now prefers BREVO_* credentials when present, otherwise LOCAL_* SMTP credentials, otherwise legacy EMAIL_* settings. Added .env.local-smtp.example/docs updates so local can use Gmail SMTP while Azure uses Brevo.
---
<!-- COMMENTS:END -->
