from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobradar', '0014_backfill_site_daily_usage'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduledTaskRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('last_run_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
