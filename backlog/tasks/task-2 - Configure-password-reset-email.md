---
id: TASK-2
title: Configure password reset email
status: In Progress
assignee:
  - '@agent'
created_date: '2026-06-20 09:50'
updated_date: '2026-06-20 12:40'
labels:
  - P0
  - auth
  - email
  - ux
  - phase-1
milestone: m-1
dependencies: []
modified_files:
  - backend/config/settings.py
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
  - backend/jobradar/tests/test_settings.py
  - .env.example
  - .env.azure.example
  - .env.local.example
  - .env.local-neon.example
  - .env.local-one-server.example
  - .env.local-smtp.example
  - docs/email-setup.md
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
1. Confirm active email settings and SMTP provider selection in development.
2. Normalize pasted Gmail App Passwords by removing Google grouping spaces before SMTP authentication.
3. Add an explicit local console-email provider so development password resets can work without valid external SMTP credentials.
4. Update email docs/templates and run focused settings/password-reset tests.
5. Report that real Gmail delivery still requires a fresh valid Gmail App Password, while local reset links now print to the Django terminal.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented provider-aware password reset email configuration: Brevo for Azure/production, local SMTP for real local delivery, and explicit console mode for local testing. Normalized Gmail app-password spacing before SMTP auth. Polished the password reset subject/body and verified generic error logging still avoids credentials/tokens. User confirmed local password reset email delivery works. Full backend validation before push passed: cd backend && DATABASE_URL= python -m pytest (88 passed). Deployed-domain reset-link verification remains pending for Azure.
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
