"""The translation table (change translation-table, spec translation-table):
occurrence keys and source hashes, the collector and its grouping, the one
writer, the gap engine's outdated/Next-label/thank-you entries, the page, the
modal mirror and the CSV round trip."""
import csv
import io
import json

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from survey import translation_table as tt
from survey.models import (
    Membership, Organization, Question, QuestionGroup, QuestionGroupTranslation, QuestionTranslation,
    SurveyCollaborator, SurveyHeader, SurveySection, SurveySectionTranslation, TranslationSource,
)
from survey.services import questions as svc_questions, sections as svc_sections, surveys as svc_surveys
from survey.services.context import Actor
from survey.services.errors import ContentLocked
from survey.translation_gaps import survey_translation_gaps
from survey.versioning import clone_survey_for_draft


def _survey(name='tt', status='draft', languages=('en', 'es'), role='owner'):
    org = Organization.objects.create(name=f'{name} org', slug=f'{name}-org')
    user = User.objects.create_user(username=f'{name}_user', password='pass')
    Membership.objects.create(user=user, organization=org, role=role)
    survey = SurveyHeader.objects.create(
        name=name, organization=org, status=status, redirect_url='#',
        available_languages=list(languages),
        thanks_html={'en': '<p>Thank you for your time.</p>'},
    )
    return survey, user


def _section(survey, code, order, title, head=False, prev=None, **kw):
    section = SurveySection.objects.create(
        survey_header=survey, name=f'sec_{code}_{order}', code=code, title=title, is_head=head, **kw)
    if prev is not None:
        prev.next_section_id = section.id
        prev.save(update_fields=['next_section_id'])
    return section


def _q(section, code, order, input_type='text', **kw):
    return Question.objects.create(
        survey_section=section, code=code, order_number=order,
        name=kw.pop('name', code), input_type=input_type, **kw)


def _druid(languages=('en', 'es')):
    """Two pages of the customer's survey: the repeated "Other" and help text,
    "Walk" under two questions, a Next label, an intro block and a thank-you page."""
    survey, user = _survey(languages=languages)
    intro = _section(survey, 'Intro', 0, 'Help Shape the Future', head=True, next_label='Start the Survey')
    page2 = _section(survey, 'S1', 1, 'Your Connection', prev=intro)
    page3 = _section(survey, 'S2', 2, 'Getting to the park', prev=page2)
    _q(intro, 'Q_HTML', 0, 'html', name='Intro block',
       subtext='<p>Druid Park Lake Drive is important.</p><p><strong>5–7 minutes.</strong></p>')
    _q(page2, 'Q_CONN', 0, 'multichoice', name='How are you connected?',
       subtext='<p>(Select all that apply)</p>',
       choices=[{'code': 1, 'name': {'en': 'I live nearby'}}, {'code': 2, 'name': {'en': 'Other'}, 'other': True}])
    _q(page2, 'Q_DO', 1, 'multichoice', name='What do you usually do?',
       subtext='<p>(Select all that apply)</p>',
       choices=[{'code': 1, 'name': {'en': 'Walk'}}, {'code': 2, 'name': {'en': 'Other'}, 'other': True}])
    _q(page3, 'Q_HOW', 0, 'multichoice', name='How do you get there?',
       choices=[{'code': 1, 'name': {'en': 'Walk'}}, {'code': 2, 'name': {'en': 'Other'}, 'other': True}])
    _q(page3, 'Q_NEIGH', 1, 'text', name='What neighborhood?')
    return survey, user


def _occ(survey, lang='es', key=None):
    occs = tt.occurrences(survey, lang)
    if key is None:
        return occs
    return next(o for o in occs if o.key == key)


def _rows(survey, lang='es'):
    return {r.key: r for r in tt.rows_for(tt.occurrences(survey, lang))}


class KeysAndHashesTest(TestCase):

    def test_section_keys_disambiguate_repeated_codes(self):
        """
        GIVEN two sections sharing a code
        WHEN their key prefixes are built
        THEN the ordinal tells them apart and a unique code gets none
        """
        survey, _ = _survey()
        a = _section(survey, 'S1', 0, 'A', head=True)
        b = _section(survey, 'S1', 1, 'B', prev=a)
        c = _section(survey, 'S2', 2, 'C', prev=b)
        self.assertEqual(tt.section_prefix(a), 'section:S1#0')
        self.assertEqual(tt.section_prefix(b), 'section:S1#1')
        self.assertEqual(tt.section_prefix(c), 'section:S2')

    def test_hash_ignores_whitespace_and_markup_noise(self):
        """
        GIVEN the same text with different whitespace, and rich text as typed vs sanitised
        WHEN hashed
        THEN the hashes are equal, and the group key carries the kind
        """
        self.assertEqual(tt.source_hash('Walk  ', tt.PLAIN), tt.source_hash(' Walk', tt.PLAIN))
        self.assertEqual(tt.source_hash('<p>Hi</p>', tt.RICH), tt.source_hash('<p>Hi</p><script>x()</script>', tt.RICH))
        self.assertNotEqual(tt.group_key('Walk', tt.PLAIN), tt.group_key('Walk', tt.RICH))


