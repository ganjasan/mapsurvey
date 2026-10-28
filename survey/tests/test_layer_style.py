"""Tests for the `layer-style` capability (openspec/specs/layer-style/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import LineString
from django.urls import reverse
from io import BytesIO
import json
from survey.models import Organization, SurveyHeader, SurveySection, Question, Membership
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.tests.helpers import _styled_layer


class LayerStyleNormalizeTest(SimpleTestCase):
    """normalize_style is the one validator (spec layer-style)."""

    def test_empty_is_todays_look(self):
        """
        GIVEN a layer saved before this change (style = {})
        WHEN it is normalised
        THEN base defaults come back, no rule, legend on
        """
        from survey.layers import normalize_style
        st = normalize_style({})
        self.assertEqual((st['opacity'], st['weight'], st['fill_opacity'], st['radius'], st['icon'], st['by'], st['legend']),
                         (0.9, 2, 0.15, 6, '', None, True))

    def test_repairs_not_rejects(self):
        """
        GIVEN a style with a weight of 40, a named colour, an unknown icon and an unknown key
        WHEN normalised
        THEN weight clamps to 12, the class colour falls back to the base colour, icon and key drop
        """
        from survey.layers import normalize_style
        st = normalize_style({'weight': 40, 'bogus': 1, 'icon': 'fa-nope',
                              'by': {'field': 'priority_class', 'mode': 'categories',
                                     'classes': [{'value': 'High', 'color': 'red', 'weight': 99, 'icon': 'fa-trash'}]}},
                             base_color='#123456')
        self.assertEqual(st['weight'], 12)
        self.assertNotIn('bogus', st)
        self.assertEqual(st['icon'], '')
        cls = st['by']['classes'][0]
        self.assertEqual((cls['color'], cls['weight'], cls['icon'], cls['label']), ('#123456', 12, 'fa-trash', 'High'))
        self.assertEqual(st['by']['other']['label'], 'Other')

    def test_rule_without_field_dropped_and_class_cap(self):
        """
        GIVEN a rule with an empty field, and one with 13 classes
        WHEN normalised
        THEN the first yields no rule and the second raises the validation error
        """
        from survey.layers import normalize_style, LayerValidationError
        self.assertIsNone(normalize_style({'by': {'field': ' ', 'classes': [{'value': 'x'}]}})['by'])
        with self.assertRaises(LayerValidationError):
            normalize_style({'by': {'field': 'f', 'classes': [{'value': str(i)} for i in range(13)]}})

    def test_graduated_sorted_and_labelled(self):
        """
        GIVEN graduated classes posted out of order with from > to on one
        WHEN normalised
        THEN classes are ascending, the swapped bounds repaired, labels derived, ramp/weight_range defaulted
        """
        from survey.layers import normalize_style
        st = normalize_style({'by': {'field': 'score', 'mode': 'graduated',
                                     'classes': [{'from': 50, 'to': 100}, {'to': 0, 'from': 50, 'label': 'low'}]}})
        classes = st['by']['classes']
        self.assertEqual([(c['from'], c['to']) for c in classes], [(0, 50), (50, 100)])
        self.assertEqual((classes[0]['label'], classes[1]['label']), ('low', '50 – 100'))
        self.assertEqual((st['by']['ramp'], st['by']['weight_range'], st['by']['breaks']), (['#8ecae6', '#d62828'], [2, 6], 'quantiles'))

    def test_match_class(self):
        """
        GIVEN a categories rule and a graduated rule
        WHEN values are matched
        THEN string equality and half-open ranges (last inclusive) decide; misses return None
        """
        from survey.layers import normalize_style, match_class
        cat = normalize_style({'by': {'field': 'c', 'classes': [{'value': '1'}, {'value': 'High'}]}})['by']
        self.assertEqual(match_class(cat, 1)['value'], '1')
        self.assertEqual(match_class(cat, 'High')['value'], 'High')
        self.assertIsNone(match_class(cat, 'Low'))
        grad = normalize_style({'by': {'field': 's', 'mode': 'graduated', 'classes': [{'from': 0, 'to': 10}, {'from': 10, 'to': 20}]}})['by']
        self.assertEqual(match_class(grad, 10)['from'], 10)
        self.assertEqual(match_class(grad, 20)['from'], 10)
        self.assertIsNone(match_class(grad, 21))
        self.assertIsNone(match_class(grad, 'abc'))


class LayerStyleSummaryLegendTest(TestCase):
    """style_summary and legend_for read the objects (spec layer-style)."""

    def setUp(self):
        self.org = Organization.objects.create(name="Style Org")
        self.survey = SurveyHeader.objects.create(name="style_survey", organization=self.org, redirect_url="/t/", status='published')
        SurveySection.objects.create(survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True)
        self.layer = _styled_layer(self.survey)

    def test_summary_categorical_numeric_empty(self):
        """
        GIVEN 8 segments with priority_class and priority_score
        WHEN each property is summarised, plus a missing one
        THEN values with counts sorted by count, numeric min/max/count/quartiles, and empty
        """
        from survey.layers import style_summary
        cat = style_summary(self.layer, 'priority_class')
        self.assertEqual(cat['kind'], 'categories')
        self.assertEqual(cat['values'][0], {'value': 'High', 'count': 3})
        self.assertEqual({v['value'] for v in cat['values']}, {'High', 'Medium', 'Low', 'Odd'})
        num = style_summary(self.layer, 'priority_score')
        self.assertEqual((num['kind'], num['min'], num['max'], num['count'], len(num['quantiles'])), ('numeric', 3, 73, 8, 3))
        self.assertEqual(style_summary(self.layer, 'nope')['kind'], 'empty')

    def test_too_many_values(self):
        """
        GIVEN a property with 13 distinct values
        WHEN summarised
        THEN kind is too_many with the count
        """
        from survey.layers import style_summary
        for i, obj in enumerate(self.layer.items.all()):
            obj.properties['many'] = f'v{i}'
            obj.save()
        from survey.models import LayerObject
        from django.contrib.gis.geos import LineString
        for i in range(8, 13):
            LayerObject.objects.create(layer=self.layer, key=f'x{i}', geometry=LineString((i, 0), (i, 1)), properties={'many': f'v{i}'})
        self.assertEqual(style_summary(self.layer, 'many'), {'kind': 'too_many', 'count': 13})

    def test_legend_rows_and_other(self):
        """
        GIVEN a three-class rule on priority_class (one object is 'Odd')
        WHEN the legend is computed, then with legend off, then with all values covered
        THEN three rows plus Other with count 1; nothing; three rows without Other
        """
        from survey.layers import legend_for
        self.layer.style = {'by': {'field': 'priority_class', 'classes': [
            {'value': 'High', 'color': '#d62828', 'weight': 5, 'label': 'High priority'},
            {'value': 'Medium', 'color': '#f77f00'}, {'value': 'Low', 'color': '#8ecae6'}]}}
        rows = legend_for(self.layer)
        self.assertEqual([r['label'] for r in rows], ['High priority', 'Medium', 'Low', 'Other'])
        self.assertEqual((rows[0]['kind'], rows[0]['color'], rows[0]['weight'], rows[-1]['count']), ('line', '#d62828', 5, 1))
        self.layer.style['legend'] = False
        self.assertEqual(legend_for(self.layer), [])
        self.layer.style['legend'] = True
        self.layer.items.filter(properties__priority_class='Odd').delete()
        self.assertEqual(len(legend_for(self.layer)), 3)


class LayerStyleRenderingTest(TestCase):
    """Metadata carries style + legend; the respondent shell embeds them (spec layer-style)."""

    def setUp(self):
        self.org = Organization.objects.create(name="Style Render Org")
        self.survey = SurveyHeader.objects.create(name="style_render", organization=self.org, redirect_url="/t/", status='published')
        self.section = SurveySection.objects.create(survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True)
        self.layer = _styled_layer(self.survey, style={'weight': 4, 'by': {'field': 'priority_class', 'classes': [
            {'value': 'High', 'color': '#d62828', 'weight': 5, 'label': 'High <b>priority</b>'},
            {'value': 'Medium', 'color': '#f77f00'}, {'value': 'Low', 'color': '#8ecae6'}]}})

    def test_metadata_and_shell(self):
        """
        GIVEN a layer with a three-class rule and one unmatched object
        WHEN the metadata is built and the section renders
        THEN meta carries the normalised style and four legend rows, and the page embeds them JSON-encoded (label escaped by the client, not here)
        """
        from survey.layers import build_map_layers_metadata
        meta = build_map_layers_metadata(self.survey)[0]
        self.assertEqual(meta['style']['weight'], 4)
        self.assertEqual(meta['style']['by']['field'], 'priority_class')
        self.assertEqual([r['label'] for r in meta['legend']], ['High <b>priority</b>', 'Medium', 'Low', 'Other'])
        html = self.client.get(reverse('section', kwargs={'survey_slug': str(self.survey.uuid), 'section_name': 's1'})).content.decode()
        self.assertIn('"legend"', html)
        self.assertIn('priority_class', html)
        self.assertIn('overlayLabel', html)
        self.assertIn('function styleFor', html)

    def test_empty_style_is_default_metadata(self):
        """
        GIVEN a layer with no style
        WHEN metadata is built
        THEN style has the defaults and legend is empty
        """
        from survey.layers import build_map_layers_metadata
        from survey.models import SurveyMapLayer
        plain = SurveyMapLayer.objects.create(survey=self.survey, name="Plain", geojson='{"type":"FeatureCollection","features":[]}')
        meta = next(m for m in build_map_layers_metadata(self.survey) if m['id'] == plain.pk)
        self.assertEqual((meta['style']['radius'], meta['style']['by'], meta['legend']), (6, None, []))


class LayerStyleEditorTest(TestCase):
    """The update endpoint normalises style, the summary endpoint feeds auto-fill,
    the card renders the Style block (spec layer-style, survey-editor delta)."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.org = Organization.objects.create(name="Style Editor Org")
        self.survey = SurveyHeader.objects.create(name="style_editor", organization=self.org, redirect_url="/t/", status='draft')
        self.section = SurveySection.objects.create(survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True)
        self.layer = _styled_layer(self.survey)
        self.owner = User.objects.create_user('styleowner', 's@example.com', 'pw')
        Membership.objects.create(user=self.owner, organization=self.org, role='admin')
        self.client.login(username='styleowner', password='pw')
        self.update = reverse('editor_survey_layer_update', kwargs={'survey_uuid': self.survey.uuid, 'layer_id': self.layer.pk})
        self.summary = reverse('editor_survey_layer_style_summary', kwargs={'survey_uuid': self.survey.uuid, 'layer_id': self.layer.pk})

    def test_update_normalises_and_returns_legend(self):
        """
        GIVEN a categories rule posted with a clamped weight and a stray key
        WHEN saved
        THEN the stored style is normalised, the payload carries style + legend, and a 13-class rule is a 400
        """
        style = {'weight': 3, 'junk': 1, 'by': {'field': 'priority_class', 'classes': [
            {'value': 'High', 'color': '#d62828', 'weight': 50}, {'value': 'Medium', 'color': '#f77f00'}, {'value': 'Low', 'color': '#8ecae6'}]}}
        r = self.client.post(self.update, {'style': json.dumps(style)})
        self.assertEqual(r.status_code, 200, r.content[:200])
        data = r.json()
        self.assertEqual(data['style']['by']['classes'][0]['weight'], 12)
        self.assertNotIn('junk', data['style'])
        self.assertEqual([row['label'] for row in data['legend']], ['High', 'Medium', 'Low', 'Other'])
        self.layer.refresh_from_db()
        self.assertEqual(self.layer.style['by']['field'], 'priority_class')
        bad = {'by': {'field': 'priority_class', 'classes': [{'value': str(i)} for i in range(13)]}}
        self.assertEqual(self.client.post(self.update, {'style': json.dumps(bad)}).status_code, 400)
        self.assertEqual(self.client.post(self.update, {'style': 'not json'}).status_code, 400)

    def test_question_layer_keeps_base_only(self):
        """
        GIVEN a layer sourced from answers
        WHEN a style with a rule is posted
        THEN the base is stored and the rule dropped; the summary endpoint is a 404 for it
        """
        from survey.models import SurveyMapLayer
        Question.objects.create(survey_section=self.section, code="Q1", name="Where?", input_type="point", order_number=1)
        ql = SurveyMapLayer.objects.create(survey=self.survey, name="Marks", geojson='{"type":"FeatureCollection","features":[]}',
                                           source='question', source_question_code='Q1')
        url = reverse('editor_survey_layer_update', kwargs={'survey_uuid': self.survey.uuid, 'layer_id': ql.pk})
        r = self.client.post(url, {'style': json.dumps({'radius': 9, 'by': {'field': 'x', 'classes': [{'value': 'a'}]}})})
        self.assertEqual(r.status_code, 200)
        ql.refresh_from_db()
        self.assertEqual((ql.style['radius'], ql.style['by']), (9, None))
        self.assertEqual(self.client.get(reverse('editor_survey_layer_style_summary', kwargs={'survey_uuid': self.survey.uuid, 'layer_id': ql.pk}) + '?field=x').status_code, 404)

    def test_summary_endpoint(self):
        """
        GIVEN the segments layer
        WHEN the owner asks for priority_class, priority_score and nothing
        THEN categories, numeric and a 400 come back; a viewer is refused
        """
        self.assertEqual(self.client.get(self.summary + '?field=priority_class').json()['kind'], 'categories')
        num = self.client.get(self.summary + '?field=priority_score').json()
        self.assertEqual((num['kind'], num['min'], num['max']), ('numeric', 3, 73))
        self.assertEqual(self.client.get(self.summary).status_code, 400)

    def test_card_markup(self):
        """
        GIVEN the settings panel
        WHEN it renders
        THEN the upload layer's card has the Style block with base controls, the rule editor and its properties, and the legend switch
        """
        html = self.client.get(reverse('editor_survey_settings_panel', kwargs={'survey_uuid': self.survey.uuid})).content.decode()
        self.assertIn('class="pr-field ref-style"', html)
        self.assertIn('data-style="opacity"', html)
        self.assertIn('data-style-rule-on', html)
        self.assertIn('<option value="priority_class">', html)
        self.assertIn('data-style-legend', html)
        self.assertIn('data-summary-url=', html)
        self.assertIn('function styleFor', html)


