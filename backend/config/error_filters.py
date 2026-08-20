"""TASK-157: what an error email is allowed to say about this deployment.

Django's `AdminEmailHandler` attaches a full settings dump to every 500 alert, and
`SafeExceptionReporterFilter` decides what to mask by matching the setting's NAME against
`API|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE`. That covers `SECRET_KEY`,
`EMAIL_HOST_PASSWORD`, `GMAIL_OAUTH_CLIENT_SECRET` and the nested
`DATABASES['default']['PASSWORD']` -- and it does NOT cover `DATABASE_URL`, whose value is the
entire production Neon connection string, password included.

Measured, not theorised: the 2026-08-20 21:28 Europe/Vienna alert (the deliberate 500 raised to
close TASK-88 AC2) was delivered with that connection string in plain text, having crossed a
third-party mail provider on the way to the owner's mailbox.

The extra names below are an EXPLICIT list rather than a wider regex guess, because the failure
being fixed is precisely "we assumed the default pattern covered it". Each entry is here for a
stated reason:

    DATABASE_URL            the observed leak: user, password, host, database in one string
    GMAIL_CALENDAR_ICS_URL  a calendar "secret address" -- read access to that calendar for anyone
                            holding it, no authentication (TASK-115 masked it in the API for the
                            same reason; TASK-116 removes the setting, this outlives that)
    MAILBOX_DO_NOT_DISCLOSE strings the owner has explicitly designated as not-to-be-disclosed;
                            mailing them in an error report is the literal opposite
    MAILBOX_SALARY_FLOOR    the owner's negotiating floor -- not a credential, but not something an
                            error report should carry either
    EMAIL_HOST_USER         the SMTP login identity whose password is already masked; publishing
                            half a credential pair is still publishing half a credential pair
    GMAIL_IMAP_USER         the mailbox address the app reads

Deliberately NOT masked, each checked: `ADMINS`, `SERVER_EMAIL`, `DEFAULT_FROM_EMAIL`,
`CODEX_CV_OWNER_EMAIL` and `FEEDBACK_URL` all carry the owner's own address -- which is the
RECIPIENT of this email, so masking them hides nothing from anyone who can already read it, and
their presence helps diagnose a misrouted alert. `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`,
`FRONTEND_URL` and the `CODEX_CV_*` paths are public or local-only and carry no secret.

The settings dump itself is kept: it is a large part of what made the TASK-88 alert worth having,
and turning it off wholesale would trade a leak for blindness.
"""

import re

from django.views.debug import SafeExceptionReporterFilter

# Names whose VALUE is sensitive but whose NAME dodges Django's default pattern. Substring match,
# case-insensitive -- e.g. SALARY_FLOOR covers MAILBOX_SALARY_FLOOR_EUR.
EXTRA_HIDDEN_SETTING_NAMES = (
    'DATABASE_URL',
    'ICS_URL',
    'DO_NOT_DISCLOSE',
    'SALARY_FLOOR',
    'EMAIL_HOST_USER',
    'IMAP_USER',
)


class DachApplyExceptionReporterFilter(SafeExceptionReporterFilter):
    """SafeExceptionReporterFilter plus the names above.

    Built by EXTENDING Django's own pattern rather than replacing it, so a future Django release
    that adds a name to its default list keeps that protection here too.
    """

    hidden_settings = re.compile(
        SafeExceptionReporterFilter.hidden_settings.pattern + '|' + '|'.join(EXTRA_HIDDEN_SETTING_NAMES),
        flags=re.IGNORECASE,
    )
