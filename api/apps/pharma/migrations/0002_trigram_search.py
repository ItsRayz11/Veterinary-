"""pg_trgm extension and GIN indexes for typo-tolerant search (PostgreSQL only; no-op elsewhere)."""

from django.db import migrations

INDEXES = [
    ("pharma_generic", "normalized_name"),
    ("pharma_genericsynonym", "normalized_synonym"),
    ("pharma_product", "normalized_brand_name"),
    ("companies_company", "normalized_name"),
]


def create(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for table, column in INDEXES:
        schema_editor.execute(
            f"CREATE INDEX IF NOT EXISTS {table}_{column}_trgm ON {table} "
            f"USING gin ({column} gin_trgm_ops)"
        )


def drop(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table, column in INDEXES:
        schema_editor.execute(f"DROP INDEX IF EXISTS {table}_{column}_trgm")


class Migration(migrations.Migration):
    dependencies = [
        ("pharma", "0001_initial"),
        ("companies", "0001_initial"),
    ]
    operations = [migrations.RunPython(create, drop)]
