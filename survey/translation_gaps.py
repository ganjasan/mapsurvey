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
- A section's Next-button label counts when the base label is set; the
  thank-you page counts when the primary-language page is non-empty (change
  translation-table).
- A translation written against an earlier source text is OUTDATED and
  reported as "<lang> (outdated)" — `translation_table` keeps the hash.
"""
OUTDATED = ' (outdated)'


def _with_outdated(missing, stale):
    """Missing languages first, then the outdated ones not already missing."""
    return list(missing) + [lang + OUTDATED for lang in stale if lang not in missing]


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
        if not gap and (section.next_label or '').strip():
            gap = not (row.next_label or '').strip()
        if gap:
            missing.append(lang)
    return missing


def thanks_missing_languages(survey):
    """The thank-you page counts once the primary-language page has text."""
    langs = translation_languages(survey)
    thanks = survey.thanks_html or {}
    if not langs or not isinstance(thanks, dict):
        return []
    primary = (survey.available_languages or ['en'])[0]
    if not (thanks.get(primary) or '').strip():
        return []
    return [lang for lang in langs if not (thanks.get(lang) or '').strip()]


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


def group_missing_languages(group, survey):
    """A question group (change question-groups): the title counts when the base
    title is set, the description when the base description is."""
    langs = translation_languages(survey)
    if not langs:
        return []
    rows = {t.language: t for t in group.translations.all()}
    missing = []
    for lang in langs:
        row = rows.get(lang)
        gap = False
        if (group.title or '').strip():
            gap = row is None or not (row.title or '').strip()
        if not gap and (group.description or '').strip():
            gap = row is None or not (row.description or '').strip()
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
    from .translation_table import outdated_by_entity
    stale = outdated_by_entity(survey)
    gaps = []
    for section in survey.surveysection_set.all().prefetch_related(
        'translations', 'question_set__translations', 'question_groups__translations',
    ):
        missing = _with_outdated(section_missing_languages(section, survey), stale.get(('section', section.id), ()))
        if missing:
            gaps.append({
                'label': 'Section: %s' % (section.title or section.name),
                'missing': missing,
            })
        for question in section.question_set.all():
            missing = _with_outdated(question_missing_languages(question, survey), stale.get(('question', question.id), ()))
            if missing:
                gaps.append({
                    'label': 'Question: %s' % (question.name or '(unnamed)'),
                    'missing': missing,
                })
        for group in section.question_groups.all():
            missing = _with_outdated(group_missing_languages(group, survey), stale.get(('group', group.id), ()))
            if missing:
                gaps.append({
                    'label': 'Group: %s' % (group.title or '(untitled)'),
                    'missing': missing,
                })
    missing = _with_outdated(thanks_missing_languages(survey), stale.get(('survey', survey.id), ()))
    if missing:
        gaps.append({'label': 'Thank-you page', 'missing': missing})
    return gaps
