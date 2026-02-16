"""
Finalize test_token: make it non-nullable, unique, with uuid4 default.
"""
import uuid as uuid_module
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0016_populate_lifecycle_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='surveyheader',
            name='test_token',
            field=models.UUIDField(default=uuid_module.uuid4, unique=True),
        ),
    ]
