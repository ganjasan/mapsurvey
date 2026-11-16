from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0130_map_layer_workspace'),
    ]

    operations = [
        migrations.AddField(
            model_name='surveysession',
            name='required_missing',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='surveysession',
            name='required_complete',
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterField(
            model_name='question',
            name='validation_settings',
            field=models.JSONField(blank=True, default=dict, help_text='Per-question settings: number {min_value, max_value}, geo {min_features, max_features, price}, spray {max_dots}, files {max_file_bytes, max_files}, budget'),
        ),
        migrations.AlterField(
            model_name='surveyheader',
            name='validation_settings',
            field=models.JSONField(blank=True, default=dict, help_text='Unused since change responses-required-unanswered; kept so no deploy drops a column.'),
        ),
    ]