class LayerStyleSerializationTest(TestCase):
    """style rides the ZIP and is normalised on the way in (spec survey-serialization delta)."""

    def test_round_trip_and_clamp(self):
        """
        GIVEN a layer with a three-class rule
        WHEN exported, the archive's class weight edited to 99, and re-imported
        THEN the imported layer has the rule with that weight clamped to 12, the rest identical; a 13-class archive imports without a rule
        """
        from io import BytesIO
        from zipfile import ZipFile
        from django.contrib.auth.models import User
        from survey.serialization import export_survey_to_zip, import_survey_from_zip
        from survey.models import SurveyMapLayer
        org = Organization.objects.create(name="Style Ser Org")
        survey = SurveyHeader.objects.create(name="style_ser", organization=org, redirect_url="/t/", status='published')
        SurveySection.objects.create(survey_header=survey, name="s1", title="S1", code="S1", is_head=True)
        _styled_layer(survey, style={'opacity': 0.5, 'by': {'field': 'priority_class', 'classes': [
            {'value': 'High', 'color': '#d62828', 'weight': 5, 'label': 'Hi'}, {'value': 'Medium', 'color': '#f77f00'}, {'value': 'Low', 'color': '#8ecae6'}]}})
        user = User.objects.create_user('seruser', 'z@example.com', 'pw')
        buf = BytesIO(); export_survey_to_zip(survey, buf); data = buf.getvalue()
        src = ZipFile(BytesIO(data)); sj = json.loads(src.read('survey.json'))
        self.assertEqual(sj['survey']['layers'][0]['style']['by']['classes'][0]['label'], 'Hi')
        sj['survey']['layers'][0]['style']['by']['classes'][0]['weight'] = 99
        out = BytesIO()
        with ZipFile(out, 'w') as dst:
            for n in src.namelist():
                dst.writestr(n, json.dumps(sj) if n == 'survey.json' else src.read(n))
        imported, warnings = import_survey_from_zip(BytesIO(out.getvalue()), organization=org, created_by=user)
        layer = SurveyMapLayer.objects.get(survey=imported)
        self.assertEqual((layer.style['opacity'], layer.style['by']['classes'][0]['weight'], layer.style['by']['classes'][0]['label']), (0.5, 12, 'Hi'))
        sj['survey']['layers'][0]['style']['by']['classes'] = [{'value': str(i)} for i in range(13)]
        out2 = BytesIO()
        with ZipFile(out2, 'w') as dst:
            for n in src.namelist():
                dst.writestr(n, json.dumps(sj) if n == 'survey.json' else src.read(n))
        imported2, _w = import_survey_from_zip(BytesIO(out2.getvalue()), organization=org, created_by=user)
        self.assertIsNone(SurveyMapLayer.objects.get(survey=imported2).style['by'])