class CollectorTest(TestCase):

    def test_occurrences_in_respondent_order_with_locations(self):
        """
        GIVEN the two-page fixture
        WHEN occurrences are collected for Spanish
        THEN pages come in navigation order, the html block has no name row, the Next
             label and the thank-you page are present, and every row reads missing
        """
        survey, _ = _druid()
        occs = _occ(survey)
        keys = [o.key for o in occs]
        self.assertEqual(keys[:3], ['section:Intro:title', 'section:Intro:next_label', 'question:Q_HTML:subtext'])
        self.assertNotIn('question:Q_HTML:name', keys)
        self.assertEqual(keys[-1], tt.THANKS_KEY)
        self.assertLess(keys.index('question:Q_CONN:name'), keys.index('question:Q_HOW:name'))
        self.assertTrue(all(o.status == tt.MISSING for o in occs))
        conn = next(o for o in occs if o.key == 'question:Q_CONN:choice:2')
        self.assertEqual(conn.where, 'Page 2 · Question 1 option')
        self.assertEqual(conn.page, 2)

    def test_rows_group_identical_text_with_usage_count(self):
        """
        GIVEN "Other" under three questions and the help text under two
        WHEN rows are built
        THEN each is one row with its usage count, in the order of its first occurrence
        """
        survey, _ = _druid()
        rows = tt.rows_for(tt.occurrences(survey, 'es'))
        other = next(r for r in rows if r.source == 'Other')
        self.assertEqual(other.count, 3)
        self.assertEqual([o.key for o in other.occurrences][0], 'question:Q_CONN:choice:2')
        help_row = next(r for r in rows if 'Select all' in r.source)
        self.assertEqual(help_row.count, 2)
        self.assertEqual(help_row.kind, tt.RICH)
        self.assertEqual(len([r for r in rows if r.source == 'Walk']), 1)

    def test_row_splits_when_translations_differ(self):
        """
        GIVEN "Walk" translated "Caminar" under one question and "Caminando" under another
        WHEN rows are built
        THEN the Walk row is split and carries no common translation
        """
        survey, _ = _druid()
        q_do = Question.objects.get(code='Q_DO')
        q_how = Question.objects.get(code='Q_HOW')
        svc_questions.set_choice_names(q_do, 'es', {'1': 'Caminar'})
        svc_questions.set_choice_names(q_how, 'es', {'1': 'Caminando'})
        walk = next(r for r in tt.rows_for(tt.occurrences(survey, 'es')) if r.source == 'Walk')
        self.assertTrue(walk.split)
        self.assertEqual(walk.translation, '')
        self.assertEqual(walk.status, tt.TRANSLATED)

    def test_source_column_in_another_language_falls_back_to_primary(self):
        """
        GIVEN a trilingual survey where one question has a Spanish name and another has none
        WHEN occurrences are collected with Spanish as the source column
        THEN the translated one shows Spanish and the other shows the primary text, marked
        """
        survey, _ = _druid(languages=('en', 'es', 'fr'))
        q = Question.objects.get(code='Q_NEIGH')
        QuestionTranslation.objects.create(question=q, language='es', name='¿Qué vecindario?')
        occs = tt.occurrences(survey, 'fr', source_language='es')
        neigh = next(o for o in occs if o.key == 'question:Q_NEIGH:name')
        self.assertEqual(neigh.shown_source, '¿Qué vecindario?')
        self.assertFalse(neigh.shown_is_primary)
        conn = next(o for o in occs if o.key == 'question:Q_CONN:name')
        self.assertEqual(conn.shown_source, 'How are you connected?')
        self.assertTrue(conn.shown_is_primary)


