"""Seed the initial cohort vocabulary.

Idempotent (`get_or_create` by slug) so it is safe on a database where staff have
already created cohorts by hand. Reversing leaves the data alone -- cohorts may
carry manual assignments by then, and dropping them would destroy analysis.
See openspec/changes/user-cohorts/design.md (D4).
"""

from django.db import migrations

DIMENSIONS = [
    {
        'slug': 'plan',
        'name': 'Plan',
        'order': 10,
        'description': (
            'Commercial tier, recorded for analysis only -- it grants no access '
            'and reflects no billing state. Users stay unassigned until judged.'
        ),
        'cohorts': [
            ('free', 'Free', 10, '#64748b', 'Uses the product at no cost; the acquisition channel.'),
            ('pro', 'Pro', 20, '#16a34a', 'Would sit on (or already funds) a paid project line item.'),
        ],
    },
    {
        'slug': 'segment',
        'name': 'Segment',
        'order': 20,
        'description': 'Kind of organisation the creator works in.',
        'cohorts': [
            ('university', 'Universities', 10, '#3b82f6',
             'Faculty, researchers and research institutes.'),
            ('student-cohort', 'Student cohorts', 20, '#60a5fa',
             'Students on a course assignment; arrive in bursts, one semester long.'),
            ('municipality', 'Municipalities', 30, '#a855f7',
             'City, regional and national government (B2G).'),
            ('consultancy', 'Consultancies', 40, '#f59e0b',
             'Planning, mobility and engineering firms delivering client projects.'),
            ('ngo', 'NGOs & community', 50, '#14b8a6',
             'Associations, community groups, activists, civic initiatives.'),
            ('business', 'Business', 60, '#ef4444',
             'Commercial non-consultancy: energy, housing, real estate, agriculture.'),
            ('individual', 'Individuals', 70, '#94a3b8',
             'Personal, hobby and friends-and-family use.'),
        ],
    },
]


def seed(apps, schema_editor):
    CohortDimension = apps.get_model('survey', 'CohortDimension')
    Cohort = apps.get_model('survey', 'Cohort')

    for spec in DIMENSIONS:
        dimension, _ = CohortDimension.objects.get_or_create(
            slug=spec['slug'],
            defaults={
                'name': spec['name'],
                'order': spec['order'],
                'description': spec['description'],
            },
        )
        for slug, name, order, color, description in spec['cohorts']:
            Cohort.objects.get_or_create(
                dimension=dimension, slug=slug,
                defaults={
                    'name': name, 'order': order,
                    'color': color, 'description': description,
                },
            )


def unseed(apps, schema_editor):
    """Deliberately a no-op: seeded cohorts may hold manual assignments."""


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0038_cohorts'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
