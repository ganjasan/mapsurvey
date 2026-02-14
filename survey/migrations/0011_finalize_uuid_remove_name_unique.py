import uuid

from django.db import migrations, models

import survey.models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0010_populate_survey_uuid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='surveyheader',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='surveyheader',
            name='name',
            field=models.CharField(max_length=45, validators=[survey.models.validate_url_name]),
        ),
    ]
