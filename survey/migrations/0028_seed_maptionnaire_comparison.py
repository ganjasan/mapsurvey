"""Data migration: seed Maptionnaire as first Competitor with three draft ComparisonPage rows.

Rolling this migration back will cascade-delete any ComparisonPage rows attached to the
Maptionnaire Competitor, including ones added manually after the initial seed.
"""
from django.db import migrations
from datetime import date

SEED_DATE = date(2026, 4, 18)


def seed_maptionnaire(apps, schema_editor):
    Competitor = apps.get_model('survey', 'Competitor')
    ComparisonPage = apps.get_model('survey', 'ComparisonPage')

    competitor, _ = Competitor.objects.get_or_create(
        slug='maptionnaire',
        defaults={
            'display_name': 'Maptionnaire',
            'is_active': True,
        },
    )

    for page_type in ('alternative', 'vs', 'migrate'):
        ComparisonPage.objects.get_or_create(
            competitor=competitor,
            page_type=page_type,
            defaults={
                'status': 'draft',
                'last_fact_checked': SEED_DATE,
            },
        )


def unseed_maptionnaire(apps, schema_editor):
    Competitor = apps.get_model('survey', 'Competitor')
    Competitor.objects.filter(slug='maptionnaire').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0027_add_competitor_comparisonpage'),
    ]

    operations = [
        migrations.RunPython(seed_maptionnaire, unseed_maptionnaire),
    ]
