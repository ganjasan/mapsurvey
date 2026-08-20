# Fold primary-language translation rows into base fields.
#
# The editor used to render a translation input for every entry of
# available_languages, including the first (primary) one, and AI drafts wrote
# the same text to both the base field and a primary-language translation row.
# The two copies diverged under editing, and respondents saw whichever the
# get_translated_* fallback picked (non-empty translation wins, else base).
#
# This migration makes the storage match the new model — primary language in
# base fields only — by promoting the value respondents CURRENTLY see:
# a non-empty primary translation replaces the base value; an empty one just
# means the base value was already showing. Behavior-preserving by
# construction. The shadowed base text (never respondent-visible) is discarded;
# counts are logged for the deploy output.
#
# Choice names are normalized to the editor's shapes: flat strings on
# single-language surveys, per-language dicts with the primary key present on
# multilingual ones.
#
# Forward-only: reversing would need the discarded shadowed text. A second run
# finds no primary rows and nothing to normalize — idempotent.

from django.db import migrations


def _resolved_choice_name(name, lang):
    """Mirror Question.get_choice_name's dict resolution: lang -> 'en' -> first."""
    if not isinstance(name, dict):
        return name
    if lang and lang in name:
        return name[lang]
    if 'en' in name:
        return name['en']
    return next(iter(name.values()), '')


def fold_primary_translations(apps, schema_editor):
    SurveyHeader = apps.get_model('survey', 'SurveyHeader')
    SectionTranslation = apps.get_model('survey', 'SurveySectionTranslation')
    QuestionTranslation = apps.get_model('survey', 'QuestionTranslation')
    Question = apps.get_model('survey', 'Question')

    folded_sections = folded_questions = normalized_choices = 0

    for survey in SurveyHeader.objects.exclude(available_languages=[]).exclude(
        available_languages__isnull=True,
    ).iterator():
        langs = survey.available_languages or []
        if not langs:
            continue
        primary = langs[0]
        multilingual = len(langs) > 1

        for row in SectionTranslation.objects.filter(
            section__survey_header=survey, language=primary,
        ).select_related('section').iterator():
            section = row.section
            updates = []
            if row.title:
                section.title = row.title
                updates.append('title')
            if row.subheading:
                section.subheading = row.subheading
                updates.append('subheading')
            if updates:
                section.save(update_fields=updates)
            row.delete()
            folded_sections += 1

        for row in QuestionTranslation.objects.filter(
            question__survey_section__survey_header=survey, language=primary,
        ).select_related('question').iterator():
            question = row.question
            updates = []
            if row.name:
                question.name = row.name
                updates.append('name')
            if row.subtext:
                question.subtext = row.subtext
                updates.append('subtext')
            if updates:
                question.save(update_fields=updates)
            row.delete()
            folded_questions += 1

        for question in Question.objects.filter(
            survey_section__survey_header=survey, choices__isnull=False,
        ).iterator():
            choices = question.choices
            if not isinstance(choices, list):
                continue
            changed = False
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                name = choice.get('name')
                if not isinstance(name, dict):
                    continue
                if multilingual:
                    if primary not in name:
                        choice['name'] = {primary: _resolved_choice_name(name, primary), **name}
                        changed = True
                else:
                    choice['name'] = _resolved_choice_name(name, primary)
                    changed = True
            if changed:
                question.save(update_fields=['choices'])
                normalized_choices += 1

    print(
        f'\n  fold_primary_language_translations: '
        f'{folded_sections} section rows folded, '
        f'{folded_questions} question rows folded, '
        f'{normalized_choices} questions with normalized choices'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0051_question_choices_catchup'),
    ]

    operations = [
        migrations.RunPython(fold_primary_translations, migrations.RunPython.noop),
    ]
