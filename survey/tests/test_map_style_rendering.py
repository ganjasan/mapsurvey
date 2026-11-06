"""Tests for the `map-style-rendering` capability (change map-styles-rendering-path, #541).

The publishing script is pure Python outside the Django app; it is imported from `scripts/`
so a test never needs the network. The fixtures are the `streets-v12` base style and the
hosted Paper A / Paper B styles as fetched on 2026-11-06.
"""
import glob
import importlib.util
import json
import os
import re

from django.test import SimpleTestCase

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(TESTS_DIR))
SCRIPT = os.path.join(REPO, 'scripts', 'mapbox_style_publish.py')
FIXTURES = os.path.join(TESTS_DIR, 'fixtures')
SETTINGS_DIR = os.path.join(REPO, 'scripts', 'map_styles')
COMPARED = ('type', 'source-layer', 'filter', 'minzoom', 'maxzoom', 'layout', 'paint')
GREY = re.compile(r'^#([0-9a-f]{2})\1\1$')


def _load_script():
    spec = importlib.util.spec_from_file_location('mapbox_style_publish', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(name):
    with open(os.path.join(FIXTURES, name)) as handle:
        return json.load(handle)


def _settings(name):
    with open(os.path.join(SETTINGS_DIR, name)) as handle:
        return json.load(handle)


def _layers_view(style):
    return [{key: layer.get(key) for key in ('id',) + COMPARED} for layer in style['layers']]


class FakeStylesClient:
    """Same shape as MapboxStylesClient; records calls instead of making them."""

    def __init__(self, existing=None):
        self.existing = dict(existing or {})  # name -> id
        self.calls = []

    def get_style(self, style_id):
        self.calls.append(('GET', style_id))
        return _fixture('mapbox_streets_v12.json')

    def find_by_name(self, name):
        self.calls.append(('FIND', name))
        return self.existing.get(name)

    def create(self, style):
        self.calls.append(('POST', style['name']))
        style_id = f'id-{len(self.existing) + 1}'
        self.existing[style['name']] = style_id
        return {'id': style_id, **style}, {}

    def update(self, style_id, style):
        self.calls.append(('PATCH', style_id))
        return {'id': style_id, **style}, {}


class PublishingScriptTest(SimpleTestCase):
    """Spec: map-style-rendering / Requirement: A style is published to Mapbox by one script."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = _load_script()
        cls.base = _fixture('mapbox_streets_v12.json')

    def test_same_settings_one_style(self):
        """
        GIVEN a Styles API that already holds a style named like the settings
        WHEN the script publishes the same settings twice
        THEN the second run PATCHes that id and never POSTs
        """
        settings = _settings('paper_a.json')
        client = FakeStylesClient()
        first_id, first_action = self.script.publish(settings, client, base=self.base)
        self.assertEqual(first_action, 'created')
        client.calls.clear()
        second_id, second_action = self.script.publish(settings, client, base=self.base)
        self.assertEqual((second_id, second_action), (first_id, 'updated'))
        methods = [call[0] for call in client.calls]
        self.assertIn('PATCH', methods)
        self.assertNotIn('POST', methods)

    def test_duplicate_names_refuse_to_publish(self):
        """
        GIVEN an account holding two styles with the settings' name
        WHEN the real client looks the name up
        THEN it refuses instead of picking one of them
        """
        client = self.script.MapboxStylesClient('sk.test', 'acct')
        client.list_styles = lambda: [{'id': 'a', 'name': 'Twin'}, {'id': 'b', 'name': 'Twin'},
                                      {'id': 'c', 'name': 'Other'}]
        with self.assertRaises(SystemExit) as raised:
            client.find_by_name('Twin')
        self.assertIn('a, b', str(raised.exception))
        self.assertEqual(client.find_by_name('Other'), 'c')
        self.assertIsNone(client.find_by_name('Missing'))

    def test_poi_toggle_round_trips(self):
        """
        GIVEN the stored streets-v12 base style
        WHEN apply_settings runs with poi: false and then with poi: true
        THEN the first result has no poi_label layer and keeps every other layer unchanged,
             and the second returns the base's layers in their original order
        """
        without = self.script.apply_settings(self.base, {'poi': False})
        self.assertFalse([l for l in without['layers'] if l.get('source-layer') == 'poi_label'])
        kept = {l['id'] for l in without['layers']}
        base_kept = [l for l in self.base['layers'] if l['id'] in kept]
        self.assertEqual(_layers_view({'layers': base_kept}), _layers_view(without))
        self.assertLess(len(without['layers']), len(self.base['layers']))
        with_poi = self.script.apply_settings(self.base, {'poi': True})
        self.assertEqual(_layers_view(with_poi), _layers_view(self.base))

    def test_greyscale_is_a_style_not_a_filter(self):
        """
        GIVEN the base style
        WHEN apply_settings runs with greyscale: true
        THEN every fill-, line-, text- and background-color, inside expressions too,
             is a #rrggbb grey with equal channels
        """
        grey = self.script.apply_settings(self.base, {'greyscale': True})
        colours = []
        for layer in grey['layers']:
            for prop in ('fill-color', 'line-color', 'text-color', 'background-color'):
                if prop in (layer.get('paint') or {}):
                    colours.extend(_colour_strings(layer['paint'][prop]))
        self.assertGreater(len(colours), 100)
        not_grey = [c for c in colours if not GREY.match(c)]
        self.assertEqual(not_grey, [])

    def test_token_never_reaches_a_browser(self):
        """
        GIVEN the script module and the templates
        WHEN both are scanned
        THEN the script reads MAPBOX_STYLES_TOKEN only and no template names it
        """
        with open(SCRIPT) as handle:
            source = handle.read()
        self.assertIn('MAPBOX_STYLES_TOKEN', source)
        self.assertNotIn('MAPBOX_ACCESS_TOKEN', source)
        offenders = []
        for path in glob.glob(os.path.join(REPO, 'survey', 'templates', '**', '*.html'), recursive=True):
            with open(path) as handle:
                if 'MAPBOX_STYLES_TOKEN' in handle.read():
                    offenders.append(os.path.relpath(path, REPO))
        self.assertEqual(offenders, [])

    def test_paper_a_is_reproduced_from_its_settings(self):
        """
        GIVEN the hosted Paper A style as fetched on 2026-11-06
        WHEN the script applies scripts/map_styles/paper_a.json to the base
        THEN the layers match the hosted style one for one, in order
        """
        built = self.script.apply_settings(self.base, _settings('paper_a.json'))
        self.assertEqual(_layers_view(built), _layers_view(_fixture('mapbox_paper_a.json')))

    def test_paper_b_is_reproduced_from_its_settings(self):
        """
        GIVEN the hosted Paper B style as fetched on 2026-11-06
        WHEN the script applies scripts/map_styles/paper_b.json to the base
        THEN the layers match the hosted style one for one, in order
        """
        built = self.script.apply_settings(self.base, _settings('paper_b.json'))
        self.assertEqual(_layers_view(built), _layers_view(_fixture('mapbox_paper_b.json')))

    def test_settings_ride_in_metadata_and_read_only_keys_are_dropped(self):
        """
        GIVEN a fetched style with id, owner and visibility
        WHEN apply_settings runs
        THEN the result carries the settings in metadata and none of the read-only keys
        """
        fetched = dict(self.base, id='abc', owner='someone', visibility='private', created='x')
        settings = _settings('paper_b.json')
        built = self.script.apply_settings(fetched, settings)
        self.assertEqual(built['metadata']['mapsurvey:settings'], settings)
        self.assertEqual(built['name'], settings['name'])
        for key in ('id', 'owner', 'visibility', 'created'):
            self.assertNotIn(key, built)
        self.assertIn('id', fetched)  # the input is untouched


def _colour_strings(value):
    if isinstance(value, str):
        return [value] if value.startswith(('#', 'hsl', 'rgb')) else []
    if isinstance(value, list):
        return [c for item in value for c in _colour_strings(item)]
    return []
