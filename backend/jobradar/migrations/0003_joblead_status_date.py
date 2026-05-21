from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('jobradar', '0002_allow_url_only_jobs')]
    operations = [
        migrations.AddField(model_name='joblead', name='status_date', field=models.DateField(blank=True, null=True)),
    ]
