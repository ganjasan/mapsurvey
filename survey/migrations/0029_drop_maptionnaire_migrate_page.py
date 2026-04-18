"""Data migration: remove the Maptionnaire migration-guide ComparisonPage.

The migration guide (/migrate-from-maptionnaire/) was dropped from v1 scope —
writing a defensible migration guide requires more reliable facts about
Maptionnaire's export formats than we can currently source. The URL pattern
and page_type='migrate' remain in the architecture for future competitors.

Idempotent: safe to run on databases where the row was never created.
Reverse: recreates the row as a draft (matching the original seed in 0028).
"""
from django.db import migrations
from datetime import date

SEED_DATE = date(2026, 4, 18)


def drop_maptionnaire_migrate(apps, schema_editor):
    ComparisonPage = apps.get_model('survey', 'ComparisonPage')
    ComparisonPage.objects.filter(
        competitor__slug='maptionnaire',
        page_type='migrate',
    ).delete()


def recreate_maptionnaire_migrate(apps, schema_editor):
    Competitor = apps.get_model('survey', 'Competitor')
    ComparisonPage = apps.get_model('survey', 'ComparisonPage')
    try:
        competitor = Competitor.objects.get(slug='maptionnaire')
    except Competitor.DoesNotExist:
        return
    ComparisonPage.objects.get_or_create(
        competitor=competitor,
        page_type='migrate',
        defaults={
            'status': 'draft',
            'last_fact_checked': SEED_DATE,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0028_seed_maptionnaire_comparison'),
    ]

    operations = [
        migrations.RunPython(drop_maptionnaire_migrate, recreate_maptionnaire_migrate),
    ]
