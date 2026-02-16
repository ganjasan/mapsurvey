"""
Add lifecycle fields to SurveyHeader: status, password_hash, test_token.
test_token is added as nullable first; populated in next migration, finalized as unique+non-null after.
"""
import uuid as uuid_module
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0014_finalize_org_slug_nonnull'),
    ]

    operations = [
        migrations.AddField(
            model_name='surveyheader',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('draft', 'Draft'),
                    ('testing', 'Testing'),
                    ('published', 'Published'),
                    ('closed', 'Closed'),
                    ('archived', 'Archived'),
                ],
                default='draft',
            ),
        ),
        migrations.AddField(
            model_name='surveyheader',
            name='password_hash',
            field=models.CharField(max_length=128, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='surveyheader',
            name='test_token',
            field=models.UUIDField(null=True, blank=True),
        ),
    ]
