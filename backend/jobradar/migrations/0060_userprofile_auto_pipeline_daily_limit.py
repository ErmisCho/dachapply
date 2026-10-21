from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobradar', '0059_board_column_order_and_reanalyse_late_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='auto_pipeline_daily_limit',
            field=models.PositiveIntegerField(default=50),
        ),
    ]
