from django.db import migrations
from django.db.models import Sum, Max


def backfill_site_daily_usage(apps, schema_editor):
    UserDailyUsage = apps.get_model('jobradar', 'UserDailyUsage')
    SiteDailyUsage = apps.get_model('jobradar', 'SiteDailyUsage')
    for row in UserDailyUsage.objects.values('date').annotate(
        total=Sum('request_count'),
        last_seen=Max('last_seen_at'),
    ):
        usage, _ = SiteDailyUsage.objects.get_or_create(
            date=row['date'],
            defaults={
                'request_count': row['total'] or 0,
                'authenticated_count': row['total'] or 0,
                'anonymous_count': 0,
                'last_seen_at': row['last_seen'],
            },
        )
        if usage.request_count == 0 and row['total']:
            usage.request_count = row['total'] or 0
            usage.authenticated_count = row['total'] or 0
            usage.last_seen_at = row['last_seen']
            usage.save(update_fields=['request_count', 'authenticated_count', 'last_seen_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('jobradar', '0013_sitedailyusage'),
    ]

    operations = [
        migrations.RunPython(backfill_site_daily_usage, migrations.RunPython.noop),
    ]
