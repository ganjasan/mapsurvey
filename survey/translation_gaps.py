"""Which non-primary languages an entity is missing translations for.

The respondent-side get_translated_* fallback silently substitutes base text
when a translation is missing, so the author never notices a gap. These
helpers are the editor's counterweight: per-entity badges and the pre-publish
warning both read them. Single-language surveys have no non-primary languages
and therefore never report gaps.

Rules (spec: translation-completeness):
- A language is missing when the entity has no translation row or an empty
  translated primary text (section title, question name).
- Optional texts (section subheading, question subtext) count only when the
  corresponding base field is non-empty.
- For choice questions, a choice name that is not a dict or lacks the
  language's key counts as missing.
"""


def translation_languages(survey):
    """Non-primary languages — everything after available_languages[0]."""
    return (survey.available_languages or [])[1:]


def section_missing_languages(section, survey):
    langs = translation_languages(survey)
    if not langs:
        return []
    rows = {t.language: t for t in section.translations.all()}
    missing = []
    for lang in langs:
        row = rows.get(lang)
        gap = row is None or not (row.title or '').strip()
        if not gap and (section.subheading or '').strip():
            gap = not (row.subheading or '').strip()
        if gap:
            missing.append(lang)
    return missing


def question_missing_languages(question, survey):
    langs = translation_languages(survey)
    if not langs:
        return []
    rows = {t.language: t for t in question.translations.all()}
    missing = []
    for lang in langs:
        row = rows.get(lang)
        gap = row is None or not (row.name or '').strip()
        if not gap and (question.subtext or '').strip():
            gap = not (row.subtext or '').strip()
        if not gap:
            for choice in (question.choices or []):
                name = choice.get('name') if isinstance(choice, dict) else None
                if not isinstance(name, dict) or not (name.get(lang) or '').strip():
                    gap = True
                    break
        if gap:
            missing.append(lang)
    return missing


def survey_translation_gaps(survey):
    """[{'label': ..., 'missing': [lang, ...]}] over all sections and questions.

    Sub-questions are included — they render in feature popups and fall back
    to base text just like top-level questions.
    """
    if not translation_languages(survey):
        return []
    gaps = []
    for section in survey.surveysection_set.all().prefetch_related(
        'translations', 'question_set__translations',
    ):
        missing = section_missing_languages(section, survey)
        if missing:
            gaps.append({
                'label': 'Section: %s' % (section.title or section.name),
                'missing': missing,
            })
        for question in section.question_set.all():
            missing = question_missing_languages(question, survey)
            if missing:
                gaps.append({
                    'label': 'Question: %s' % (question.name or '(unnamed)'),
                    'missing': missing,
                })
    return gaps