class StatusTest(TestCase):

    def test_translation_without_hash_reads_translated(self):
        """
        GIVEN a translation row written before hashes existed
        WHEN its status is computed
        THEN it is translated, not outdated
        """
        survey, _ = _druid()
        q = Question.objects.get(code='Q_NEIGH')
        QuestionTranslation.objects.create(question=q, language='es', name='¿Qué vecindario?')
        self.assertEqual(_occ(survey, key='question:Q_NEIGH:name').status, tt.TRANSLATED)

    def test_base_edit_after_translation_makes_it_stale(self):
        """
        GIVEN a Spanish name saved through the question service, then the English name changed
        WHEN status is computed
        THEN the row is outdated; re-saving the Spanish from the table clears it
        """
        survey, user = _druid()
        q = Question.objects.get(code='Q_NEIGH')
        svc_questions.save_translations_for(q, survey, {'es': {'name': '¿Qué vecindario?', 'subtext': ''}})
        self.assertEqual(_occ(survey, key='question:Q_NEIGH:name').status, tt.TRANSLATED)
        q.name = 'What community or neighborhood?'
        q.save(update_fields=['name'])
        self.assertEqual(_occ(survey, key='question:Q_NEIGH:name').status, tt.STALE)
        tt.apply(Actor(user=user), survey, 'es', {'question:Q_NEIGH:name': '¿Qué vecindario?'}, overwrite=True)
        self.assertEqual(_occ(survey, key='question:Q_NEIGH:name').status, tt.TRANSLATED)

    def test_unchanged_translation_resave_keeps_stale(self):
        """
        GIVEN an outdated translation
        WHEN the service re-saves the same Spanish text without naming the field as reviewed
        THEN the hash is untouched and the row stays outdated
        """
        survey, _ = _druid()
        q = Question.objects.get(code='Q_NEIGH')
        svc_questions.save_translations_for(q, survey, {'es': {'name': 'Vecindario', 'subtext': ''}})
        q.name = 'Changed'
        q.save(update_fields=['name'])
        svc_questions.save_translations_for(q, survey, {'es': {'name': 'Vecindario', 'subtext': ''}})
        self.assertEqual(_occ(survey, key='question:Q_NEIGH:name').status, tt.STALE)

    def test_choice_and_thanks_hashes_recorded_by_their_services(self):
        """
        GIVEN option names saved by set_choices and a thank-you page by set_thanks
        WHEN the English changes
        THEN both rows read outdated
        """
        survey, user = _druid()
        actor = Actor(user=user)
        q = Question.objects.get(code='Q_HOW')
        svc_questions.set_choices(actor, q, [
            {'code': 1, 'name': {'en': 'Walk', 'es': 'Caminando'}},
            {'code': 2, 'name': {'en': 'Other', 'es': 'Otro'}, 'other': True}])
        svc_surveys.set_thanks(actor, survey, {'es': '<p>Gracias.</p>'}, languages=['es'])
        self.assertEqual(_occ(survey, key='question:Q_HOW:choice:1').status, tt.TRANSLATED)
        self.assertEqual(_occ(survey, key=tt.THANKS_KEY).status, tt.TRANSLATED)
        q.choices[0]['name']['en'] = 'Walk or run'
        q.save(update_fields=['choices'])
        survey.thanks_html = {**survey.thanks_html, 'en': '<p>Thanks a lot.</p>'}
        survey.save(update_fields=['thanks_html'])
        self.assertEqual(_occ(survey, key='question:Q_HOW:choice:1').status, tt.STALE)
        self.assertEqual(_occ(survey, key='question:Q_HOW:choice:2').status, tt.TRANSLATED)
        self.assertEqual(_occ(survey, key=tt.THANKS_KEY).status, tt.STALE)

    def test_hashes_are_keyed_by_the_canonical_survey(self):
        """
        GIVEN a translation saved on a survey
        WHEN the hash row is looked up
        THEN it belongs to the canonical survey header
        """
        survey, _ = _druid()
        q = Question.objects.get(code='Q_NEIGH')
        svc_questions.save_translations_for(q, survey, {'es': {'name': 'Vecindario', 'subtext': ''}})
        row = TranslationSource.objects.get(key='question:Q_NEIGH:name', language='es')
        self.assertEqual(row.survey_id, survey.id)
        self.assertEqual(row.source_hash, tt.source_hash('What neighborhood?', tt.PLAIN))


class GapEngineTest(TestCase):

    def test_gaps_report_next_label_thanks_page_and_outdated(self):
        """
        GIVEN a bilingual survey with an outdated Spanish name, no Spanish Next label and
              no Spanish thank-you page
        WHEN survey-wide gaps are computed
        THEN the question is listed with "es (outdated)", the intro section for its Next
             label and the thank-you page with "es"
        """
        survey, _ = _druid()
        for section in SurveySection.objects.filter(survey_header=survey):
            SurveySectionTranslation.objects.create(section=section, language='es', title='T', next_label=None)
        q = Question.objects.get(code='Q_NEIGH')
        svc_questions.save_translations_for(q, survey, {'es': {'name': 'Vecindario', 'subtext': ''}})
        q.name = 'Changed'
        q.save(update_fields=['name'])
        gaps = {g['label']: g['missing'] for g in survey_translation_gaps(survey)}
        self.assertEqual(gaps['Question: Changed'], ['es (outdated)'])
        self.assertEqual(gaps['Section: Help Shape the Future'], ['es'])
        self.assertNotIn('Section: Your Connection', gaps)
        self.assertEqual(gaps['Thank-you page'], ['es'])

    def test_missing_and_outdated_are_not_doubled(self):
        """
        GIVEN a question whose Spanish name is outdated and whose Spanish subtext is missing
        WHEN gaps are computed
        THEN the language is listed once, as missing
        """
        survey, _ = _druid()
        q = Question.objects.get(code='Q_CONN')
        svc_questions.save_translations_for(q, survey, {'es': {'name': 'Conexión', 'subtext': ''}})
        q.name = 'Changed'
        q.save(update_fields=['name'])
        gaps = {g['label']: g['missing'] for g in survey_translation_gaps(survey)}
        self.assertEqual(gaps['Question: Changed'], ['es'])


