from django.db import migrations, models

FIELDS = [
    'evaluation_prompt_template',
    'combined_prompt_template',
    'enrichment_prompt_template',
    'bulk_links_prompt_template',
]


def add_missing_prompt_template_columns(apps, schema_editor):
    table = 'jobradar_userprofile'
    existing = {col.name for col in schema_editor.connection.introspection.get_table_description(schema_editor.connection.cursor(), table)}
    qn = schema_editor.quote_name
    for field in FIELDS:
        if field not in existing:
            schema_editor.execute(f"ALTER TABLE {qn(table)} ADD COLUMN {qn(field)} text NOT NULL DEFAULT ''")


class Migration(migrations.Migration):

    dependencies = [
        ('jobradar', '0010_userprofile_candidate_profile_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(add_missing_prompt_template_columns, migrations.RunPython.noop)],
            state_operations=[
                migrations.AddField(model_name='userprofile', name='evaluation_prompt_template', field=models.TextField(blank=True, default='')),
                migrations.AddField(model_name='userprofile', name='combined_prompt_template', field=models.TextField(blank=True, default='')),
                migrations.AddField(model_name='userprofile', name='enrichment_prompt_template', field=models.TextField(blank=True, default='')),
                migrations.AddField(model_name='userprofile', name='bulk_links_prompt_template', field=models.TextField(blank=True, default='')),
            ],
        ),
    ]
