from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0094_normalize_redirect_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='surveyheader',
            name='embed_allowed_hosts',
            field=models.JSONField(blank=True, default=list, help_text='Hosts allowed to embed this survey in an iframe, e.g. ["city.example.org", "*.consult.example"]. Empty = any site. Read on the canonical survey only.'),
        ),
    ]
