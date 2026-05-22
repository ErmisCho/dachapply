from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('jobradar', '0006_interview_stage')]

    operations = [
        migrations.AddField(
            model_name='joblead',
            name='last_update_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='joblead',
            name='feedback_due_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
