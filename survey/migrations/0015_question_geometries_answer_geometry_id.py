from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0014_finalize_org_slug_nonnull'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='geometries',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='answer',
            name='geometry_id',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='question',
            name='input_type',
            field=models.CharField(
                choices=[
                    ('text', 'Text'),
                    ('number', 'Number'),
                    ('choice', 'Choices'),
                    ('multichoice', 'Multiple Choices'),
                    ('range', 'Range'),
                    ('rating', 'Rating'),
                    ('datetime', 'Date/Time'),
                    ('point', 'Geo Point'),
                    ('line', 'Geo Line'),
                    ('polygon', 'Geo Polygon'),
                    ('image', 'Image'),
                    ('text_line', 'Single Line Text'),
                    ('html', 'HTML'),
                    ('pressure', 'Geometry Pressure'),
                ],
                max_length=80,
            ),
        ),
    ]