class WriterTest(TestCase):

    def setUp(self):
        self.survey, self.user = _druid()
        self.actor = Actor(user=self.user)

    def test_group_key_fills_every_occurrence(self):
        """
        GIVEN "Other" under three questions
        WHEN the group row is saved with "Otro"
        THEN every option carries name["es"] == "Otro" and the report counts three fills
        """
        rows = _rows(self.survey)
        other = next(r for r in rows.values() if r.source == 'Other')
        report = tt.apply(self.actor, self.survey, 'es', {other.key: 'Otro'})
        self.assertEqual((report.filled, report.skipped, report.overwritten), (3, 0, 0))
        for code in ('Q_CONN', 'Q_DO', 'Q_HOW'):
            q = Question.objects.get(code=code)
            self.assertEqual(q.choices[1]['name'], {'en': 'Other', 'es': 'Otro'})
        self.assertEqual(_rows(self.survey)[other.key].status, tt.TRANSLATED)

    def test_occurrence_key_writes_one_place(self):
        """
        GIVEN "Walk" under two questions
        WHEN one occurrence key is saved
        THEN only that option changes and the row is split afterwards once both differ
        """
        tt.apply(self.actor, self.survey, 'es', {'question:Q_DO:choice:1': 'Caminar'})
        self.assertEqual(Question.objects.get(code='Q_DO').choices[0]['name']['es'], 'Caminar')
        self.assertNotIn('es', Question.objects.get(code='Q_HOW').choices[0]['name'])
        walk = next(r for r in _rows(self.survey).values() if r.source == 'Walk')
        self.assertFalse(walk.split)
        self.assertEqual(walk.status, tt.MISSING)
        self.assertEqual(walk.translation, 'Caminar')

    def test_existing_translation_is_skipped_unless_overwrite(self):
        """
        GIVEN a question already translated
        WHEN the writer gets a different text without and then with overwrite
        THEN the first is skipped and the second replaces it
        """
        tt.apply(self.actor, self.survey, 'es', {'question:Q_NEIGH:name': 'Vecindario'})
        report = tt.apply(self.actor, self.survey, 'es', {'question:Q_NEIGH:name': 'Barrio'})
        self.assertEqual((report.filled, report.skipped), (0, 1))
        self.assertEqual(QuestionTranslation.objects.get(question__code='Q_NEIGH', language='es').name, 'Vecindario')
        report = tt.apply(self.actor, self.survey, 'es', {'question:Q_NEIGH:name': 'Barrio'}, overwrite=True)
        self.assertEqual(report.overwritten, 1)
        self.assertEqual(QuestionTranslation.objects.get(question__code='Q_NEIGH', language='es').name, 'Barrio')

    def test_section_group_and_thanks_go_through_their_services(self):
        """
        GIVEN a section title, a Next label, a group title and the thank-you page
        WHEN they are saved through the writer
        THEN the rows land in their models, the Next label is capped at 30, the thank-you
             page is sanitised, and existing fields of the same row are kept
        """
        page2 = SurveySection.objects.get(code='S1')
        group = QuestionGroup.objects.create(survey_section=page2, code='G1', title='About you', order_number=5)
        SurveySectionTranslation.objects.create(section=page2, language='es', subheading='<p>Intro es</p>')
        report = tt.apply(self.actor, self.survey, 'es', {
            'section:S1:title': 'Su conexión',
            'section:Intro:next_label': 'C' * 40,
            'group:G1:title': 'Acerca de usted',
            tt.THANKS_KEY: '<p>Gracias.</p><script>x()</script>',
        })
        self.assertEqual(report.filled, 4)
        row = SurveySectionTranslation.objects.get(section=page2, language='es')
        self.assertEqual((row.title, row.subheading), ('Su conexión', '<p>Intro es</p>'))
        self.assertEqual(len(SurveySectionTranslation.objects.get(section__code='Intro', language='es').next_label), 30)
        self.assertEqual(QuestionGroupTranslation.objects.get(group=group, language='es').title, 'Acerca de usted')
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.thanks_html['es'], '<p>Gracias.</p>')

    def test_rich_translation_is_coerced(self):
        """
        GIVEN a rich row
        WHEN saved with a script element
        THEN the stored subtext contains no script
        """
        tt.apply(self.actor, self.survey, 'es', {'question:Q_HTML:subtext': '<p>Hola</p><script>x()</script>'})
        self.assertEqual(QuestionTranslation.objects.get(question__code='Q_HTML', language='es').subtext, '<p>Hola</p>')

    def test_empty_value_clears_only_when_asked(self):
        """
        GIVEN a translated question
        WHEN an empty value arrives from a CSV and then from the table
        THEN the CSV leaves it and the table clears it
        """
        tt.apply(self.actor, self.survey, 'es', {'question:Q_NEIGH:name': 'Vecindario'})
        tt.apply(self.actor, self.survey, 'es', {'question:Q_NEIGH:name': ''})
        self.assertTrue(QuestionTranslation.objects.filter(question__code='Q_NEIGH', language='es').exists())
        report = tt.apply(self.actor, self.survey, 'es', {'question:Q_NEIGH:name': ''}, clear_empty=True)
        self.assertEqual(report.cleared, 1)
        self.assertFalse(QuestionTranslation.objects.filter(question__code='Q_NEIGH', language='es').exists())
        self.assertFalse(TranslationSource.objects.filter(key='question:Q_NEIGH:name').exists())

    def test_unknown_key_is_reported(self):
        report = tt.apply(self.actor, self.survey, 'es', {'question:NOPE:name': 'x'})
        self.assertEqual(report.unmatched, ['question:NOPE:name'])

    def test_live_survey_saves_in_place_and_locked_survey_refuses(self):
        """
        GIVEN a published survey with live editing on, then one shadowed by a draft
        WHEN a row is saved
        THEN the first saves without creating a draft and the second raises ContentLocked
        """
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        with self.settings(LIVE_SURVEY_EDITING=True):
            tt.apply(self.actor, self.survey, 'es', {'question:Q_NEIGH:name': 'Vecindario'})
        self.assertFalse(self.survey.has_draft_copy())
        self.assertEqual(QuestionTranslation.objects.get(question__code='Q_NEIGH', language='es').name, 'Vecindario')
        with self.settings(LIVE_SURVEY_EDITING=False):
            with self.assertRaises(ContentLocked):
                tt.apply(self.actor, self.survey, 'es', {'question:Q_NEIGH:name': 'Barrio'})


