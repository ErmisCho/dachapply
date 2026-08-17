from django.conf import settings
from django.core.management.base import BaseCommand

from jobradar.services.mailbox import oauth_authorization_url, oauth_exchange_code, write_refresh_token


class Command(BaseCommand):
    help = (
        'TASK-109 AC1: one-time OAuth consent handshake for the Gmail-API mailbox-check path -- the '
        'route for an owner who has declined 2-Step Verification and so cannot get an IMAP app '
        'password (see docs/email-setup.md). Prints the Google authorization URL to open in a '
        'browser, accepts the authorization code pasted back, exchanges it for a refresh token, and '
        'writes ONLY that refresh token to the local, gitignored GMAIL_OAUTH_TOKEN_PATH file. Never '
        'prints the token itself, and never contacts a real mailbox -- this is the consent handshake '
        'only, `manage.py check_mailbox` is what actually reads mail afterward.'
    )

    def handle(self, *args, **opts):
        client_id = settings.GMAIL_OAUTH_CLIENT_ID
        client_secret = settings.GMAIL_OAUTH_CLIENT_SECRET
        if not (client_id and client_secret):
            self.stdout.write(self.style.ERROR(
                'GMAIL_OAUTH_CLIENT_ID/GMAIL_OAUTH_CLIENT_SECRET are not set. Add them to your local '
                '.env first (see .env.local.example and docs/email-setup.md), then re-run this command.'
            ))
            return

        self.stdout.write('Open this URL in a browser, sign in with the mailbox you want checked, and consent:\n')
        self.stdout.write(oauth_authorization_url(client_id))
        self.stdout.write(
            '\nAfter consenting you will land on an unreachable localhost page (e.g. "This site can\'t '
            'be reached") -- that is expected, nothing is meant to be listening there. Copy the value '
            'of the `code=` parameter out of that page\'s own address bar.\n'
        )
        code = input('Paste the authorization code here: ').strip()
        if not code:
            self.stdout.write(self.style.ERROR('No code entered; aborting.'))
            return

        try:
            token_response = oauth_exchange_code(client_id, client_secret, code)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'Token exchange failed: {exc}'))
            return

        refresh_token = token_response.get('refresh_token', '')
        if not refresh_token:
            self.stdout.write(self.style.ERROR(
                'Google did not return a refresh_token. This usually means this app was already '
                'authorized once before and the consent prompt did not re-trigger -- revoke access at '
                'https://myaccount.google.com/permissions and run this command again.'
            ))
            return

        write_refresh_token(settings.GMAIL_OAUTH_TOKEN_PATH, refresh_token)
        self.stdout.write(self.style.SUCCESS(
            f'Refresh token saved to {settings.GMAIL_OAUTH_TOKEN_PATH}. `manage.py check_mailbox` will '
            'now use the Gmail API automatically -- no further setup needed until the token expires or '
            'is revoked (testing-mode tokens expire after about 7 days; see docs/email-setup.md).'
        ))
