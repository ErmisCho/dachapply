from django.db import migrations, models


def backfill_applied_at(apps, schema_editor):
    """Copy status_date onto applied_at for jobs still sitting in 'applied'.

    Only this case is derivable: status_date means "date of the last transition",
    so for a job whose last transition was into 'applied' it *is* the applied
    date. Jobs that already moved on (interview/rejected/...) overwrote that date
    long ago, so their applied_at stays null rather than being guessed.
    """
    JobLead = apps.get_model('jobradar', 'JobLead')
    JobLead.objects.filter(status='applied', applied_at__isnull=True, status_date__isnull=False).update(applied_at=models.F('status_date'))


class Migration(migrations.Migration):

    dependencies = [
        ('jobradar', '0021_joblead_applied_at_and_outcome_statuses'),
    ]

    operations = [
        migrations.RunPython(backfill_applied_at, migrations.RunPython.noop),
    ]
