from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0008_add_thanks_html'),
    ]

    operations = [
        migrations.AddField(
            model_name='surveyheader',
            name='uuid',
            field=models.UUIDField(null=True, editable=False),
        ),
    ]
