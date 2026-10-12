"""Normalise SurveyHeader.redirect_url (change fix-redirect-url-validation, #271).

redirect_url was free text. On 2026-10-12 31 canonical surveys held a hashtag,
a thank-you message, a relative path or "#https://..." (the box was pre-filled
with "#"), and their respondents could not finish. This rewrites every row --
canonical surveys, draft copies, archived versions -- to "#" or a valid absolute
http(s) URL, keeping the link a creator meant when the URL only had "#" in front.

The rules are copied from survey/redirects.py on purpose: a migration must keep
doing what it did when it shipped, whatever happens to the app code later.
"""
import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import migrations, models

_validator = URLValidator(schemes=['http', 'https'])
_LEADING_ANCHOR_BEFORE_URL = re.compile(r'^#+(?=https?://)', re.IGNORECASE)
_SCHEME = re.compile(r'^(https?)://', re.IGNORECASE)


def normalise(value):
    value = (value or '').strip()
    value = _LEADING_ANCHOR_BEFORE_URL.sub('', value)
    if value.lower().startswith('www.'):
        value = 'https://' + value
    value = _SCHEME.sub(lambda m: m.group(1).lower() + '://', value)
    if len(value) > 250:
        return '#'
    try:
        _validator(value)
    except ValidationError:
        return '#'
    return value


def forwards(apps, schema_editor):
    SurveyHeader = apps.get_model('survey', 'SurveyHeader')
    for pk, old in SurveyHeader.objects.values_list('pk', 'redirect_url'):
        new = normalise(old)
        if new != old:
            SurveyHeader.objects.filter(pk=pk).update(redirect_url=new)
            print(f'  redirect_url normalised: survey {pk}: {old!r} -> {new!r}')


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0093_story_topics'),
    ]

    operations = [
        migrations.AlterField(
            model_name='surveyheader',
            name='redirect_url',
            field=models.CharField(default='#', help_text='"#" shows the built-in thank-you page; otherwise a full http(s) address respondents are sent to after the last page. Read it through survey.redirects, never raw.', max_length=250),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
