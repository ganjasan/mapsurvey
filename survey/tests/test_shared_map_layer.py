"""Tests for the `shared-map-layer` capability (openspec/specs/shared-map-layer/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from io import BytesIO
import json
import zipfile
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.versioning import clone_survey_for_draft
import csv
from survey.tests.helpers import _mark, _objects_layer, _react, _shared_map_survey


class SharedMapModelTest(TestCase):
    """Fields and validation (spec shared-map-layer, task 1)."""

    def setUp(self):
        self.f = _shared_map_survey()

    def test_defaults(self):
        """
        GIVEN a layer created without shared-map fields
        WHEN it is read back
        THEN it is an upload layer with tallies on, comments off, no approval gate
        """
        from survey.models import SurveyMapLayer
        layer = SurveyMapLayer.objects.create(survey=self.f['survey'], name="Plain", geojson='{}')
        self.assertEqual((layer.source, layer.show_tallies, layer.show_comments, layer.approve_first),
                         ('upload', True, False, False))

    def test_clean_rejects_unknown_or_non_geo_code(self):
        """
        GIVEN a question layer
        WHEN its source code names nothing, or a text question
        THEN clean() raises on source_question_code; a geo code passes
        """
        from django.core.exceptions import ValidationError
        layer = self.f['layer']
        layer.full_clean()
        for code in ('NOPE', 'WHY', ''):
            layer.source_question_code = code
            with self.assertRaises(ValidationError):
                layer.clean()


class SharedMapMaterialisationTest(TestCase):
    """Marks become objects; keys survive re-submits (spec shared-map-layer, task 2)."""

    def setUp(self):
        self.f = _shared_map_survey()
        self.a = SurveySession.objects.create(survey=self.f['survey'])
        self.b = SurveySession.objects.create(survey=self.f['survey'])

    def _sync(self, session):
        from survey.layers import sync_question_layer
        return sync_question_layer(self.f['layer'], session)

    def test_first_submit_creates_objects(self):
        """
        GIVEN session A stored two marks, one with a WHY answer
        WHEN the layer is synced for A
        THEN two objects keyed sA-1, sA-2 exist, titled by WHY, visible, linked to A
        """
        _mark(self.a, self.f['q1'], 13.4, 52.5, why="Bin by the gate")
        _mark(self.a, self.f['q1'], 13.5, 52.6)
        self.assertEqual(self._sync(self.a), 2)
        objs = {o.key: o for o in self.f['layer'].items.all()}
        self.assertEqual(set(objs), {f's{self.a.pk}-1', f's{self.a.pk}-2'})
        first = objs[f's{self.a.pk}-1']
        self.assertEqual((first.title, first.status, first.source_session_id), ("Bin by the gate", 'visible', self.a.pk))
        self.assertIsNotNone(first.source_answer_id)
        self.assertEqual(objs[f's{self.a.pk}-2'].title, '')

    def test_backfill_materialises_marks_stored_before_the_layer_existed(self):
        """
        GIVEN two sessions stored marks (one is on hold) while no `question` layer existed,
              and a third session answered only the WHY sub-question
        WHEN the layer is backfilled
        THEN objects exist for both marking sessions under the same keys a section POST would
             use, the cached geojson carries the clean session's mark, and a second backfill
             creates no duplicates
        """
        from survey.layers import backfill_question_layer
        _mark(self.a, self.f['q1'], 13.4, 52.5, why="Early bird")
        self.b.validation_status = 'on_hold'
        self.b.save()
        _mark(self.b, self.f['q1'], 13.5, 52.6)
        self.f['layer'].items.all().delete()
        self.assertEqual(backfill_question_layer(self.f['layer']), 2)
        keys = set(self.f['layer'].items.values_list('key', flat=True))
        self.assertEqual(keys, {f's{self.a.pk}-1', f's{self.b.pk}-1'})
        self.f['layer'].refresh_from_db()
        titles = [ft['properties'].get('_title') for ft in json.loads(self.f['layer'].geojson)['features']]
        self.assertEqual(titles, ["Early bird"])
        self.assertEqual(backfill_question_layer(self.f['layer']), 2)
        self.assertEqual(self.f['layer'].items.count(), 2)

    def test_resubmit_keeps_key_and_reactions(self):
        """
        GIVEN A's mark materialised and B reacted 👍 to it
        WHEN A's answers are deleted and re-inserted (as the section POST does) and the layer re-synced
        THEN the same key still exists with the new geometry and B's reaction is still attached
        """
        _mark(self.a, self.f['q1'], 13.4, 52.5, why="v1")
        self._sync(self.a)
        obj = self.f['layer'].items.get(key=f's{self.a.pk}-1')
        _react(self.b, self.f['obj'], obj, up=True)
        Answer.objects.filter(survey_session=self.a).delete()
        _mark(self.a, self.f['q1'], 13.9, 52.9, why="v2")
        self._sync(self.a)
        obj.refresh_from_db()
        self.assertEqual(obj.title, "v2")
        self.assertAlmostEqual(obj.geometry.x, 13.9)
        self.assertEqual(obj.answers.count(), 1)
        self.assertEqual(self.f['layer'].items.count(), 1)

    def test_fewer_features_drops_surplus_and_its_reactions(self):
        """
        GIVEN A had two marks, B reacted to the second
        WHEN A re-submits with one mark
        THEN sA-2 and B's reaction on it are gone, sA-1 remains
        """
        _mark(self.a, self.f['q1'], 13.4, 52.5)
        _mark(self.a, self.f['q1'], 13.5, 52.6)
        self._sync(self.a)
        second = self.f['layer'].items.get(key=f's{self.a.pk}-2')
        _react(self.b, self.f['obj'], second, up=False)
        Answer.objects.filter(survey_session=self.a).delete()
        _mark(self.a, self.f['q1'], 13.4, 52.5)
        self._sync(self.a)
        self.assertEqual(list(self.f['layer'].items.values_list('key', flat=True)), [f's{self.a.pk}-1'])
        self.assertFalse(Answer.objects.filter(survey_session=self.b, layer_object__isnull=False).exists())

    def test_approve_first_creates_pending(self):
        """
        GIVEN the layer requires approval
        WHEN A's mark is materialised
        THEN the object is pending
        """
        self.f['layer'].approve_first = True
        self.f['layer'].save()
        _mark(self.a, self.f['q1'], 13.4, 52.5)
        self._sync(self.a)
        self.assertEqual(self.f['layer'].items.get().status, 'pending')

    def test_section_post_materialises(self):
        """
        GIVEN a respondent opened the section (session created)
        WHEN they POST a point with a WHY property
        THEN the layer has their object titled by WHY
        """
        url = reverse('section', kwargs={'survey_slug': str(self.f['survey'].uuid), 'section_name': 's1'})
        self.client.get(url)
        feature = json.dumps({"type": "Feature", "geometry": {"type": "Point", "coordinates": [13.4, 52.5]},
                              "properties": {"question_id": "Q1", "WHY": ["Posted why"]}})
        self.client.post(url, {'Q1': feature + '|'})
        sid = self.client.session['survey_session_id']
        obj = self.f['layer'].items.get(source_session_id=sid)
        self.assertEqual((obj.key, obj.title), (f's{sid}-1', "Posted why"))

    def test_older_version_feeds_canonical(self):
        """
        GIVEN an archived version of the survey with its own copy of Q1
        WHEN a session on that version is synced
        THEN the canonical layer gets the object
        """
        version = SurveyHeader.objects.create(name="v1", organization=self.f['survey'].organization, redirect_url="/t/",
                                              status='archived', canonical_survey=self.f['survey'])
        vsec = SurveySection.objects.create(survey_header=version, name="s1", title="S1", code="S1", is_head=True)
        vq1 = Question.objects.create(survey_section=vsec, code="Q1", name="Where?", input_type="point", order_number=1)
        vs = SurveySession.objects.create(survey=version)
        Answer.objects.create(survey_session=vs, question=vq1, point=Point(1, 2))
        self.assertEqual(self._sync(vs), 1)
        self.assertEqual(self.f['layer'].items.get().source_session_id, vs.pk)


class SharedMapEndpointTest(TestCase):
    """What a respondent receives (spec shared-map-layer, task 3)."""

    def setUp(self):
        from survey.layers import sync_question_layer
        self.f = _shared_map_survey()
        self.url = reverse('section', kwargs={'survey_slug': str(self.f['survey'].uuid), 'section_name': 's1'})
        self.layer_url = reverse('survey_layer_geojson', kwargs={'survey_slug': str(self.f['survey'].uuid), 'layer_id': self.f['layer'].pk})
        # Respondent A: a real client session with one mark.
        self.client.get(self.url)
        self.a = SurveySession.objects.get(pk=self.client.session['survey_session_id'])
        _mark(self.a, self.f['q1'], 13.4, 52.5, why="A's bin")
        sync_question_layer(self.f['layer'], self.a)
        # Respondent B: a bare session with one mark.
        self.b = SurveySession.objects.create(survey=self.f['survey'])
        _mark(self.b, self.f['q1'], 13.5, 52.6, why="B's bin")
        sync_question_layer(self.f['layer'], self.b)
        self.a_key, self.b_key = f's{self.a.pk}-1', f's{self.b.pk}-1'

    def _keys(self, response):
        return [f['properties']['_key'] for f in json.loads(response.content)['features']]

    def _card_url(self, key):
        return reverse('survey_layer_object', kwargs={'survey_slug': str(self.f['survey'].uuid),
                                                      'layer_id': self.f['layer'].pk, 'key': key})

    def test_own_marks_absent_no_store(self):
        """
        GIVEN A and B each have a mark
        WHEN A fetches the layer
        THEN only B's mark is there, the response is no-store, and the card for A's own mark is 404
        """
        response = self.client.get(self.layer_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._keys(response), [self.b_key])
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(self.client.get(self._card_url(self.a_key)).status_code, 404)
        self.assertEqual(self.client.get(self._card_url(self.b_key)).status_code, 200)

    def test_etag_varies_per_session_and_revalidates(self):
        """
        GIVEN two respondents
        WHEN each fetches the layer
        THEN their ETags differ, and a matching If-None-Match gets 304
        """
        first = self.client.get(self.layer_url)
        other = Client()
        other.get(self.url)
        second = other.get(self.layer_url)
        self.assertNotEqual(first['ETag'], second['ETag'])
        self.assertEqual(self.client.get(self.layer_url, HTTP_IF_NONE_MATCH=first['ETag']).status_code, 304)

    def test_unclean_and_moderated_marks_absent(self):
        """
        GIVEN B's session is on hold, and C's mark is hidden, D's pending
        WHEN A fetches the layer
        THEN none of them is served, and B's reaction no longer counts
        """
        from survey.layers import sync_question_layer
        c = SurveySession.objects.create(survey=self.f['survey'])
        d = SurveySession.objects.create(survey=self.f['survey'])
        for s in (c, d):
            _mark(s, self.f['q1'], 14, 53)
            sync_question_layer(self.f['layer'], s)
        self.f['layer'].items.filter(source_session=c).update(status='hidden')
        self.f['layer'].items.filter(source_session=d).update(status='pending')
        self.b.validation_status = 'on_hold'
        self.b.save()
        self.assertEqual(self._keys(self.client.get(self.layer_url)), [])
        for key in (self.b_key, f's{c.pk}-1', f's{d.pk}-1'):
            self.assertEqual(self.client.get(self._card_url(key)).status_code, 404)

    def test_tallies_and_comments_follow_settings(self):
        """
        GIVEN B's mark has 2 👍, 1 👎 and 2 comments (one hidden), reacted by clean sessions
        WHEN A fetches the layer and the card with 👍/👎 shared, then with 👍/👎 unshared and comments shared
        THEN counts and comments appear exactly as far as the sub-questions share them, and the hidden comment never does
        """
        obj = self.f['layer'].items.get(key=self.b_key)
        for up in (True, True, False):
            _react(SurveySession.objects.create(survey=self.f['survey']), self.f['obj'], obj, up=up)
        _react(SurveySession.objects.create(survey=self.f['survey']), self.f['obj'], obj, comment="Bags every morning")
        _react(SurveySession.objects.create(survey=self.f['survey']), self.f['obj'], obj, comment="rude words")
        Answer.objects.filter(text="rude words").update(hidden=True)
        rejected = SurveySession.objects.create(survey=self.f['survey'], validation_status='not_approved')
        _react(rejected, self.f['obj'], obj, up=True)

        # Comments are not shared yet, so their count is not either.
        props = json.loads(self.client.get(self.layer_url).content)['features'][0]['properties']
        self.assertEqual((props['tally_up'], props['tally_down'], props['comment_count']), (2, 1, 0))
        card = json.loads(self.client.get(self._card_url(self.b_key)).content)
        self.assertEqual(card['tallies'], {'up': 2, 'down': 1, 'comments': 0})
        self.assertNotIn('comments', card)

        Question.objects.filter(pk=self.f['vote'].pk).update(share_with_respondents=False)
        Question.objects.filter(pk=self.f['cmt'].pk).update(share_with_respondents=True)
        props = json.loads(self.client.get(self.layer_url).content)['features'][0]['properties']
        self.assertNotIn('tally_up', props)
        card = json.loads(self.client.get(self._card_url(self.b_key)).content)
        self.assertNotIn('tallies', card)
        self.assertEqual(card['comments'], ["Bags every morning"])

    def test_section_renders_hint_and_no_total(self):
        """
        GIVEN the section with the Objects question bound to a question layer
        WHEN a respondent renders it
        THEN the block says own marks are not listed and shows no object total
        """
        html = self.client.get(self.url).content.decode()
        self.assertIn('Your own marks are not in this list', html)
        self.assertIn('data-layer-source="question"', html)
        self.assertNotIn('data-lo-total>', html)

    def test_creator_sees_everything(self):
        """
        GIVEN the owner is logged in
        WHEN they fetch the layer and a pending mark's card
        THEN every clean mark of every status is served with its status, and the card carries comments
        """
        from django.contrib.auth.models import User
        owner = User.objects.create_user('owner', 'o@example.com', 'pw')
        Membership.objects.create(user=owner, organization=self.f['survey'].organization, role='admin')
        from survey.layers import rebuild_layer
        self.f['layer'].items.filter(source_session=self.b).update(status='pending')
        rebuild_layer(self.f['layer'])   # what the moderation endpoint does after a status change
        self.client.login(username='owner', password='pw')
        features = json.loads(self.client.get(self.layer_url).content)['features']
        self.assertEqual(sorted(f['properties']['_key'] for f in features), sorted([self.a_key, self.b_key]))
        self.assertEqual({f['properties']['_status'] for f in features}, {'visible', 'pending'})
        card = json.loads(self.client.get(self._card_url(self.b_key)).content)
        self.assertEqual(card['status'], 'pending')
        self.assertIn('comments', card)


class SharedMapEditorTest(TestCase):
    """The Objects-on-the-map form is the one door to a layer from answers and
    its settings; the layer card only names it; the object editor is read-only;
    the source question cannot be deleted (spec survey-editor delta, task 5)."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.f = _shared_map_survey("shared_map_editor")
        self.f['survey'].status = 'draft'
        self.f['survey'].save()
        self.owner = User.objects.create_user('edowner', 'e@example.com', 'pw')
        Membership.objects.create(user=self.owner, organization=self.f['survey'].organization, role='admin')
        self.client.login(username='edowner', password='pw')
        self.uuid = self.f['survey'].uuid
        self.create_url = reverse('editor_question_create', kwargs={'survey_uuid': self.uuid, 'section_id': self.f['section'].pk})

    def _post(self, url, **extra):
        data = {'name': 'React', 'input_type': 'layer_objects', 'subtext': '', 'display_style': 'default',
                'color': '#000000', 'choices_json': '[]', 'min_objects': '0', 'objects_search': 'auto'}
        data.update(extra)
        return self.client.post(url, data)

    def test_picker_lists_layers_and_geo_sources(self):
        """
        GIVEN a survey with one question layer (fed by Q1) and a second geo question Q2 without one
        WHEN the create modal renders for an Objects question
        THEN the picker lists the layer under Layers and only Q2 under Respondents' marks, with label options
        """
        Question.objects.create(survey_section=self.f['section'], code="Q2", name="Route?", input_type="line", order_number=5)
        html = self.client.get(reverse('editor_question_edit', kwargs={'survey_uuid': self.uuid, 'question_id': self.f['obj'].pk})).content.decode()
        self.assertIn('data-layer-picker', html)
        self.assertIn('value="answers:Q2"', html)
        self.assertNotIn('value="answers:Q1"', html)
        self.assertIn('respondents&#x27; marks on Q1', html.replace("respondents' marks on Q1", "respondents&#x27; marks on Q1"))
        self.assertIn('id="fg-shared-map"', html)

    def test_picking_a_geo_source_creates_the_layer_with_settings(self):
        """
        GIVEN a geo question Q2 with a text sub-question T2 and no layer
        WHEN the owner creates an Objects question with layer=answers:Q2, label T2, comments on
        THEN a question layer for Q2 exists with that label and settings and the question is bound to it;
             a second question on the same source in the same section is refused (one layer once per
             section); an unknown code or label is ignored safely
        """
        from survey.models import SurveyMapLayer
        q2 = Question.objects.create(survey_section=self.f['section'], code="Q2", name="Route?", input_type="line", order_number=5)
        Question.objects.create(survey_section=self.f['section'], code="T2", name="Tell us", input_type="text", parent_question_id=q2, order_number=1)
        r = self._post(self.create_url, layer='answers:Q2', sm_settings='1', sm_label_field='T2', sm_show_comments='1')
        self.assertEqual(r.status_code, 200, r.content[:300])
        layer = SurveyMapLayer.objects.get(survey=self.f['survey'], source_question_code='Q2')
        self.assertEqual((layer.source, layer.label_field, layer.approve_first, layer.name),
                         ('question', 'T2', False, 'Marks: Route?'))
        self.assertEqual(Question.objects.get(name='React').layer_id, layer.pk)
        # Second question on the same source in the same section: the layer is
        # reused, not duplicated, and the question is refused — it is already
        # on this map (spec layer-objects-question).
        r = self._post(self.create_url, name='React again', layer='answers:Q2', sm_settings='1', sm_show_tallies='1')
        self.assertEqual(SurveyMapLayer.objects.filter(source_question_code='Q2').count(), 1)
        self.assertIn('Already on this section’s map', r.content.decode())
        self.assertFalse(Question.objects.filter(name='React again').exists())
        # Unknown source: no layer, the form complains about the layer field.
        r = self._post(self.create_url, name='Nope', layer='answers:NOPE')
        self.assertFalse(SurveyMapLayer.objects.filter(source_question_code='NOPE').exists())

    def test_live_preview_shows_a_marks_layer_before_it_exists_and_the_collects_state(self):
        """
        GIVEN a geo question Q2 with no marks layer yet, and the saved Objects question OBJ (which has sub-questions)
        WHEN the live preview renders a draft with layer=answers:Q2, and one with question_id=OBJ
        THEN the first shows the shared-map block for a transient "Marks: …" layer (not "not bound"),
             and the second reports collects=1 although the draft itself is unsaved
        """
        Question.objects.create(survey_section=self.f['section'], code="Q2", name="Route?", input_type="line", order_number=5)
        url = reverse('editor_question_preview_live', kwargs={'survey_uuid': self.uuid, 'section_id': self.f['section'].pk})
        html = self.client.post(url, {'input_type': 'layer_objects', 'name': 'React', 'layer': 'answers:Q2',
                                      'panel_mode': 'legend'}).content.decode()
        self.assertNotIn('not bound to a reference layer', html)
        self.assertIn('data-layer-source="question"', html)
        self.assertIn('data-panel-mode="legend"', html)
        self.assertIn('data-layer-id="new"', html)
        html = self.client.post(url, {'input_type': 'layer_objects', 'name': 'Marks by others', 'layer': str(self.f['layer'].pk),
                                      'question_id': str(self.f['obj'].pk), 'min_objects': '2'}).content.decode()
        self.assertIn('data-collects="1"', html)
        self.assertIn('data-min-objects="2"', html)

    def test_sharing_is_per_subquestion_for_any_layer(self):
        """
        GIVEN an uploaded layer bound by an Objects question with a 👍/👎 and a text sub-question,
              and answers about one object from two clean sessions
        WHEN nothing is shared, then the 👍/👎 sub-question is shared through the switch endpoint,
             then the text one (the survey is published between edits so a respondent can fetch)
        THEN the respondent metadata, the layer GeoJSON and the object card carry tallies and
             comments exactly as far as the sub-questions share them, uploaded layer included
        """
        from survey.layers import build_map_layers_metadata
        survey = self.f['survey']
        layer = _objects_layer(survey, name="Bins")
        objq = Question.objects.create(survey_section=self.f['section'], code="UOBJ", name="Bins", input_type="layer_objects", layer=layer, order_number=7)
        vote = Question.objects.create(survey_section=self.f['section'], code="UVOTE", name="Like?", input_type="thumbs",
                                       parent_question_id=objq, order_number=1, choices=[{"code": 1, "name": "up"}, {"code": 0, "name": "down"}])
        cmt = Question.objects.create(survey_section=self.f['section'], code="UCMT", name="Say", input_type="text", parent_question_id=objq, order_number=2)
        obj = layer.items.order_by('key').first()
        for sess in (SurveySession.objects.create(survey=survey), SurveySession.objects.create(survey=survey)):
            Answer.objects.create(survey_session=sess, question=vote, layer_object=obj, selected_choices=[1])
            Answer.objects.create(survey_session=sess, question=cmt, layer_object=obj, text="nice")
        geo_url = reverse('survey_layer_geojson', kwargs={'survey_slug': str(survey.uuid), 'layer_id': layer.pk})
        card_url = reverse('survey_layer_object', kwargs={'survey_slug': str(survey.uuid), 'layer_id': layer.pk, 'key': obj.key})
        share_url = lambda q: reverse('editor_question_share', kwargs={'survey_uuid': self.uuid, 'question_id': q.pk})
        status = lambda st: SurveyHeader.objects.filter(pk=survey.pk).update(status=st)
        resp = Client()

        def respondent():
            status('published')
            r0 = resp.get(reverse('section', kwargs={'survey_slug': str(survey.uuid), 'section_name': self.f['section'].name}))
            self.assertEqual(r0.status_code, 200, r0.content[:200])
            g = resp.get(geo_url)
            c = resp.get(card_url)
            self.assertEqual(c.status_code, 200, c.content[:200])
            meta = next(m for m in build_map_layers_metadata(survey) if m['id'] == layer.pk)
            status('draft')
            return meta, g, c.json()

        meta, g, card = respondent()
        self.assertFalse(meta['show_tallies'])
        self.assertNotIn('tally_up', g.content.decode())
        self.assertNotIn('tallies', card)
        self.assertNotIn('comments', card)
        # share 👍/👎
        r = self.client.post(share_url(vote), {'share': '1'})
        self.assertEqual((r.status_code, r['HX-Trigger']), (204, 'questionUpdated'))
        meta, g, card = respondent()
        self.assertTrue(meta['show_tallies'])
        self.assertEqual(g['Cache-Control'], 'private, no-store')
        feat = next(f for f in json.loads(g.content)['features'] if f['properties']['_key'] == obj.key)
        self.assertEqual((feat['properties']['tally_up'], feat['properties']['tally_down']), (2, 0))
        self.assertEqual(card['tallies']['up'], 2)
        self.assertNotIn('comments', card)
        # share comments
        self.client.post(share_url(cmt), {'share': '1'})
        meta, g, card = respondent()
        self.assertEqual(card['comments'], ["nice", "nice"])
        # a rating sub-question has nothing to share
        rating = Question.objects.create(survey_section=self.f['section'], code="URATE", name="Rate", input_type="rating",
                                         parent_question_id=objq, order_number=3, choices=[{"code": i, "name": str(i)} for i in range(1, 6)])
        self.assertEqual(self.client.post(share_url(rating), {'share': '1'}).status_code, 400)

    def test_quick_add_chips_create_preset_subquestions(self):
        """
        GIVEN the Objects question OBJ
        WHEN the 👍/👎, Rating and Comment chips post quick=thumbs|rating|comment
        THEN three sub-questions exist with the preset names, the 👍/👎 one shared and the others not,
             the rating with codes 1–5, and each response returns to the parent's modal with the switches
        """
        url = reverse('editor_subquestion_create', kwargs={'survey_uuid': self.uuid, 'parent_id': self.f['obj'].pk}) + '?return=modal'
        for quick in ('thumbs', 'rating', 'comment'):
            r = self.client.post(url, {'quick': quick}, HTTP_HX_REQUEST='true')
            self.assertEqual(r.status_code, 200, r.content[:200])
            html = r.content.decode()
            self.assertIn('data-share-toggle', html)
            self.assertIn('id="fg-subquestions"', html)
        subs = {q.name: q for q in Question.objects.filter(parent_question_id=self.f['obj'])}
        self.assertEqual((subs['Do you like it?'].input_type, subs['Do you like it?'].share_with_respondents), ('thumbs', True))
        self.assertEqual((subs['How would you rate it?'].input_type, [c['code'] for c in subs['How would you rate it?'].choices]), ('rating', [1, 2, 3, 4, 5]))
        self.assertEqual((subs['Anything to add?'].input_type, subs['Anything to add?'].share_with_respondents), ('text', False))

    def test_source_settings_keep_label_and_moderation_only(self):
        """
        GIVEN the Objects question bound to the Q1 marks layer
        WHEN its form is saved with the Source block (label WHY, approve-first on)
        THEN the layer carries both, and the form renders the Source block without the old
             tallies/comments checkboxes
        """
        url = reverse('editor_question_edit', kwargs={'survey_uuid': self.uuid, 'question_id': self.f['obj'].pk})
        self._post(url, name='Marks by others', layer=str(self.f['layer'].pk), sm_settings='1', sm_label_field='WHY', sm_approve_first='1')
        self.f['layer'].refresh_from_db()
        self.assertEqual((self.f['layer'].label_field, self.f['layer'].approve_first), ('WHY', True))
        html = self.client.get(url).content.decode()
        self.assertIn('id="fg-shared-map"', html)
        self.assertIn('Label each mark by', html)
        self.assertNotIn('sm_show_tallies', html)
        self.assertNotIn('sm_show_comments', html)

    def test_settings_edit_through_the_question(self):
        """
        GIVEN the Objects question bound to the Q1 layer
        WHEN its form is saved with approve_first on and label WHY
        THEN the layer carries both; the layer card no longer offers those fields
        """
        url = reverse('editor_question_edit', kwargs={'survey_uuid': self.uuid, 'question_id': self.f['obj'].pk})
        r = self._post(url, name='Marks by others', layer=str(self.f['layer'].pk), sm_settings='1',
                       sm_label_field='WHY', sm_approve_first='1', sm_show_tallies='1')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.f['layer'].refresh_from_db()
        self.assertEqual((self.f['layer'].label_field, self.f['layer'].approve_first, self.f['layer'].show_comments), ('WHY', True, False))
        html = self.client.get(reverse('editor_survey_settings_panel', kwargs={'survey_uuid': self.uuid})).content.decode()
        self.assertIn('source: answers', html)
        self.assertIn('settings are on the question', html)
        self.assertNotIn('data-field="approve_first"', html)
        self.assertNotIn('data-field="key_field"', html[html.index('data-layer-id="%d"' % self.f['layer'].pk):])

    def test_object_editor_read_only(self):
        """
        GIVEN the question layer with one materialised mark
        WHEN the owner opens its object editor and tries to change geometry, delete, import
        THEN the page renders the read-only banner and every write is refused with 400
        """
        from survey.layers import sync_question_layer
        s = SurveySession.objects.create(survey=self.f['survey'])
        _mark(s, self.f['q1'], 13.4, 52.5)
        sync_question_layer(self.f['layer'], s)
        obj = self.f['layer'].items.get()
        kw = {'survey_uuid': self.uuid, 'layer_id': self.f['layer'].pk}
        html = self.client.get(reverse('editor_layer_objects', kwargs=kw)).content.decode()
        self.assertIn('loe--readonly', html)
        self.assertEqual(self.client.post(reverse('editor_layer_object_geometry', kwargs=dict(kw, key=obj.key)),
                                          json.dumps({'geometry': {'type': 'Point', 'coordinates': [1, 1]}}),
                                          content_type='application/json').status_code, 400)
        self.assertEqual(self.client.delete(reverse('editor_layer_object', kwargs=dict(kw, key=obj.key))).status_code, 400)
        self.assertEqual(self.client.post(reverse('editor_layer_objects_collection', kwargs=kw),
                                          json.dumps({'title': 'x', 'geometry': {'type': 'Point', 'coordinates': [1, 1]}}),
                                          content_type='application/json').status_code, 400)
        self.assertEqual(self.client.get(reverse('editor_layer_object', kwargs=dict(kw, key=obj.key))).status_code, 200)
        self.assertEqual(self.f['layer'].items.count(), 1)

    def test_delete_source_question_refused_while_an_objects_question_reads_it(self):
        """
        GIVEN Q1 feeds the layer and the Objects question OBJ shows that layer
        WHEN the owner deletes Q1, and opens Q1's form
        THEN the delete is refused (409, blocked) naming OBJ, Q1 remains, and the form names the layer
        """
        r = self.client.post(reverse('editor_question_delete', kwargs={'survey_uuid': self.uuid, 'question_id': self.f['q1'].pk}))
        self.assertEqual(r.status_code, 409)
        self.assertIn('Marks by others', r.json()['blocked'])
        self.assertTrue(Question.objects.filter(pk=self.f['q1'].pk).exists())
        html = self.client.get(reverse('editor_question_edit', kwargs={'survey_uuid': self.uuid, 'question_id': self.f['q1'].pk})).content.decode()
        self.assertIn('feed the reference layer', html)
        q2 = Question.objects.create(survey_section=self.f['section'], code="Q9", name="Other", input_type="point", order_number=9)
        self.assertEqual(self.client.post(reverse('editor_question_delete', kwargs={'survey_uuid': self.uuid, 'question_id': q2.pk})).status_code, 200)

    def test_deleting_the_last_objects_question_drops_the_marks_layer_and_frees_the_source(self):
        """
        GIVEN the Objects question OBJ is the only one showing the Q1 marks layer
        WHEN the owner deletes OBJ, then Q1
        THEN OBJ's delete answers with HX-Trigger questionUpdated (the preview refreshes), the
             orphaned marks layer is gone with it, and Q1 now deletes normally
        """
        from survey.models import SurveyMapLayer
        r = self.client.post(reverse('editor_question_delete', kwargs={'survey_uuid': self.uuid, 'question_id': self.f['obj'].pk}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['HX-Trigger'], 'questionUpdated')
        self.assertFalse(SurveyMapLayer.objects.filter(pk=self.f['layer'].pk).exists())
        r = self.client.post(reverse('editor_question_delete', kwargs={'survey_uuid': self.uuid, 'question_id': self.f['q1'].pk}))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Question.objects.filter(pk=self.f['q1'].pk).exists())

    def test_a_reader_in_another_version_neither_blocks_nor_loses_the_layer(self):
        """
        GIVEN the published version's OBJ shows the Q1 marks layer, and a draft copy where the
              creator removed its own OBJ
        WHEN the creator deletes Q1 in the draft
        THEN the draft's Q1 goes (readers in other headers do not block a draft's structure),
             while the layer stays — the published version still shows it
        """
        from survey.models import SurveyMapLayer
        draft = clone_survey_for_draft(self.f['survey'])
        Question.objects.filter(survey_section__survey_header=draft, input_type='layer_objects').delete()
        q1_draft = Question.objects.get(survey_section__survey_header=draft, code='Q1')
        r = self.client.post(reverse('editor_question_delete', kwargs={'survey_uuid': draft.uuid, 'question_id': q1_draft.pk}))
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertFalse(Question.objects.filter(pk=q1_draft.pk).exists())
        self.assertTrue(SurveyMapLayer.objects.filter(pk=self.f['layer'].pk).exists())
        self.assertTrue(Question.objects.filter(pk=self.f['obj'].pk).exists())

    def test_deleting_the_source_question_takes_an_unread_marks_layer_with_it(self):
        """
        GIVEN a marks layer on Q1 that no Objects question shows any more (OBJ re-bound elsewhere)
        WHEN the owner deletes Q1
        THEN Q1 and the layer are both gone
        """
        from survey.models import SurveyMapLayer
        Question.objects.filter(pk=self.f['obj'].pk).update(layer=None)
        r = self.client.post(reverse('editor_question_delete', kwargs={'survey_uuid': self.uuid, 'question_id': self.f['q1'].pk}))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Question.objects.filter(pk=self.f['q1'].pk).exists())
        self.assertFalse(SurveyMapLayer.objects.filter(pk=self.f['layer'].pk).exists())


