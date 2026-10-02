# Change in-app-changelog: the seen watermark and the card switch.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0089_story_position'),
    ]

    operations = [
        migrations.AddField(
            model_name='creatorpreferences',
            name='changelog_seen',
            field=models.CharField(blank=True, default='', max_length=80),
        ),
        migrations.AddField(
            model_name='creatorpreferences',
            name='changelog_cards',
            field=models.BooleanField(default=True),
        ),
    ]
