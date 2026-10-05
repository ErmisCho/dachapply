from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobradar', '0054_joblead_ready_to_submit_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='board_status_order',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
    ]