class SharedMapExportTest(TestCase):
    """Export carries the verdict; ZIP round-trips the config (task 6)."""

    def setUp(self):
        from django.contrib.auth.models import User
        from survey.layers import sync_question_layer
        self.f = _shared_map_survey("shared_map_export")
        self.owner = User.objects.create_user('exowner', 'x@example.com', 'pw')
        Membership.objects.create(user=self.owner, organization=self.f['survey'].organization, role='admin')
        self.client.login(username='exowner', password='pw')
        self.a = SurveySession.objects.create(survey=self.f['survey'])
        _mark(self.a, self.f['q1'], 13.4, 52.5, why="A's bin")
        sync_question_layer(self.f['layer'], self.a)
        self.obj = self.f['layer'].items.get()
        for up in (True, True, False):
            _react(SurveySession.objects.create(survey=self.f['survey']), self.f['obj'], self.obj, up=up)
        _react(SurveySession.objects.create(survey=self.f['survey']), self.f['obj'], self.obj, comment="ok")
        self.obj.status = 'hidden'
        self.obj.save()

    def _zip(self):
        from zipfile import ZipFile
        from io import BytesIO
        response = self.client.get(reverse('download_data', kwargs={'survey_slug': str(self.f['survey'].uuid)}))
        self.assertEqual(response.status_code, 200)
        return ZipFile(BytesIO(response.content))

    def test_export_skips_display_only_questions_and_scopes_aggregates_to_the_header(self):
        """
        GIVEN a display-only Objects question (no sub-questions) on the Q1 layer, and a draft copy
              whose cloned sub-questions also point at the layer
        WHEN the survey is exported
        THEN no objects CSV is written for the display-only question, and the layer's results
             GeoJSON carries columns for this header's sub-questions only
        """
        Question.objects.create(survey_section=self.f['section'], code="DISP", name="Just show", input_type="layer_objects",
                                layer=self.f['layer'], order_number=9)
        draft = clone_survey_for_draft(self.f['survey'])
        self.assertTrue(Question.objects.filter(survey_section__survey_header=draft, parent_question_id__layer=self.f['layer']).exists())
        r = self.client.get(reverse('download_data', kwargs={'survey_slug': str(self.f['survey'].uuid)}))
        zf = zipfile.ZipFile(BytesIO(r.content))
        names = zf.namelist()
        self.assertFalse(any('objects_DISP' in n for n in names), names)
        self.assertTrue(any('objects_OBJ' in n for n in names), names)
        results = next(n for n in names if n.endswith('.results.geojson'))
        props = json.loads(zf.read(results))['features'][0]['properties']
        sub_cols = {k.rsplit('_', 1)[0] for k in props if k.endswith('_count')}
        self.assertEqual(sub_cols, {'VOTE', 'CMT'})

    def test_geojson_and_csv_carry_the_verdict(self):
        """
        GIVEN A's mark with 2 👍, 1 👎, one comment, hidden by the creator
        WHEN the survey data is downloaded
        THEN A's feature in the Q1 GeoJSON has mark_key/votes_up=2/votes_down=1/comments=1, and the objects CSV has a status column saying hidden
        """
        z = self._zip()
        names = z.namelist()
        geo = next(n for n in names if n.endswith('.geojson') and 'results' not in n)   # Q1 is the only geo question
        props = json.loads(z.read(geo))['features'][0]['properties']
        self.assertEqual((props['mark_key'], props['votes_up'], props['votes_down'], props['comments']),
                         (self.obj.key, 2, 1, 1))
        csv_name = next(n for n in names if n.endswith('objects_OBJ.csv'))
        csv = z.read(csv_name).decode()
        self.assertIn('status', csv.splitlines()[0])
        self.assertIn('hidden', csv)

    def test_zip_round_trip_and_dangling_code(self):
        """
        GIVEN the survey exported as a structure ZIP
        WHEN it is imported back, and again with the geo question removed from the archive
        THEN the layer keeps source/code/settings with zero objects and the pair stays bound; the second import downgrades it with a report line
        """
        from survey.serialization import export_survey_to_zip, import_survey_from_zip
        from survey.models import SurveyMapLayer
        self.f['layer'].show_comments = True
        self.f['layer'].save()
        from io import BytesIO
        buf = BytesIO()
        export_survey_to_zip(self.f['survey'], buf)
        data = buf.getvalue()
        imported, warnings = import_survey_from_zip(BytesIO(data), organization=self.f['survey'].organization, created_by=self.owner)
        layer = SurveyMapLayer.objects.get(survey=imported)
        # Q1 already exists in this organisation, so the import remaps its code —
        # and the layer's source code follows the remap (spec survey-editor).
        imported_q1 = Question.objects.get(survey_section__survey_header=imported, input_type='point')
        self.assertEqual((layer.source, layer.source_question_code, layer.show_comments, layer.items.count()),
                         ('question', imported_q1.code, True, 0))
        self.assertEqual(Question.objects.get(survey_section__survey_header=imported, input_type='layer_objects').layer_id, layer.pk)
        self.assertFalse([w for w in warnings if 'Reference layer' in w])
        # Dangling: rewrite the archive's survey.json without Q1.
        from zipfile import ZipFile
        src = ZipFile(BytesIO(data))
        survey_json = json.loads(src.read('survey.json'))
        for section in survey_json['survey']['sections']:
            section['questions'] = [q for q in section['questions'] if q.get('code') != 'Q1']
        out = BytesIO()
        with ZipFile(out, 'w') as dst:
            for name in src.namelist():
                dst.writestr(name, json.dumps(survey_json) if name == 'survey.json' else src.read(name))
        imported2, warnings2 = import_survey_from_zip(BytesIO(out.getvalue()), organization=self.f['survey'].organization, created_by=self.owner)
        layer2 = SurveyMapLayer.objects.get(survey=imported2)
        self.assertEqual((layer2.source, layer2.source_question_code), ('upload', ''))
        self.assertTrue([w for w in warnings2 if 'imported as an empty layer' in w])
