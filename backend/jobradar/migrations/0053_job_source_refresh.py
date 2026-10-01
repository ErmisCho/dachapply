from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('jobradar', '0052_widen_job_text_fields')]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='posting_refresh_cadence',
            field=models.CharField(choices=[('off', 'Off'), ('daily', 'Daily'), ('weekly', 'Weekly')], default='daily', max_length=10),
        ),
        migrations.AddField(
            model_name='joblead',
            name='pending_source_text',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='joblead',
            name='pending_source_fetched_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='joblead',
            name='source_checked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='joblead',
            name='source_fetch_error',
            field=models.TextField(blank=True, default=''),
        ),
    ]
