"""TASK-93: proof that a registered address belongs to whoever registered it.

The token is Django's PasswordResetTokenGenerator with its own salt and a hash value that drops
`password` and `last_login`. That is not cosmetic: register_view logs the new account straight in,
and every later login rewrites last_login, so a stock reset token minted at registration would
already be invalid by the time the user opened the link in their inbox. What is left -- pk and
email -- is exactly what the link asserts, so changing the address invalidates it and nothing else
does, short of PASSWORD_RESET_TIMEOUT (resend is the recovery path).
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.db.models import Q
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.response import Response

logger = logging.getLogger(__name__)

UNVERIFIED_DETAIL = 'Confirm your email address first. Check your inbox for the confirmation link, or request a new one from Account settings.'


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = 'jobradar.email_verification'

    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{user.email}{timestamp}'


email_verification_token = EmailVerificationTokenGenerator()


def is_email_verified(user):
    """Whether this account's address is proven.

    A missing profile row means an account that predates TASK-93 (or a createsuperuser account,
    which never gets one) and reads as verified: the gate must never lock out accounts that existed
    before it, which is AC3's other half -- the migration default covers the rows that do exist.
    """
    profile = getattr(user, 'jobradar_profile', None)
    return profile.email_verified if profile else True


def unverified_email_response(user):
    """403 Response while the address is unproven, else None.

    Same shape as views.password_rejection, so every gated endpoint is one `if` away from the check
    and none of them can grow its own wording of it.
    """
    if is_email_verified(user):
        return None
    return Response({'detail': UNVERIFIED_DETAIL, 'code': 'email_unverified'}, status=403)


def verification_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return f'{settings.FRONTEND_URL}/verify-email/{uid}/{email_verification_token.make_token(user)}'


def send_verification_email(user):
    """Send the confirmation link. Returns whether it went out.

    Best effort on purpose: registration creates the account first and calls this after, so a dead
    SMTP host costs the user a resend, not their signup. Never raises.
    """
    if not user.email:
        return False
    link = verification_link(user)
    try:
        send_mail(
            'Confirm your DACHApply email address',
            'Hello,\n\n'
            'Confirm this address to finish setting up your DACHApply account:\n\n'
            f'{link}\n\n'
            'If the link does not work, copy and paste the URL into your browser.\n\n'
            'You can already use your dashboard. Confirming unlocks the features that involve other '
            'people: friend requests and invite codes.\n\n'
            'If you did not create this account, you can safely ignore this email.\n\n'
            'Regards,\n'
            'The DACHApply Team',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True
    except Exception:
        # Never log the link: it is a bearer token for this account's verified state.
        logger.exception('Verification email delivery failed for user_id=%s', user.pk)
        return False


def mark_verified(user):
    """Flip the flag and resolve the friend request registration deferred.

    The stored lookup is cleared whether or not it matched, so a replayed link cannot re-run it and
    an unmatched name simply disappears -- the caller is told nothing either way, which is the same
    silence registration gave them.
    """
    profile = getattr(user, 'jobradar_profile', None)
    if profile is None:
        return
    lookup = profile.pending_friend_lookup
    profile.email_verified = True
    profile.pending_friend_lookup = ''
    if lookup and not profile.submit_for_id and not profile.requested_submit_for_id:
        User = get_user_model()
        profile.requested_submit_for = User.objects.filter(Q(username__iexact=lookup) | Q(email__iexact=lookup)).exclude(pk=user.pk).first()
    profile.save(update_fields=['email_verified', 'pending_friend_lookup', 'requested_submit_for'])
