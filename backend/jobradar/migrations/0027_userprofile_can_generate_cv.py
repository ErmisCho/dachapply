from django.conf import settings
from django.db import migrations, models


def enable_cv_for_env_owner(apps, schema_editor):
    """Tick the new flag for the account CODEX_CV_OWNER_EMAIL already names.

    is_cv_owner keeps that env value as a fallback, so the owner's access does not depend on this
    running. It runs anyway so the admin checkbox tells the truth: without it the one account that
    can generate today would show up as disabled, and switching the flag off for them would look
    like it worked while the fallback silently kept the endpoints open.

    Matches on email or username because accounts here are created with the email as the username.
    Creates nothing: an owner with no UserProfile row keeps working through the env fallback.
    """
    owner = (getattr(settings, 'CODEX_CV_OWNER_EMAIL', '') or '').strip()
    if not owner:
        return
    UserProfile = apps.get_model('jobradar', 'UserProfile')
    UserProfile.objects.filter(user__email__iexact=owner).update(can_generate_cv=True)
    UserProfile.objects.filter(user__username__iexact=owner).update(can_generate_cv=True)


class Migration(migrations.Migration):

    dependencies = [
        ('jobradar', '0026_alter_invitecode_options_invitecode_owner'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='can_generate_cv',
            field=models.BooleanField(default=False),
        ),
        # Reverse is a no-op on purpose: the field is dropped on the way back anyway, and a reverse
        # that cleared the flag would be indistinguishable from an operator revoking it.
        migrations.RunPython(enable_cv_for_env_owner, migrations.RunPython.noop),
    ]
