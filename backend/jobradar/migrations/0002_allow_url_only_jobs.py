from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('jobradar', '0001_initial')]
    operations = [
        migrations.AlterField(model_name='joblead', name='company', field=models.CharField(blank=True, default='Unknown company', max_length=200)),
        migrations.AlterField(model_name='joblead', name='title', field=models.CharField(blank=True, default='Untitled role', max_length=250)),
    ]
