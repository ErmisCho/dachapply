from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('jobradar', '0008_friend_submitter_scope'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='requested_submit_for',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='friend_submit_requests', to=settings.AUTH_USER_MODEL),
        ),
    ]
