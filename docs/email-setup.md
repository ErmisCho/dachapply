# Email setup: local vs Azure

DACHApply uses Django email settings from environment variables.

Provider-specific variables are supported. With `EMAIL_PROVIDER=auto`, the app chooses providers in this order:

1. Brevo, if `BREVO_*` credentials are filled.
2. Local SMTP, if `LOCAL_*` credentials are filled.
3. Legacy `EMAIL_*` settings/defaults.

So if both Brevo and local SMTP are configured, Brevo is used.

## Local development

There are two supported local modes.

### Option A: local console email

Use console email if you do not want to call any real SMTP provider locally:

```text
DACHAPPLY_ENV=local
DEBUG=True
FRONTEND_URL=http://127.0.0.1:8000
EMAIL_PROVIDER=console
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=DACHApply <local@dachapply.test>
```

With the console backend, password reset emails are printed in the Django backend terminal instead of being sent. `EMAIL_PROVIDER=console` forces this local mode even if old SMTP credentials remain in `.env`.

### Option B: local real SMTP email

Use this if you want local password reset emails delivered to an inbox. Gmail SMTP is easiest for local use because it does not require Brevo IP allowlisting:

```text
DACHAPPLY_ENV=local-smtp
DEBUG=True
FRONTEND_URL=http://127.0.0.1:8000
EMAIL_PROVIDER=auto
EMAIL_TIMEOUT=10
LOCAL_EMAIL_HOST=smtp.gmail.com
LOCAL_EMAIL_PORT=587
LOCAL_EMAIL_USE_TLS=True
LOCAL_EMAIL_USE_SSL=False
LOCAL_EMAIL_HOST_USER=your-gmail-address@gmail.com
LOCAL_EMAIL_HOST_PASSWORD=your-gmail-app-password-without-spaces
LOCAL_DEFAULT_FROM_EMAIL=DACHApply <your-gmail-address@gmail.com>
```

Gmail requires 2-Step Verification and a Gmail App Password; do not use your normal Google account password. Google displays app passwords in four groups with spaces, but SMTP authentication needs the compact 16-character value. The app normalizes that common pasted format, but keeping `.env` without spaces avoids confusion.

If you also fill the `BREVO_*` variables, Brevo is used instead of local SMTP. If you use Brevo SMTP locally, you must authorize your current public IP in Brevo. Home IPs can change.

To test locally:

```bash
cd backend
python manage.py runserver 127.0.0.1:8000
```

Request a password reset from the frontend, then copy the reset link from the backend terminal output.

## Azure / production

Use Brevo SMTP in Azure App Settings / Container environment variables:

```text
DACHAPPLY_ENV=azure
DEBUG=False
FRONTEND_URL=https://your-app.azurecontainerapps.io
EMAIL_PROVIDER=brevo
EMAIL_TIMEOUT=10
BREVO_EMAIL_HOST=smtp-relay.brevo.com
BREVO_EMAIL_PORT=587
BREVO_EMAIL_USE_TLS=True
BREVO_EMAIL_USE_SSL=False
BREVO_EMAIL_HOST_USER=<brevo smtp login>
BREVO_EMAIL_HOST_PASSWORD=<brevo smtp key>
BREVO_DEFAULT_FROM_EMAIL=DACHApply <verified-sender@example.com>
```

Brevo requires authorized sending IPs for SMTP keys. For Azure, add the Azure outbound IP address(es) to Brevo:

- Azure App Service: App Service > Properties > Outbound IP addresses.
- Azure Container Apps: use a static egress/NAT setup if you need stable outbound IPs.

## Owner-only mailbox check (TASK-109/TASK-110)

This is a separate feature from the password-reset email above: `manage.py check_mailbox` reads the
owner's own Gmail inbox on a schedule to surface job-search suggestions and draft guarded replies
into Gmail's Drafts folder. It never sends mail -- sending is exclusively the owner acting in Gmail
itself. Two ways to authorize it; pick whichever the owner's Google account can actually do.

### Option A: IMAP app password (needs 2-Step Verification)

```text
GMAIL_IMAP_USER=your-gmail-address@gmail.com
GMAIL_IMAP_APP_PASSWORD=your-gmail-app-password
```

