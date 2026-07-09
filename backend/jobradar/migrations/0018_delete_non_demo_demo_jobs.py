from django.db import migrations
from django.db.models import Q


DEMO_USERNAME = 'demo@dachapply.com'
DEMO_JOB_URL_PREFIX = 'https://demo.dachapply.local/'
LEGACY_DEMO_JOB_URLS = ['https://example.com/jobs/dynatrace']


def delete_non_demo_demo_jobs(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    JobLead = apps.get_model('jobradar', 'JobLead')
    demo = User.objects.filter(username=DEMO_USERNAME).first()
    qs = JobLead.objects.filter(
        Q(url__startswith=DEMO_JOB_URL_PREFIX) |
        Q(source='demo') |
        Q(source='seed', url__in=LEGACY_DEMO_JOB_URLS)
    )
    if demo:
        qs = qs.exclude(Q(created_by_id=demo.pk) | Q(submitted_for_id=demo.pk))
    qs.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('jobradar', '0017_sitevisitor_had_anonymous_and_more'),
    ]

    operations = [
        migrations.RunPython(delete_non_demo_demo_jobs, migrations.RunPython.noop),
    ]
