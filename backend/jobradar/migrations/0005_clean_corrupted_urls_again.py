import re
from django.db import migrations


def normalize_job_url(value):
    raw=(value or '').strip()
    value=raw.replace('https://[https://','https://').replace('http://[http://','http://').strip('[]()<>.,;')
    embedded=re.findall(r'https?://[^\s\[\])>"}]+', value)
    if embedded:
        value=embedded[-1].strip('[]()<>.,;')
    if value.startswith('https-') or value.startswith('http-'):
        scheme, rest=value.split('-', 1)
        parts=rest.split('-')
        if len(parts) >= 2 and '.' in parts[0]:
            return f'{scheme}://' + parts[0] + '/' + '/'.join(parts[1:])
    if value and not value.startswith(('http://','https://')) and '.' in value and ' ' not in value:
        return 'https://' + value
    return value


def clean_urls(apps, schema_editor):
    JobLead=apps.get_model('jobradar','JobLead')
    for job in JobLead.objects.exclude(url=''):
        cleaned=normalize_job_url(job.url)
        if cleaned != job.url:
            job.url=cleaned
            job.save(update_fields=['url'])


class Migration(migrations.Migration):
    dependencies = [('jobradar', '0004_clean_corrupted_urls')]
    operations = [migrations.RunPython(clean_urls, migrations.RunPython.noop)]