class CsvTest(TestCase):

    def setUp(self):
        self.survey, self.user = _druid()
        self.actor = Actor(user=self.user)

    def _export(self):
        return tt.export_csv(tt.rows_for(tt.occurrences(self.survey, 'es')))

    def test_export_shape(self):
        """
        GIVEN the fixture
        WHEN the Spanish table is exported
        THEN the file starts with a BOM and the header, the first rows are the intro page's
             title, Next button and text block, rich text is plain with blank lines, a
             repeated row names its count and a formula-looking cell is prefixed
        """
        q = Question.objects.get(code='Q_NEIGH')
        q.name = '=SUM(A1)'
        q.save(update_fields=['name'])
        data = self._export()
        self.assertTrue(data.startswith('﻿key,page,element,source,translation,status'))
        lines = list(csv.reader(io.StringIO(data.lstrip('﻿'))))
        self.assertEqual(lines[1][1:4], ['Page 1: Help Shape the Future', 'Page title', 'Help Shape the Future'])
        self.assertEqual(lines[2][2:4], ['Next button', 'Start the Survey'])
        self.assertEqual(lines[3][2:4], ['Formatted text', 'Druid Park Lake Drive is important.\n\n5–7 minutes.'])
        other = next(l for l in lines if l[3] == 'Other')
        self.assertEqual(other[2], 'Question 1 option (×3)')
        self.assertEqual(other[5], 'missing')
        self.assertTrue(any(l[3] == "'=SUM(A1)" for l in lines))

    def test_round_trip_fills_missing_and_skips_existing(self):
        """
        GIVEN an export whose translation cells a translator filled
        WHEN it is imported, then exported again
        THEN every filled row is written, a pre-existing translation is skipped, and the
             second export carries the imported texts
        """
        tt.apply(self.actor, self.survey, 'es', {'question:Q_NEIGH:name': 'Vecindario'})
        lines = list(csv.reader(io.StringIO(self._export().lstrip('﻿'))))
        out = io.StringIO()
        writer = csv.writer(out)
        for i, line in enumerate(lines):
            if i and not line[4]:
                line[4] = 'ES ' + line[3].replace('\n\n', '\n\n')
            if i and line[3] == '=SUM(A1)':
                pass
            if i and line[2].startswith('Question') and 'neighborhood' in line[3]:
                line[4] = 'Barrio'
            writer.writerow(line)
        parsed = tt.parse_csv(out.getvalue().encode('utf-8'))
        values, unmatched = tt.values_from_csv(parsed, tt.rows_for(tt.occurrences(self.survey, 'es')))
        self.assertEqual(unmatched, [])
        report = tt.apply(self.actor, self.survey, 'es', values)
        self.assertEqual(report.skipped, 1)
        self.assertEqual(report.unmatched, [])
        self.assertEqual(QuestionTranslation.objects.get(question__code='Q_NEIGH', language='es').name, 'Vecindario')
        self.assertEqual(Question.objects.get(code='Q_HOW').choices[1]['name']['es'], 'ES Other')
        html = QuestionTranslation.objects.get(question__code='Q_HTML', language='es').subtext
        self.assertEqual(html, '<p>ES Druid Park Lake Drive is important.</p><p>5–7 minutes.</p>')
        again = list(csv.reader(io.StringIO(self._export().lstrip('﻿'))))
        self.assertEqual([l[4] for l in again if l[3] == 'Other'], ['ES Other'])
        self.assertTrue(all(l[5] == 'translated' for l in again[1:]))

    def test_hand_built_file_matches_by_source_and_reports_unmatched(self):
        """
        GIVEN a CSV with no key column, in the customer's Page/Element/English/Spanish shape
        WHEN it is imported
        THEN rows are matched by the English text and an unknown one is reported
        """
        data = ('Page,Element,source,translation\n'
                'Page 2,Question 1 option,Other,Otro\n'
                'Page 3,Question 2,What neighborhood?,¿Qué vecindario?\n'
                'Page 3,Question 9,Prefer not to say,Prefiero no responder\n').encode('utf-8')
        values, unmatched = tt.values_from_csv(tt.parse_csv(data), tt.rows_for(tt.occurrences(self.survey, 'es')))
        self.assertEqual(unmatched, ['Prefer not to say'])
        report = tt.apply(self.actor, self.survey, 'es', values)
        self.assertEqual(report.filled, 4)
        self.assertEqual(Question.objects.get(code='Q_DO').choices[1]['name']['es'], 'Otro')

    def test_semicolon_delimiter_and_formula_prefix(self):
        """
        GIVEN a semicolon-separated file whose translation cell was exported with the apostrophe guard
        WHEN parsed
        THEN the delimiter is sniffed and the apostrophe stripped
        """
        data = "key;page;element;source;translation;status\nquestion:Q_NEIGH:name;p;e;What neighborhood?;'=Barrio;missing\n".encode('utf-8')
        values, _ = tt.values_from_csv(tt.parse_csv(data), tt.rows_for(tt.occurrences(self.survey, 'es')))
        self.assertEqual(values, {'question:Q_NEIGH:name': '=Barrio'})


