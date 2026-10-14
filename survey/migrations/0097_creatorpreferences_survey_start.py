from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0096_demorequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='creatorpreferences',
            name='survey_start_default',
            field=models.CharField(
                blank=True,
                choices=[('', 'Ask every time'), ('blank', 'Start from scratch'), ('ai', 'Draft with AI')],
                default='',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='creatorpreferences',
            name='agent_access_requested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
