# Change funnel-history-metrics: the real first-publish moment on the survey row,
# and the daily snapshot table behind the staff dashboard's state series.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0093_story_topics'),
    ]

    operations = [
        migrations.AddField(
            model_name='surveyheader',
            name='published_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.CreateModel(
            name='MetricSnapshot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('key', models.CharField(max_length=40)),
                ('value', models.FloatField()),
            ],
            options={
                'ordering': ['-date', 'key'],
                'indexes': [models.Index(fields=['key', 'date'], name='survey_metr_key_9feffe_idx')],
                'unique_together': {('date', 'key')},
            },
        ),
    ]
