from django.db import migrations, models


class WidenOnly(migrations.AlterField):
    """Widen forwards; on rollback keep the wider column (narrowing could fail or lose values)."""

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        return None


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0010_review_pipeline"),
    ]

    operations = [
        WidenOnly(
            model_name="recordassessment",
            name="source_state",
            field=models.CharField(db_index=True, max_length=32),
        ),
    ]
