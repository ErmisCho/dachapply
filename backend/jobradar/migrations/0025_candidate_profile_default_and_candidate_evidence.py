from django.db import migrations, models

# Copied verbatim rather than imported: migrations must stay self-contained, and models.py no
# longer carries this text at all. Until this migration it was the default value of
# UserProfile.candidate_profile -- one real person's bio, handed to every account that skipped
# onboarding.
LEGACY_DEFAULT_CANDIDATE_PROFILE = '''Software Engineer based in Vienna. Strong Python backend experience. Django, FastAPI, REST APIs, Java. RAG, semantic search, LangChain, LangGraph. Elasticsearch/OpenSearch. SQL, PostgreSQL, MySQL. Docker, Linux, Kubernetes basics, AWS basics, Azure learning in progress. RabbitMQ, Redis, async/background processing from personal projects. Enterprise background in finance, telecom, and AI/search systems. German: professional working proficiency, B2 completed, C1 in progress. English: C2 certified. Stronger fit for Python Backend, AI Engineer, RAG, Search, Data Engineering, Platform, and reliability-focused roles. Weaker fit for frontend-heavy React/TypeScript roles, pure DevOps/SRE roles, pure ML research roles, and roles requiring deep professional cloud/Spark/Terraform experience. Do not invent experience. Be honest about gaps and hiring risk.'''


def pin_legacy_default_profiles(apps, schema_editor):
    """Pin the legacy text onto the rows that hold it today, before the default drops.

    Django materialises field defaults at INSERT time and does not put them in the DDL, so on a
    healthy database every such row already stores this text verbatim and this UPDATE changes
    zero bytes. It is here for the row that was ever inserted against a database-level default
    (old SQLite table rebuilds can carry one), so that dropping the default cannot silently empty
    a profile that is being evaluated against this text right now.

    Idempotent by construction: it writes back exactly the bytes it matched on, so re-running is a
    no-op and a user who legitimately typed this same text keeps it untouched.

    Rows holding '' are deliberately left empty. Backfilling them is the leak this migration is
    part of closing -- an empty profile must refuse prompt generation, not inherit a stranger's.
    """
    UserProfile = apps.get_model('jobradar', 'UserProfile')
    UserProfile.objects.filter(candidate_profile=LEGACY_DEFAULT_CANDIDATE_PROFILE).update(
        candidate_profile=LEGACY_DEFAULT_CANDIDATE_PROFILE
    )


class Migration(migrations.Migration):

    dependencies = [
        ('jobradar', '0024_userprofile_follow_up_digest_enabled'),
    ]

    operations = [
        migrations.RunPython(pin_legacy_default_profiles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='userprofile',
            name='candidate_profile',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='candidate_evidence',
            field=models.TextField(blank=True, default=''),
        ),
    ]
