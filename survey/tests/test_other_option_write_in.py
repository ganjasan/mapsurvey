"""Tests for the `other-option-write-in` capability (openspec/specs/other-option-write-in/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from io import BytesIO
import json
import re
import zipfile
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, PublicResultsPage, PublicResultsBlock
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.analytics import SurveyAnalyticsService
from survey.versioning import clone_survey_for_draft
import csv
from survey.tests.helpers import _make_org, _objects_layer


class OtherOptionWriteInTest(TestCase):
    """The native "Other, please specify" option (spec other-option-write-in): one
    flagged choice, a write-in field under it on every surface, text on the same
    Answer row, an adjacent export column, inline display for the creator and no
    text on public surfaces."""

    COPE = [{"code": 1, "name": "Stay indoors"}, {"code": 2, "name": "Seek shade"},
            {"code": 4, "name": "Other (specify)", "other": True}]
    SRC = [{"code": 1, "name": "Trees"}, {"code": 2, "name": "Water"},
           {"code": 9, "name": "Other", "other": True}]

    def setUp(self):
        self.org = _make_org('OtherOrg')
        self.user = User.objects.create_user('otherowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='other_survey', organization=self.org, created_by=self.user,
            status='published', redirect_url='/thanks/', available_languages=['en'],
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )

        def q(name, code, input_type, order, choices=None, parent=None, **extra):
            return Question.objects.create(
                survey_section=self.section, name=name, code=code, input_type=input_type,
                order_number=order, choices=choices, parent_question_id=parent, **extra,
            )

        self.q_cope = q('How do you cope?', 'Q_COPE', 'choice', 1, self.COPE)
        self.q_src = q('Sources', 'Q_SRC', 'multichoice', 2, self.SRC)
        self.q_plain = q('Plain', 'Q_PLAIN', 'choice', 3, [{"code": 1, "name": "A"}, {"code": 2, "name": "B"}])
        self.q_dd = q('District', 'Q_DD', 'choice', 4,
                      [{"code": 1, "name": "North"}, {"code": 5, "name": "Other", "other": True}],
                      display_style='dropdown')
        self.q_point = q('Spot', 'Q_SPOT', 'point', 5)
        self.sub_type = q('Type', 'S_TYPE', 'choice', 1,
                          [{"code": 1, "name": "Park"}, {"code": 3, "name": "Other", "other": True}],
                          parent=self.q_point)
        self.layer = _objects_layer(self.survey, name='Sites', key_field='zone_id', label_field='name')
        self.q_obj = q('Objects', 'LR001', 'layer_objects', 6, layer=self.layer, min_objects=0)
        self.sub_obj = q('Fix', 'LR_FIX', 'choice', 1,
                         [{"code": 1, "name": "Bench"}, {"code": 4, "name": "Other", "other": True}],
                         parent=self.q_obj)
        self.url = f'/surveys/{self.survey.uuid}/{self.section.name}/'

    def _start(self):
        self.client.get(f'/surveys/{self.survey.uuid}/')
        return self.client.get(self.url)

    def _session(self):
        return SurveySession.objects.create(survey=self.survey)

    def _login_editor(self):
        self.survey.status = 'draft'
        self.survey.save()
        self.client.login(username='otherowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_rule_module_and_model_accessors(self):
        """
        GIVEN a choice question with one flagged option and a rating question with a stray flag
        WHEN the write-in rule is asked what the flag means
        THEN only choice types have a write-in option, text is kept only with the flagged code,
             a second flag collapses, and the model accessors delegate to the same rule
        """
        from survey import other_option
        self.assertEqual(self.q_cope.other_choice_code(), 4)
        self.assertIsNone(self.q_plain.other_choice_code())
        rating = Question.objects.create(
            survey_section=self.section, name='Stars', code='Q_ST', input_type='rating', order_number=9,
            choices=[{"code": 1, "name": "1"}, {"code": 2, "name": "2", "other": True}],
        )
        self.assertIsNone(rating.other_choice_code())
        self.assertEqual(other_option.other_text(self.q_cope, [4], ' towel '), 'towel')
        self.assertEqual(other_option.other_text(self.q_cope, [4], None), '')
        self.assertIsNone(other_option.other_text(self.q_cope, [1], 'towel'))
        clamped = other_option.clamp_single_other(
            [{"code": 1, "other": True}, {"code": 2, "other": True}, "junk"])
        self.assertEqual(clamped, [{"code": 1, "other": True}, {"code": 2}, "junk"])
        answer = Answer(question=self.q_src, selected_choices=[1, 9], text='mall')
        self.assertEqual(answer.other_text(), 'mall')
        self.assertEqual(answer.choice_display(), 'Trees, Other: mall')
        self.assertIsNone(Answer(question=self.q_src, selected_choices=[1], text='stale').other_text())
        self.assertEqual(other_option.export_cell(self.q_cope, None, ''),
                         {'How do you cope?': '', 'How do you cope?: Other (specify)': ''})
        self.assertEqual(other_option.export_cell(self.q_plain, None, ''), '')

    def test_write_in_renders_hidden_and_disabled_on_every_surface(self):
        """
        GIVEN a section with flagged options on a radio, a multichoice, a dropdown and two popup sub-questions
        WHEN the respondent opens it
        THEN each flagged option carries a write-in input named <code>-other, hidden and disabled,
             the plain question carries none, the reveal script is loaded, and both popup forms carry one
        """
        html = self._start().content.decode()
        for code, other in (('Q_COPE', 4), ('Q_SRC', 9), ('Q_DD', 5)):
            wrap = re.search(
                r'<div class="other-writein" data-other-for="%s" data-other-code="%s"([^>]*)>\s*<input([^>]*)>' % (code, other),
                html)
            self.assertIsNotNone(wrap, code)
            self.assertIn('hidden', wrap.group(1))
            self.assertIn('name="%s-other"' % code, wrap.group(2))
            self.assertIn('disabled', wrap.group(2))
        self.assertNotIn('data-other-for="Q_PLAIN"', html)
        self.assertRegex(html, r'js/other_option(\.[0-9a-f]+)?\.js')
        forms = json.loads(re.search(r'id="sq-forms-data"[^>]*>(.*?)</script>', html, re.S).group(1))
        self.assertIn('name="S_TYPE-other"', forms['Q_SPOT'])
        self.assertIn('name="LR_FIX-other"', forms['LR001'])

    def test_top_level_save_revisit_and_tamper(self):
        """
        GIVEN a respondent who picks the write-in option on a radio and a multichoice question
        WHEN the section is posted, revisited, re-posted with the text but not the option,
             then with the option and an empty text
        THEN the text lands on the same Answer row as the codes, the revisit shows it prefilled
             and visible, the tampered text is discarded, and the empty write-in is stored as ''
        """
        self._start()
        self.client.post(self.url, {
            'Q_COPE': '4', 'Q_COPE-other': ' wet towel ',
            'Q_SRC': ['1', '9'], 'Q_SRC-other': 'mall', 'Q_PLAIN': '1',
        })
        session = SurveySession.objects.get(survey=self.survey)
        cope = Answer.objects.get(survey_session=session, question=self.q_cope)
        self.assertEqual((cope.selected_choices, cope.text), ([4], 'wet towel'))
        src = Answer.objects.get(survey_session=session, question=self.q_src)
        self.assertEqual((src.selected_choices, src.text), ([1, 9], 'mall'))
        self.assertIsNone(Answer.objects.get(survey_session=session, question=self.q_plain).text)

        html = self.client.get(self.url).content.decode()
        wrap = re.search(r'<div class="other-writein" data-other-for="Q_COPE"([^>]*)>\s*<input([^>]*)>', html)
        self.assertNotIn('hidden', wrap.group(1))
        self.assertIn('value="wet towel"', wrap.group(2))
        self.assertNotIn('disabled', wrap.group(2))

        self.client.post(self.url, {'Q_COPE': '2', 'Q_COPE-other': 'stale', 'Q_SRC': ['1'], 'Q_SRC-other': 'stale'})
        self.assertIsNone(Answer.objects.get(survey_session=session, question=self.q_cope).text)
        self.assertIsNone(Answer.objects.get(survey_session=session, question=self.q_src).text)
        self.client.post(self.url, {'Q_COPE': '4', 'Q_COPE-other': ''})
        self.assertEqual(Answer.objects.get(survey_session=session, question=self.q_cope).text, '')

    def test_geo_sub_answer_round_trip(self):
        """
        GIVEN a point feature whose popup picked the write-in type and typed a reason
        WHEN the section is posted and revisited
        THEN the child Answer carries codes and text on one row, no row exists for the
             write-in property, and the restored feature carries S_TYPE and S_TYPE-other
        """
        self._start()
        feature = json.dumps({
            'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [74.6, 42.87]},
            'properties': {'question_id': 'Q_SPOT', 'S_TYPE': ['3'], 'S_TYPE-other': ['graffiti']},
        })
        response = self.client.post(self.url, {'Q_SPOT': feature})
        self.assertIn(response.status_code, (200, 302))
        session = SurveySession.objects.get(survey=self.survey)
        children = list(Answer.objects.filter(survey_session=session, parent_answer_id__isnull=False))
        self.assertEqual(len(children), 1)
        self.assertEqual((children[0].question.code, children[0].selected_choices, children[0].text),
                         ('S_TYPE', [3], 'graffiti'))
        props = self.client.get(self.url).context['existing_geo_answers']['Q_SPOT'][0]['properties']
        self.assertEqual(props['S_TYPE'], ['3'])
        self.assertEqual(props['S_TYPE-other'], ['graffiti'])

    def test_object_answer_round_trip(self):
        """
        GIVEN a respondent who picked the write-in option about object 1 and typed what to fix
        WHEN the obj__<key>__<code> fields are posted and the section revisited
        THEN the object Answer carries codes and text, and the page embeds LR_FIX-other for the popup
        """
        self._start()
        response = self.client.post(self.url, {'obj__1__LR_FIX': '4', 'obj__1__LR_FIX-other': 'broken bench'})
        self.assertIn(response.status_code, (200, 302))
        rows = list(Answer.objects.filter(layer_object__isnull=False))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].layer_object.key, rows[0].selected_choices, rows[0].text),
                         ('1', [4], 'broken bench'))
        html = self.client.get(self.url).content.decode()
        data = json.loads(re.search(r'id="object-answers-data"[^>]*>(.*?)</script>', html, re.S).group(1))
        self.assertEqual(data['LR001']['1']['LR_FIX'], ['4'])
        self.assertEqual(data['LR001']['1']['LR_FIX-other'], ['broken bench'])

    def test_export_adjacent_column_in_csv_geojson_and_objects(self):
        """
        GIVEN answers with and without the write-in option on a top-level question, a multichoice,
             a geo sub-question and an object sub-question
        WHEN the creator downloads the data
        THEN every surface carries "<question>: <option label>" right after the question's column,
             filled only where the option was picked, and the unflagged question has no such column
        """
        import csv
        import io
        s1, s2 = self._session(), self._session()
        Answer.objects.create(survey_session=s1, question=self.q_cope, selected_choices=[4], text='wet towel')
        Answer.objects.create(survey_session=s2, question=self.q_cope, selected_choices=[1])
        Answer.objects.create(survey_session=s1, question=self.q_src, selected_choices=[1, 9], text='mall')
        Answer.objects.create(survey_session=s1, question=self.q_plain, selected_choices=[2])
        point = Answer.objects.create(survey_session=s1, question=self.q_point, point=Point(74.6, 42.87, srid=4326))
        Answer.objects.create(survey_session=s1, question=self.sub_type, parent_answer_id=point,
                              selected_choices=[3], text='graffiti')
        obj = self.layer.items.get(key='1')
        Answer.objects.create(survey_session=s1, question=self.sub_obj, layer_object=obj,
                              selected_choices=[4], text='broken bench')

        self.client.login(username='otherowner', password='pass')
        response = self.client.get(f'/surveys/{self.survey.uuid}/download')
        self.assertEqual(response.status_code, 200)
        archive = zipfile.ZipFile(BytesIO(response.content))
        names = archive.namelist()

        main_csv = [n for n in names if n.endswith('.csv') and not n.split('/')[-1].startswith('objects_')][0]
        rows = list(csv.DictReader(io.StringIO(archive.read(main_csv).decode('utf-8'))))
        by_session = {r['session_id']: r for r in rows}
        r1, r2 = by_session[str(s1.id)], by_session[str(s2.id)]
        self.assertEqual(r1['How do you cope?'], 'Other (specify)')
        self.assertEqual(r1['How do you cope?: Other (specify)'], 'wet towel')
        self.assertEqual(r2['How do you cope?'], 'Stay indoors')
        self.assertEqual(r2['How do you cope?: Other (specify)'], '')
        self.assertEqual(r1['Sources'], 'Trees; Other')
        self.assertEqual(r1['Sources: Other'], 'mall')
        header = list(rows[0].keys())
        self.assertFalse([k for k in header if k.startswith('Plain:')])
        self.assertEqual(header.index('How do you cope?: Other (specify)'), header.index('How do you cope?') + 1)

        geo = json.loads(archive.read([n for n in names if n.endswith('.geojson') and 'Spot' in n][0]))
        props = geo['features'][0]['properties']
        self.assertEqual((props['Type'], props['Type: Other']), ('Other', 'graffiti'))

        objects_csv = [n for n in names if n.split('/')[-1].startswith('objects_')][0]
        orows = list(csv.DictReader(io.StringIO(archive.read(objects_csv).decode('utf-8'))))
        self.assertEqual((orows[0]['Fix'], orows[0]['Fix: Other']), ('Other', 'broken bench'))

    def test_creator_sees_text_inline_and_charts_count_by_code(self):
        """
        GIVEN a session whose choice answer and geo sub-answer picked the write-in option with text
        WHEN the Responses formatters and the chart stats run
        THEN the cell and drawer read "Other (specify): wet towel", the sub-answer attribute reads
             "Other: graffiti", and the chart counts the option by code with no text
        """
        from survey.analytics import SurveyAnalyticsService
        s1 = self._session()
        a = Answer.objects.create(survey_session=s1, question=self.q_cope, selected_choices=[4], text='wet towel')
        point = Answer.objects.create(survey_session=s1, question=self.q_point, point=Point(74.6, 42.87, srid=4326))
        sub = Answer.objects.create(survey_session=s1, question=self.sub_type, parent_answer_id=point,
                                    selected_choices=[3], text='graffiti')
        service = SurveyAnalyticsService(self.survey)
        self.assertEqual(service._format_cell(a), 'Other (specify): wet towel')
        self.assertEqual(service._subanswer_display(sub), 'Other: graffiti')
        self.assertIn('Other (specify): wet towel', json.dumps(service.format_session_answers(s1), default=str))
        stats = service._stats_choices(self.q_cope)
        self.assertEqual(stats['choice_counts'][stats['choice_codes'].index(4)], 1)
        self.assertNotIn('wet towel', json.dumps(stats))

    def test_public_results_and_object_aggregates_carry_no_text(self):
        """
        GIVEN three sessions that picked the write-in option with distinct texts, and an object
             answer with a write-in
        WHEN the public chart block and the object aggregates are built
        THEN the option is counted by code and none of the texts appears in either payload
        """
        from survey.public_results import PublicResultsService
        from survey.object_stats import object_aggregates
        texts = ['alpha one', 'beta two', 'gamma three']
        for t in texts:
            Answer.objects.create(survey_session=self._session(), question=self.q_cope, selected_choices=[4], text=t)
        page = PublicResultsPage.objects.create(survey=self.survey, slug='other-prs', is_published=True)
        block = PublicResultsBlock.objects.create(page=page, block_type='chart', question=self.q_cope, order=0)
        payload = PublicResultsService(page)._build_block(block)
        self.assertEqual({i['code']: i['display'] for i in payload['items']}[4], '3')
        dumped = json.dumps(payload)
        for t in texts:
            self.assertNotIn(t, dumped)
        obj = self.layer.items.get(key='1')
        Answer.objects.create(survey_session=self._session(), question=self.sub_obj, layer_object=obj,
                              selected_choices=[4], text='delta four')
        agg = json.dumps(object_aggregates(self.q_obj), default=str)
        self.assertIn('"4": 1', agg)
        self.assertNotIn('delta four', agg)

    def test_editor_keeps_one_flag_reopens_it_and_hoists_add_choice_row(self):
        """
        GIVEN a creator who posts a choice question with two flagged options
        WHEN the question is saved and reopened in the modal
        THEN only the first flag is stored, the modal reloads rows with the flag, the choices table
             has the Other column, and addChoiceRow is a hoisted declaration, not an assignment
        """
        self._login_editor()
        choices = [{"code": 1, "name": "A"}, {"code": 2, "name": "B", "other": True}, {"code": 3, "name": "C", "other": True}]
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Which?', 'input_type': 'choice', 'color': '#000000', 'choices_json': json.dumps(choices)},
        )
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(survey_section=self.section, name='Which?')
        self.assertEqual([c.get('other') for c in q.choices], [None, True, None])
        html = self.client.get(reverse('editor_question_edit', args=[self.survey.uuid, q.id])).content.decode()
        self.assertIn('addChoiceRow(choice.code, choice.name, !!choice.other, choice.icon, choice.group, choice.color)', html)
        self.assertIn('"other": true', html)
        self.assertIn('class="choice-other-cell"', html)
        self.assertIn('function addChoiceRow(code, name, other, icon, group, color)', html)
        self.assertNotIn('window.addChoiceRow = function', html)

    def test_live_preview_clamps_and_renders_the_write_in(self):
        """
        GIVEN an unsaved choice draft with two flagged options
        WHEN the modal posts it to the live preview endpoint
        THEN one write-in field renders, under the first flagged option, and the frame loads the reveal script
        """
        self._login_editor()
        response = self.client.post(
            reverse('editor_question_preview_live', args=[self.survey.uuid, self.section.id]),
            {'input_type': 'choice', 'name': 'Which?',
             'choices_json': json.dumps([{"code": 1, "name": "A", "other": True}, {"code": 2, "name": "B", "other": True}])},
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(html.count('class="other-writein"'), 1)
        self.assertIn('data-other-code="1"', html)
        self.assertRegex(html, r'js/other_option(\.[0-9a-f]+)?\.js')

    def test_zip_and_draft_copy_keep_the_flag(self):
        """
        GIVEN a survey whose choice question carries the write-in flag
        WHEN it is exported to ZIP, re-imported, and cloned for a draft
        THEN both copies keep other: true on the same option
        """
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, 'structure')
        buf.seek(0)
        data = json.loads(zipfile.ZipFile(buf).read('survey.json'))
        cope = [q for s in data['survey']['sections'] for q in s['questions'] if 'How do you cope?' in json.dumps(q['name'])][0]
        self.assertTrue(cope['choices'][2]['other'])
        buf.seek(0)
        self.survey.name = 'other_survey_old'
        self.survey.save()
        imported, _ = import_survey_from_zip(buf)
        iq = Question.objects.get(survey_section__survey_header=imported, name='How do you cope?')
        self.assertEqual(iq.other_choice_code(), 4)
        draft = clone_survey_for_draft(self.survey)
        dq = Question.objects.get(survey_section__survey_header=draft, code='Q_COPE')
        self.assertEqual(dq.other_choice_code(), 4)
