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

## Which file to use

- `.env.local.example`: local console-email template.
- `.env.local-smtp.example`: local real-SMTP template, Gmail example.
- `.env.local-neon.example`: local Neon DB + console email template.
- `.env.local-one-server.example`: local one-server Django-serves-frontend template.
- `.env.azure.example`: Azure/Brevo SMTP template.
- `.env`: your local private file; do not commit it.

Your real Azure values should be stored in Azure settings, not committed to Git.
