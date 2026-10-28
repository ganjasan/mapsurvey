"""Tests for the `object-answers` capability (openspec/specs/object-answers/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from io import BytesIO
import json
import re
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, PublicResultsPage, PublicResultsBlock
from survey.analytics import SurveyAnalyticsService
from django.db.utils import IntegrityError
from survey.tests.helpers import _objects_layer


class LayerObjectsRespondentTest(TestCase):
    """The list block, the bound-layer metadata and answers about objects
    (specs layer-objects-question, object-answers, reference-overlay-layers)."""

    def setUp(self):
        self.org = Organization.objects.create(name="LOR Org")
        self.survey = SurveyHeader.objects.create(
            name="lor_survey", organization=self.org, redirect_url="/thanks/",
            status='published', available_languages=['en'],
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        self.next_section = SurveySection.objects.create(
            survey_header=self.survey, name="s2", title="S2", code="S2",
        )
        self.section.next_section = self.next_section
        self.section.save()
        Question.objects.create(survey_section=self.next_section, code="LR100", name="Later", input_type="text", order_number=1)
        self.layer = _objects_layer(self.survey, name="Sites", key_field='zone_id', label_field='name')
        for obj, cat in zip(self.layer.items.order_by('key'), ('Parks', 'Parks', 'Roads')):
            obj.category = cat
            obj.save()
        from survey.layers import rebuild_layer
        rebuild_layer(self.layer)
        self.q = Question.objects.create(
            survey_section=self.section, code="LR001", name="Objects", input_type="layer_objects",
            layer=self.layer, min_objects=1, order_number=1,
        )
        self.rating = Question.objects.create(
            survey_section=self.section, code="LR002", name="Rate", input_type="rating",
            parent_question_id=self.q, order_number=1, choices=[{"code": i, "name": str(i)} for i in range(1, 6)],
        )
        self.thumbs = Question.objects.create(
            survey_section=self.section, code="LR003", name="Build?", input_type="thumbs",
            parent_question_id=self.q, order_number=2,
        )
        self.thumbs.choices = self.thumbs.thumbs_choices()
        self.thumbs.save()
        self.comment = Question.objects.create(
            survey_section=self.section, code="LR004", name="Comment", input_type="text",
            parent_question_id=self.q, order_number=3,
        )
        self.url = f'/surveys/{self.survey.uuid}/{self.section.name}/'

    def _start(self):
        self.client.get(f'/surveys/{self.survey.uuid}/')
        return self.client.get(self.url)

    def test_block_and_bound_layer_metadata_render(self):
        """
        GIVEN a section with an Objects-on-the-map question bound to a layer
        WHEN the respondent opens it
        THEN the block shell carries the code, layer, minimum and search mode; the layer
             metadata marks the layer bound with an object URL; the sub-question form is
             pre-rendered for the popup; and no object geometry is inlined
        """
        html = self._start().content.decode()
        self.assertIn('data-layer-objects', html)
        self.assertIn(f'data-layer-id="{self.layer.pk}"', html)
        self.assertIn('data-min-objects="1"', html)
        self.assertIn('data-search="auto"', html)
        self.assertIn('"bound": true', html)
        self.assertIn('/objects/KEY/', html)
        self.assertIn('initLayerObjectBlocks', html)
        # The sub-question form is pre-rendered into the sq-forms json_script
        # (json_script escapes quotes, so match on the names, not the markup).
        forms = json.loads(re.search(r'id="sq-forms-data"[^>]*>(.*?)</script>', html, re.S).group(1))
        self.assertIn('LR002', forms['LR001'])          # rating sub-question
        self.assertIn('thumbs__option', forms['LR001'])  # thumbs widget
        self.assertNotIn('"coordinates"', html)

    def test_display_only_question_shows_the_layer_and_collects_nothing(self):
        """
        GIVEN an Objects question in legend mode with min_objects=2 but no sub-questions
        WHEN the respondent opens the section and submits it without touching an object
        THEN the block renders as a legend line with min 0 and no counter, the layer is visible,
             and the POST moves on — nothing was there to answer (spec layer-objects-question)
        """
        Question.objects.filter(parent_question_id=self.q).delete()
        self.q.panel_mode = 'legend'
        self.q.min_objects = 2
        self.q.save()
        self._start()
        html = self.client.get(self.url).content.decode()
        self.assertIn('data-panel-mode="legend"', html)
        self.assertIn('data-collects="0"', html)
        self.assertIn('data-min-objects="0"', html)
        self.assertIn('data-lo-toggle', html)
        self.assertNotIn('class="layer-objects__list"', html)
        self.assertIn('data-visible-layers="[%d]"' % self.layer.pk, html)
        response = self.client.post(self.url, {})
        self.assertIn(response.status_code, (200, 302))
        self.assertFalse(Answer.objects.filter(layer_object__isnull=False).exists())

    def test_object_answers_are_stored_one_row_per_object_and_subquestion(self):
        """
        GIVEN a respondent who answered about objects 1 and 2 (rating, thumbs, comment)
        WHEN the section POSTs obj__<key>__<code> fields
        THEN one Answer per (object, sub-question) exists with layer_object set and no parent answer
        """
        self._start()
        response = self.client.post(self.url, {
            'obj__1__LR002': '4', 'obj__1__LR003': '1', 'obj__1__LR004': 'Keep the oaks',
            'obj__2__LR002': '2', 'obj__2__LR003': '0',
        })
        self.assertIn(response.status_code, (200, 302))
        rows = Answer.objects.filter(layer_object__isnull=False).select_related('layer_object', 'question')
        self.assertEqual(rows.count(), 5)
        by = {(a.layer_object.key, a.question.code): a for a in rows}
        self.assertEqual(by[('1', 'LR002')].selected_choices, [4])
        self.assertEqual(by[('1', 'LR003')].selected_choices, [1])
        self.assertEqual(by[('1', 'LR004')].text, 'Keep the oaks')
        self.assertEqual(by[('2', 'LR003')].selected_choices, [0])
        self.assertTrue(all(a.parent_answer_id_id is None for a in rows))

    def test_resubmit_replaces_and_unknown_keys_are_ignored(self):
        """
        GIVEN stored object answers
        WHEN the section is POSTed again with a changed rating, a dropped object and a bogus key
        THEN the rows reflect the latest POST only and the bogus key stores nothing
        """
        self._start()
        self.client.post(self.url, {'obj__1__LR002': '4', 'obj__2__LR002': '2'})
        self.client.post(self.url, {'obj__1__LR002': '5', 'obj__zzz__LR002': '3', 'obj__1__NOPE': 'x'})
        rows = list(Answer.objects.filter(layer_object__isnull=False))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].layer_object.key, rows[0].selected_choices), ('1', [5]))

    def test_hidden_block_discards_object_answers(self):
        """
        GIVEN the Objects question is hidden by a visibility rule for this session
        WHEN the POST still carries obj__ fields
        THEN nothing is stored
        """
        controller = Question.objects.create(
            survey_section=self.section, code="LR000", name="Interested?", input_type="choice", order_number=0,
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
        )
        self.q.visibility_rule = {"question_code": "LR000", "choice_codes": [1]}
        self.q.save()
        self._start()
        self.client.post(self.url, {'LR000': '2', 'obj__1__LR002': '4'})
        self.assertEqual(Answer.objects.filter(layer_object__isnull=False).count(), 0)

    def test_session_restore_carries_object_answers_to_the_page(self):
        """
        GIVEN a respondent who answered about object 1 and moved on
        WHEN they come back to the section
        THEN the page embeds the stored values keyed by object and sub-question for the popup and ✓ state
        """
        self._start()
        self.client.post(self.url, {'obj__1__LR002': '4', 'obj__1__LR004': 'Keep the oaks'})
        html = self.client.get(self.url).content.decode()
        self.assertIn('id="object-answers-data"', html)
        data = json.loads(re.search(r'id="object-answers-data"[^>]*>(.*?)</script>', html, re.S).group(1))
        self.assertEqual(data['LR001']['1']['LR002'], ['4'])
        self.assertEqual(data['LR001']['1']['LR004'], ['Keep the oaks'])

    def test_deleting_an_object_removes_its_answers(self):
        """
        GIVEN answers about object 1
        WHEN the object is deleted
        THEN its answers cascade away and other objects' answers stay
        """
        self._start()
        self.client.post(self.url, {'obj__1__LR002': '4', 'obj__2__LR002': '2'})
        self.layer.items.get(key='1').delete()
        self.assertEqual(list(Answer.objects.filter(layer_object__isnull=False).values_list('layer_object__key', flat=True)), ['2'])

    def test_unique_constraint_per_session_question_object(self):
        """
        GIVEN one stored answer for (session, sub-question, object)
        WHEN a second identical row is inserted directly
        THEN the database refuses it, while legacy rows without an object are unconstrained
        """
        from django.db import IntegrityError, transaction
        session = SurveySession.objects.create(survey=self.survey)
        obj = self.layer.items.get(key='1')
        Answer.objects.create(survey_session=session, question=self.rating, layer_object=obj, selected_choices=[3])
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Answer.objects.create(survey_session=session, question=self.rating, layer_object=obj, selected_choices=[4])
        Answer.objects.create(survey_session=session, question=self.rating, selected_choices=[1])
        Answer.objects.create(survey_session=session, question=self.rating, selected_choices=[2])

    def test_unbound_layer_keeps_read_only_popup_semantics(self):
        """
        GIVEN a second layer not bound to any question, with popups enabled
        WHEN the page renders the layer metadata
        THEN that layer is marked unbound and keeps show_popups, so the factory binds the read-only popup
        """
        other = _objects_layer(self.survey, name="Boundary", show_popups=True)
        html = self._start().content.decode()
        data = json.loads(re.search(r'id="ref-layers-data"[^>]*>(.*?)</script>', html, re.S).group(1))
        by_id = {d['id']: d for d in data}
        self.assertEqual((by_id[self.layer.pk]['bound'], by_id[other.pk]['bound'], by_id[other.pk]['show_popups']), (True, False, True))


class ObjectAnswersReadTest(TestCase):
    """Export, Responses aggregates and the public block (spec object-answers, group 5)."""

    def setUp(self):
        self.org = Organization.objects.create(name="OAR Org")
        self.owner = User.objects.create_user(username='oarowner', password='pw12345678')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="oar_survey", organization=self.org, redirect_url="/thanks/",
            status='published', available_languages=['en'], created_by=self.owner,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        self.layer = _objects_layer(self.survey, name="Sites", key_field='zone_id', label_field='name')
        self.q = Question.objects.create(
            survey_section=self.section, code="OA001", name="Objects", input_type="layer_objects",
            layer=self.layer, order_number=1,
        )
        self.rating = Question.objects.create(
            survey_section=self.section, code="OA002", name="Rate", input_type="rating",
            parent_question_id=self.q, order_number=1, choices=[{"code": i, "name": str(i)} for i in range(1, 6)],
        )
        self.thumbs = Question.objects.create(
            survey_section=self.section, code="OA003", name="Build?", input_type="thumbs",
            parent_question_id=self.q, order_number=2,
        )
        self.thumbs.choices = self.thumbs.thumbs_choices()
        self.thumbs.save()
        self.comment = Question.objects.create(
            survey_section=self.section, code="OA004", name="Comment", input_type="text",
            parent_question_id=self.q, order_number=3,
        )
        self.objects = {o.key: o for o in self.layer.items.all()}
        # 3 sessions about object 1 (ratings 4,5,3; thumbs up,up,down; one comment),
        # 1 session about object 2 (rating 2, thumbs down), nothing about 3.
        self.sessions = [SurveySession.objects.create(survey=self.survey) for _ in range(3)]
        for s, r, t in zip(self.sessions, (4, 5, 3), (1, 1, 0)):
            Answer.objects.create(survey_session=s, question=self.rating, layer_object=self.objects['1'], selected_choices=[r])
            Answer.objects.create(survey_session=s, question=self.thumbs, layer_object=self.objects['1'], selected_choices=[t])
        Answer.objects.create(survey_session=self.sessions[0], question=self.comment, layer_object=self.objects['1'], text='Keep the oaks')
        Answer.objects.create(survey_session=self.sessions[0], question=self.rating, layer_object=self.objects['2'], selected_choices=[2])
        Answer.objects.create(survey_session=self.sessions[0], question=self.thumbs, layer_object=self.objects['2'], selected_choices=[0])

    def test_aggregates_per_object(self):
        """
        GIVEN the answers above
        WHEN per-object aggregates are computed
        THEN object 1 has 3 answers, mean 4.0, up 2 / down 1, one comment; object 3 has none
        """
        from survey.object_stats import object_aggregates, headline, flat_properties
        agg = object_aggregates(self.q)
        one = agg['1']
        self.assertEqual(one['answers'], 3)
        self.assertEqual(one['subs']['OA002']['mean'], 4.0)
        self.assertEqual((one['subs']['OA003']['up'], one['subs']['OA003']['down']), (2, 1))
        self.assertEqual(one['subs']['OA004']['count'], 1)
        self.assertEqual(one['subs']['OA004']['values'], [])
        self.assertEqual(headline(one), '3 · 4.0★ · 👍 2/1')
        self.assertEqual(agg['3']['answers'], 0)
        props = flat_properties(one)
        self.assertEqual((props['answers'], props['OA002_mean'], props['OA003_up'], props['OA003_down']), (3, 4.0, 2, 1))
        self.assertNotIn('Keep the oaks', json.dumps(props))

    def test_export_zip_has_object_csv_and_results_geojson(self):
        """
        GIVEN the owner downloads the responses ZIP
        WHEN the archive is read
        THEN objects_OA001.csv has one row per (session, object) with the sub-question columns,
             and layers/Sites.results.geojson carries per-object aggregates and no text
        """
        self.client.login(username='oarowner', password='pw12345678')
        response = self.client.get(reverse('download_data', kwargs={'survey_slug': str(self.survey.uuid)}))
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(BytesIO(response.content)) as zf:
            names = zf.namelist()
            csv_name = next(n for n in names if n.endswith('objects_OA001.csv'))
            geo_name = next(n for n in names if n.endswith('layers/Sites.results.geojson'))
            csv_text = zf.read(csv_name).decode()
            geo = json.loads(zf.read(geo_name))
        rows = [r for r in csv_text.splitlines() if r.strip()]
        self.assertEqual(len(rows), 1 + 4)   # header + 3 sessions about object 1 + 1 about object 2
        self.assertIn('object_key', rows[0])
        self.assertIn('Rate', rows[0])
        self.assertIn('Build?', rows[0])
        self.assertIn('Keep the oaks', csv_text)
        self.assertIn(',up,', csv_text)
        by_key = {f['properties']['_key']: f['properties'] for f in geo['features']}
        self.assertEqual((by_key['1']['answers'], by_key['1']['OA002_mean'], by_key['1']['OA003_up']), (3, 4.0, 2))
        self.assertEqual(by_key['3']['answers'], 0)
        self.assertNotIn('Keep the oaks', json.dumps(geo))

    def test_responses_stats_and_map_badges(self):
        """
        GIVEN the analytics service and the Responses page
        WHEN the question stats and layer metadata are built
        THEN the layer_objects question yields an 'objects' stat with per-object rows,
             and the bound layer's metadata carries badges and the sessions to select
        """
        service = SurveyAnalyticsService(self.survey)
        stat = service.get_question_stats(self.q)
        self.assertEqual(stat['type'], 'objects')
        first = stat['object_rows'][0]
        self.assertEqual((first['key'], first['answers'], first['headline']), ('1', 3, '3 · 4.0★ · 👍 2/1'))
        self.assertEqual(sorted(json.loads(first['sessions_json'])), sorted(s.id for s in self.sessions))
        from survey.analytics_views import _map_layers_with_object_stats
        metas = _map_layers_with_object_stats(self.survey)
        stats = metas[0]['object_stats']
        self.assertEqual(stats['1']['headline'], '3 · 4.0★ · 👍 2/1')
        self.assertEqual(stats['2']['answers'], 1)
        self.assertNotIn('3', stats)
        self.client.login(username='oarowner', password='pw12345678')
        html = self.client.get(reverse('editor_survey_analytics', kwargs={'survey_uuid': self.survey.uuid})).content.decode()
        self.assertIn('objects-stat-row', html)
        self.assertIn('object_stats', html)

    def test_public_results_objects_block_respects_k(self):
        """
        GIVEN a public results page with k = 3 and an objects block
        WHEN it renders
        THEN object 1 (3 answers) shows its aggregates, object 2 (1 answer) is masked,
             object 3 shows 0, and no comment text appears anywhere in the payload
        """
        from survey.models import PublicResultsPage, PublicResultsBlock
        from survey.public_results import PublicResultsService, block_type_for_question
        self.assertEqual(block_type_for_question(self.q), 'objects')
        page = PublicResultsPage.objects.create(survey=self.survey, slug="oar", is_published=True, k_anonymity_threshold=3)
        PublicResultsBlock.objects.create(page=page, block_type="objects", question=self.q, order=0)
        blocks = PublicResultsService(page).build_blocks()
        block = blocks[0]
        self.assertEqual(block['data_type'], 'objects')
        rows = {r['key']: r for r in block['rows']}
        self.assertEqual(rows['1']['answers']['display'], '3')
        self.assertTrue(rows['2']['answers']['masked'])
        self.assertEqual(rows['2']['subs'][0]['display'], '<3')
        self.assertEqual(rows['3']['answers']['display'], '0')
        self.assertEqual([s['code'] for s in block['sub_questions']], ['OA002', 'OA003'])
        self.assertNotIn('Keep the oaks', json.dumps(block))
        html = self.client.get(reverse('public_results', kwargs={'slug': 'oar'})).content.decode()
        self.assertIn('objects-holder', html)
        self.assertIn('renderObjects', html)
