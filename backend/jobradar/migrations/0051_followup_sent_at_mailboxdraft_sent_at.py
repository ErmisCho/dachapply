from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('jobradar', '0050_mailboxsuggestion_postponed_until_and_more')]

    operations = [
        migrations.AddField(
            model_name='followup',
            name='sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mailboxdraft',
            name='sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