Requires 2-Step Verification to be turned on for the account -- Google only issues app passwords with
2SV on, and retired "less secure app access" entirely. If 2SV is off and staying off, use Option B
instead.

### Option B: Gmail-API OAuth (works with 2-Step Verification off)

No third-party OAuth library is used -- just a refresh-token POST and plain REST+JSON calls to the
Gmail API, scoped to `https://www.googleapis.com/auth/gmail.modify` (never the much broader
`https://mail.google.com/`), which is enough to list/read messages and create drafts but not enough
to permanently delete anything or send mail.

1. **Create a Google Cloud project.** [console.cloud.google.com](https://console.cloud.google.com/) ->
   create a new project (or reuse an existing personal one).
2. **Enable the Gmail API.** In that project: APIs & Services -> Library -> search "Gmail API" ->
   Enable.
3. **Configure the OAuth consent screen.** APIs & Services -> OAuth consent screen -> User Type
   "External" -> fill in the required app name/support email -> add the `gmail.modify` scope -> under
   "Test users", add the owner's own Gmail address. Leave the app in "Testing" publishing status (see
   the expiry note below).
4. **Create an OAuth client.** APIs & Services -> Credentials -> Create Credentials -> OAuth client ID
   -> Application type **Desktop app**. Download or copy the generated client ID and client secret.
5. **Add them to `.env`:**

   ```text
   GMAIL_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GMAIL_OAUTH_CLIENT_SECRET=your-client-secret
   ```

6. **Run the one-time consent handshake:**

   ```bash
   cd backend
   python manage.py gmail_oauth_setup
   ```

   This prints a Google authorization URL. Open it, sign in with the mailbox to be checked, and
   consent. You will land on an unreachable `http://localhost/...` page afterward -- that is expected,
   nothing is meant to be listening there. Copy the `code=` value out of that page's own address bar
   and paste it back into the terminal when prompted. The command exchanges it for a refresh token and
   writes only that token to a local, gitignored file (`GMAIL_OAUTH_TOKEN_PATH`, defaulting to
   `dachapply-gmail-oauth-token.json` at the repo root) -- never printed to the terminal, never
   committed. `manage.py check_mailbox` then uses it automatically; IMAP wins if both Option A and
   Option B are configured.

**Testing-mode token expiry: re-authorize every 7 days, or publish the app to stop it.** While the
OAuth consent screen is in "Testing" publishing status, Google expires the refresh token after about 7
days of testing-mode use, regardless of whether it's actually being used. When that happens,
`check_mailbox` will fail every run with a Gmail OAuth error recorded on the `MailboxRun` it creates
(visible in the /mailbox digest, same as any other check failure) -- it does not fail silently. To
recover, just run `manage.py gmail_oauth_setup` again.

**Publishing to stop the 7-day cycle was tried on 2026-08-21 and is NOT available to this app.** The
advice this paragraph used to give -- publish the consent screen, no verification review needed for a
single-owner app -- was true about the *review* and wrong about the *button*. In the current Google
Auth Platform console (Audience page) the "Publish app" control is greyed out behind:

    "Your app's OAuth configuration is incomplete. You must enter the missing information to
     proceed. Please visit the Branding page to finish configuring your app."

Branding requires an application home page, a privacy policy URL and matching Authorised domains,
and an authorised domain must be verified in Google Search Console -- i.e. a domain the owner
controls. The app is served from `*.azurecontainerapps.io`, which is not verifiable by us, so
publishing needs a purchased domain hosting a privacy policy. "Make internal" is greyed out too: that
needs a Google Workspace account, not a gmail.com one.

So the 7-day re-authorization stands, and TASK-160 covers it instead: the deployed site watches the
shared database and emails the owner when the check is failing or has not succeeded within
`MAILBOX_STALE_ALERT_HOURS` (default 24). Re-authorizing is two commands and takes about 30 seconds;
the point of the watchdog is that nobody has to remember to check.

## Which file to use

- `.env.local.example`: local console-email template.
- `.env.local-smtp.example`: local real-SMTP template, Gmail example.
- `.env.local-neon.example`: local Neon DB + console email template.
- `.env.local-one-server.example`: local one-server Django-serves-frontend template.
- `.env.azure.example`: Azure/Brevo SMTP template.
- `.env`: your local private file; do not commit it.

Your real Azure values should be stored in Azure settings, not committed to Git.