class PageTest(TestCase):
    """The Translations tab: the nav tab, roles, the empty state, the draft
    redirect, row saves, export, import and adding a language."""

    def setUp(self):
        self.survey, self.user = _druid()
        self.client.login(username='tt_user', password='pass')
        self.url = reverse('editor_survey_translations', kwargs={'survey_uuid': self.survey.uuid})

    def _member(self, role, name):
        """An org member; an org editor reaches a survey only as its collaborator."""
        user = User.objects.create_user(username=name, password='pass')
        Membership.objects.create(user=user, organization=self.survey.organization, role=role)
        if role == 'editor':
            SurveyCollaborator.objects.create(user=user, survey=self.survey, role='editor')
        return user

    def test_tab_on_every_survey_page(self):
        """
        GIVEN the survey
        WHEN Build and Responses render
        THEN both carry the Translations tab between Survey and Responses
        """
        for name in ('editor_survey_detail', 'editor_survey_analytics'):
            html = self.client.get(reverse(name, kwargs={'survey_uuid': self.survey.uuid})).content.decode()
            self.assertIn(self.url, html)
            self.assertLess(html.index('fa-hammer'), html.index(self.url))
            self.assertLess(html.index(self.url), html.index('fa-chart-bar'))

    def test_page_renders_rows_with_links_and_counts(self):
        """
        GIVEN the fixture
        WHEN the owner opens the tab
        THEN the table has a row per unique text, usage counts, links into Build and status counts
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(html.count('class="tt-group'), 14)
        self.assertIn('×3', html)
        self.assertIn('?section=%d&amp;question=%d&amp;lang=es' % (
            SurveySection.objects.get(code='S1').id, Question.objects.get(code='Q_CONN').id), html)
        self.assertIn('?panel=thanks', html)
        self.assertIn('data-count="missing">14', html)
        self.assertIn('Add language', html)

    def test_defaults_and_remembered_pair_from_url(self):
        """
        GIVEN a trilingual survey and a creator whose UI language is French
        WHEN the tab opens with no parameters, then with ?from=es&to=fr
        THEN the target defaults to French and the explicit pair is honoured
        """
        self.survey.available_languages = ['en', 'es', 'fr']
        self.survey.save(update_fields=['available_languages'])
        from survey.models import CreatorPreferences
        CreatorPreferences.objects.update_or_create(user=self.user, defaults={'ui_language': 'fr'})
        html = self.client.get(self.url).content.decode()
        self.assertIn('data-to="fr"', html)
        html = self.client.get(self.url + '?from=es&to=fr').content.decode()
        self.assertIn('data-from="es"', html)
        # No Spanish text exists yet, so every source cell falls back to the
        # primary text with the note (the page itself renders in French here).
        self.assertIn('<div class="tt-note">', html)

    def test_single_language_empty_state(self):
        """
        GIVEN an English-only survey
        WHEN the owner opens the tab
        THEN the empty state offers the language picker and no table is rendered
        """
        self.survey.available_languages = ['en']
        self.survey.save(update_fields=['available_languages'])
        html = self.client.get(self.url).content.decode()
        self.assertIn('tt-empty', html)
        self.assertIn('lang-search', html)
        self.assertNotIn('tt-table', html)

    def test_viewer_reads_and_exports_but_cannot_write(self):
        """
        GIVEN a viewer
        WHEN they open the tab, export, and post a save and an import
        THEN the page and the CSV are served and both writes are refused with 403
        """
        self._member('viewer', 'viewer1')
        self.client.login(username='viewer1', password='pass')
        html = self.client.get(self.url).content.decode()
        self.assertIn('readonly', html)
        self.assertNotIn('tt-import-btn', html)
        self.assertNotIn('Add language', html)
        export = self.client.get(reverse('editor_survey_translations_export', kwargs={'survey_uuid': self.survey.uuid}) + '?to=es')
        self.assertEqual(export.status_code, 200)
        self.assertIn('attachment; filename="tt-translations-es.csv"', export['Content-Disposition'])
        save = self.client.post(reverse('editor_survey_translation_save', kwargs={'survey_uuid': self.survey.uuid}),
                                {'key': 'question:Q_NEIGH:name', 'value': 'x', 'from': 'en', 'to': 'es'})
        self.assertEqual(save.status_code, 403)
        imp = self.client.post(reverse('editor_survey_translations_import', kwargs={'survey_uuid': self.survey.uuid}), {'to': 'es'})
        self.assertEqual(imp.status_code, 403)

    def test_editor_sees_owner_hint_and_no_add(self):
        self._member('editor', 'editor1')
        self.client.login(username='editor1', password='pass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('Add language', html)
        self.assertIn('workspace owner adds languages', html)
        add = self.client.post(reverse('editor_survey_translation_add_language', kwargs={'survey_uuid': self.survey.uuid}), {'language': 'fr'})
        self.assertEqual(add.status_code, 403)

    def test_row_save_renders_row_with_status_and_counts(self):
        """
        GIVEN the owner on the tab
        WHEN a group row is saved over HTMX
        THEN the response is the re-rendered row, translated, and the counts header moved
        """
        rows = _rows(self.survey)
        other = next(r for r in rows.values() if r.source == 'Other')
        response = self.client.post(reverse('editor_survey_translation_save', kwargs={'survey_uuid': self.survey.uuid}),
                                    {'key': other.key, 'value': 'Otro', 'from': 'en', 'to': 'es'})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="row-%s"' % other.key, html)
        self.assertIn('tt-translated', html)
        self.assertIn('>Otro</textarea>', html)
        self.assertEqual(json.loads(response['X-TT-Counts'])['translated'], 1)

    def test_live_survey_with_draft_redirects_to_draft(self):
        """
        GIVEN a published survey with unpublished changes
        WHEN the owner opens the live survey's tab
        THEN they land on the draft's tab with the same query
        """
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        with self.settings(LIVE_SURVEY_EDITING=True):
            draft = clone_survey_for_draft(self.survey)
            response = self.client.get(self.url + '?to=es')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('editor_survey_translations', kwargs={'survey_uuid': draft.uuid}) + '?to=es')

    def test_import_round_trip_through_the_views(self):
        """
        GIVEN an exported CSV with the translation column filled
        WHEN it is uploaded with the import form
        THEN the report lands on the page and the rows are written
        """
        export = self.client.get(reverse('editor_survey_translations_export', kwargs={'survey_uuid': self.survey.uuid}) + '?to=es')
        lines = list(csv.reader(io.StringIO(export.content.decode('utf-8-sig'))))
        out = io.StringIO()
        writer = csv.writer(out)
        for i, line in enumerate(lines):
            if i and line[3] == 'Other':
                line[4] = 'Otro'
            writer.writerow(line)
        response = self.client.post(
            reverse('editor_survey_translations_import', kwargs={'survey_uuid': self.survey.uuid}),
            {'to': 'es', 'from': 'en', 'file': SimpleUploadedFile('t.csv', out.getvalue().encode('utf-8'), content_type='text/csv')})
        self.assertEqual(response.status_code, 302)
        html = self.client.get(response['Location']).content.decode()
        self.assertIn('t.csv', html)
        self.assertIn('3 filled', html)
        self.assertEqual(Question.objects.get(code='Q_HOW').choices[1]['name']['es'], 'Otro')

    def test_owner_adds_a_language_from_the_page(self):
        """
        GIVEN an English-only survey
        WHEN the owner posts a language
        THEN available_languages grows, the status is unchanged and the redirect opens the new pair
        """
        self.survey.available_languages = ['en']
        self.survey.save(update_fields=['available_languages'])
        response = self.client.post(reverse('editor_survey_translation_add_language', kwargs={'survey_uuid': self.survey.uuid}), {'language': 'es'})
        self.assertEqual(response.status_code, 200)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.available_languages, ['en', 'es'])
        self.assertEqual(self.survey.status, 'draft')
        self.assertTrue(response.json()['redirect'].endswith('?from=en&to=es'))
        bad = self.client.post(reverse('editor_survey_translation_add_language', kwargs={'survey_uuid': self.survey.uuid}), {'language': 'x1'})
        self.assertEqual(bad.status_code, 400)


class ModalMirrorTest(TestCase):
    """The modals keep a read-only mirror of the translations (spec survey-editor)."""

    def setUp(self):
        self.survey, self.user = _druid()
        self.client.login(username='tt_user', password='pass')
        self.q = Question.objects.get(code='Q_NEIGH')
        QuestionTranslation.objects.create(question=self.q, language='es', name='¿Qué vecindario?')

    def test_question_modal_shows_mirror_and_ignores_posted_translations(self):
        """
        GIVEN a question with a Spanish name
        WHEN the modal renders and then a save posts translation_es_name
        THEN the mirror links to the row and the posted value changes nothing
        """
        url = reverse('editor_question_edit', kwargs={'survey_uuid': self.survey.uuid, 'question_id': self.q.id})
        html = self.client.get(url).content.decode()
        self.assertIn('¿Qué vecindario?', html)
        self.assertIn('?to=es#row-question:Q_NEIGH:name', html)
        self.assertNotIn('name="translation_es_name"', html)
        self.assertIn('choice-name-mirror', html)
        self.client.post(url, {'name': 'What neighborhood?', 'input_type': 'text', 'translation_es_name': 'Barrio',
                               'autosave': '1'})
        self.assertEqual(QuestionTranslation.objects.get(question=self.q, language='es').name, '¿Qué vecindario?')

    def test_section_form_mirror_and_post_ignored(self):
        section = SurveySection.objects.get(code='S1')
        SurveySectionTranslation.objects.create(section=section, language='es', title='Su conexión')
        url = reverse('editor_section_detail', kwargs={'survey_uuid': self.survey.uuid, 'section_id': section.id})
        html = self.client.get(url).content.decode()
        self.assertIn('Su conexión', html)
        self.assertIn('?to=es#row-section:S1:title', html)
        self.assertNotIn('name="translation_es_title"', html)
        self.client.post(url, {'title': 'Your Connection', 'name': section.name, 'code': 'S1',
                               'translation_es_title': 'Nope', 'autosave': '1'})
        self.assertEqual(SurveySectionTranslation.objects.get(section=section, language='es').title, 'Su conexión')

    def test_choices_save_keeps_stored_translations(self):
        """
        GIVEN an option translated on the tab
        WHEN the modal saves the choices with the stored Spanish round-tripped
        THEN the Spanish name stays and no hash is rewritten
        """
        q = Question.objects.get(code='Q_HOW')
        svc_questions.set_choice_names(q, 'es', {'1': 'Caminando'})
        before = TranslationSource.objects.get(key='question:Q_HOW:choice:1', language='es').updated_at
        url = reverse('editor_question_edit', kwargs={'survey_uuid': self.survey.uuid, 'question_id': q.id})
        self.client.post(url, {'name': 'How do you get there?', 'input_type': 'multichoice', 'autosave': '1',
                               'choices_json': json.dumps([
                                   {'code': 1, 'name': {'en': 'Walk', 'es': 'Caminando'}},
                                   {'code': 2, 'name': {'en': 'Other'}, 'other': True}])})
        q.refresh_from_db()
        self.assertEqual(q.choices[0]['name'], {'en': 'Walk', 'es': 'Caminando'})
        self.assertEqual(TranslationSource.objects.get(key='question:Q_HOW:choice:1', language='es').updated_at, before)

    def test_thanks_panel_links_other_languages_and_keeps_them(self):
        """
        GIVEN a thank-you page in English and Spanish
        WHEN the panel renders and saves the English
        THEN the Spanish tab is a link to the table row and the Spanish text survives the save
        """
        self.survey.thanks_html = {'en': '<p>Thanks.</p>', 'es': '<p>Gracias.</p>'}
        self.survey.save(update_fields=['thanks_html'])
        url = reverse('editor_survey_thanks_panel', kwargs={'survey_uuid': self.survey.uuid})
        html = self.client.get(url).content.decode()
        self.assertIn('?to=es#row-survey:thanks', html)
        self.assertNotIn('name="thanks_es"', html)
        self.client.post(url, {'thanks_en': '<p>Thank you!</p>'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.thanks_html, {'en': '<p>Thank you!</p>', 'es': '<p>Gracias.</p>'})
