# Change translation-table: the source hash a translation was written against.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0104_auditlog_structure_actions'),
    ]

    operations = [
        migrations.CreateModel(
            name='TranslationSource',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=160)),
                ('language', models.CharField(max_length=10)),
                ('source_hash', models.CharField(max_length=40)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('survey', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='translation_sources', to='survey.surveyheader')),
            ],
            options={
                'unique_together': {('survey', 'key', 'language')},
            },
        ),
    ]
