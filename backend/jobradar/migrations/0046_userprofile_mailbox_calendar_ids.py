# TASK-116 AC6: replaces mailbox_calendar_ics_urls (a secret ICS URL) with mailbox_calendar_ids (a
# Google Calendar id -- not a secret). Removing the old field in the SAME migration that adds the new
# one is deliberate: leaving both around, even briefly, is exactly the "two configuration paths for
# one setting" failure mode this task exists to end.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobradar', '0045_mailboxmessage_calendar_checked_at'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userprofile',
            name='mailbox_calendar_ics_urls',
        ),
        migrations.AddField(
            model_name='userprofile',
            name='mailbox_calendar_ids',
            field=models.TextField(blank=True, default=''),
        ),
    ]
