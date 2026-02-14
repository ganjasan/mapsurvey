"""
Finalize Organization.slug as non-nullable unique, and SurveyHeader.organization as non-nullable CASCADE.
This migration runs AFTER the data migration that populates all slugs and org assignments.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0013_populate_default_org_memberships'),
    ]

    operations = [
        # Organization.slug: nullable → non-null
        migrations.AlterField(
            model_name='organization',
            name='slug',
            field=models.SlugField(max_length=100, unique=True),
        ),
        # SurveyHeader.organization: nullable SET_NULL → non-null CASCADE
        migrations.AlterField(
            model_name='surveyheader',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='survey.organization',
            ),
        ),
    ]
