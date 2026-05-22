from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('jobradar', '0005_clean_corrupted_urls_again')]

    operations = [
        migrations.AddField(
            model_name='joblead',
            name='interview_stage',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='joblead',
            name='interview_total',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
