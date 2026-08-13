from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobradar', '0019_joblead_original_source_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='learned_application_preferences',
            field=models.TextField(blank=True, default=''),
        ),
    ]
