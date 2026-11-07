"""Tests for the `map-style-editor` capability (change map-styles-editor, #543; epic #545).

The editor page and its controls, the preview endpoint's MapLibre rewriting, Save as a new
version, re-pinning on live base-map edits, the print tab and the contrast rule.
"""
import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from billing.tests.helpers import make_sub, trial_used_elsewhere
from survey import basemaps as basemap_registry
from survey.map_styles import controls, preview
from survey.map_styles import tasks as style_tasks
from survey.models import MapStyle, MapStyleVersion, Membership, SurveyCollaborator
from survey.services import sections as svc_sections
from survey.services import surveys as svc_surveys
from survey.services.context import Actor
from survey.tests.helpers import _make_org, _make_survey_with_section
from survey.tests.test_map_style_library import ready_style

BASE = {'version': 8, 'name': 'Mapbox Streets', 'glyphs': 'mapbox://fonts/mapbox/{fontstack}/{range}.pbf',
        'sprite': 'mapbox://sprites/mapbox/streets-v12', 'fog': {'color': 'white'}, 'projection': {'name': 'globe'},
        'sources': {'composite': {'type': 'vector', 'url': 'mapbox://mapbox.mapbox-streets-v8,mapbox.mapbox-terrain-v2'}},
        'layers': [
            {'id': 'land', 'type': 'background', 'paint': {'background-color': 'hsl(20, 20%, 95%)'}},
            {'id': 'landcover', 'type': 'fill', 'source': 'composite', 'source-layer': 'landcover',
             'paint': {'fill-color': 'hsl(110, 41%, 78%)'}},
            {'id': 'poi-label', 'type': 'symbol', 'source': 'composite', 'source-layer': 'poi_label', 'layout': {}},
            {'id': 'road-label', 'type': 'symbol', 'source': 'composite', 'source-layer': 'road', 'layout': {}},
        ]}


class ControlsTest(SimpleTestCase):
    """Spec: map-style-editor / Requirement: The editor page edits a workspace style with bounded controls."""

    def test_settings_are_cleaned(self):
        """
        GIVEN a posted document with a bad colour, an unknown key, a preset and an out-of-range zoom
        WHEN it is cleaned
        THEN park is refused, foo is dropped, roads is the strong triple and the zoom is clamped to 16
        """
        settings, errors = controls.clean_settings({'park': 'red', 'foo': 1, 'roads': 'strong', 'place_names_maxzoom': 40,
                                                    'land': '#ffffff', 'water': '#cfe2f2', 'boundary': '#9a9a9a',
                                                    'labels_major': '#333333', 'labels_minor': '#777777'})
        self.assertEqual(list(errors), ['park'])
        self.assertNotIn('foo', settings)
        self.assertEqual(settings['roads'], controls.ROAD_PRESETS['strong'])
        self.assertEqual(settings['place_names_maxzoom'], 16)

    def test_paper_a_round_trips(self):
        """
        GIVEN Paper A's settings document
        WHEN it is turned into form values and cleaned back
        THEN the generator receives the same document (name and base aside)
        """
        with open('scripts/map_styles/paper_a.json') as handle:
            paper = json.load(handle)
        cleaned, errors = controls.clean_settings(controls.form_values(paper))
        self.assertEqual(errors, {})
        expected = {k: v for k, v in paper.items() if k not in ('name', 'base')}
        self.assertEqual(cleaned, expected)

    def test_removal_kept_means_no_key(self):
        """
        GIVEN a document keeping POI
        WHEN it is cleaned
        THEN the generator gets no `poi` key (absent = leave the base as it is)
        """
        cleaned, _ = controls.clean_settings({'poi': True, 'land': '#ffffff', 'park': '#dcefd2', 'water': '#cfe2f2',
                                              'boundary': '#9a9a9a', 'labels_major': '#333333', 'labels_minor': '#777777'})
        self.assertNotIn('poi', cleaned)
        self.assertIs(cleaned['paths'], False)


class PreviewRewriteTest(SimpleTestCase):
    """Spec: map-style-editor / Requirement: The preview endpoint renders the current settings for MapLibre."""

    def test_rewritten_style(self):
        """
        GIVEN the base style and settings removing POI and colouring parks
        WHEN the style is built for MapLibre
        THEN no poi_label layer remains, landcover is the park colour, sources are https v4 URLs with the token,
             glyphs and sprite are https, and fog/projection are gone
        """
        from survey.map_styles.generator import apply_settings
        style = preview.for_maplibre(apply_settings(BASE, {'poi': False, 'park': '#dcefd2'}), 'pk.test')
        self.assertFalse([l for l in style['layers'] if l.get('source-layer') == 'poi_label'])
        landcover = [l for l in style['layers'] if l['id'] == 'landcover'][0]
        self.assertEqual(landcover['paint']['fill-color'], '#dcefd2')
        url = style['sources']['composite']['url']
        self.assertTrue(url.startswith('https://api.mapbox.com/v4/'))
        self.assertIn('access_token=pk.test', url)
        self.assertTrue(style['glyphs'].startswith('https://api.mapbox.com/fonts/v1/'))
        self.assertTrue(style['sprite'].startswith('https://api.mapbox.com/styles/v1/mapbox/streets-v12/sprite'))
        for key in ('fog', 'projection'):
            self.assertNotIn(key, style)


class _EditorFixture(TestCase):
    def setUp(self):
        self.org = _make_org('EditOrg')
        self.owner = User.objects.create_user('editowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        make_sub(self.org)
        self.style = ready_style(self.org, name='House', mapbox_id='artemkonuchov/house0001')
        self.survey, self.section = _make_survey_with_section(self.org, 'edit_survey', owner=self.owner)
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')
        self.client.login(username='editowner', password='pass')
        self.edit_url = reverse('org_map_style_edit', args=[self.org.slug, self.style.uuid])
        self.save_url = reverse('org_map_style_save', args=[self.org.slug, self.style.uuid])
        self.preview_url = reverse('org_map_style_preview', args=[self.org.slug, self.style.uuid])

    def values(self, **overrides):
        values = controls.form_values(self.style.latest().settings)
        values.update(overrides)
        return values

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')


class EditorPageTest(_EditorFixture):
    """Spec: map-style-editor / Requirement: The editor page edits a workspace style with bounded controls."""

    def test_editor_opens_for_an_editor(self):
        """
        GIVEN a member with the editor role
        WHEN they open the editor of the workspace's style
        THEN the page renders the name, every control and the latest version's values
        """
        editor = User.objects.create_user('editeditor', password='pass')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        self.client.login(username='editeditor', password='pass')
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('value="House"', html)
        for key in ('poi', 'paths', 'shields', 'relief', 'regions', 'buildings', 'greyscale', 'bold_roads'):
            self.assertIn(f'data-key="{key}"', html)
        for role in ('land', 'park', 'water', 'boundary', 'labels_major', 'labels_minor'):
            self.assertIn(f'data-role="{role}"', html)
        self.assertIn('value="#dcefd2"', html)  # the park colour of the ready version
        self.assertIn('maplibre-gl', html)

    def test_editor_never_carries_the_whats_new_card(self):
        """
        GIVEN an owner who has not seen the newest changelog entry
        WHEN they open the style editor
        THEN the page carries no What's new card (it would cover the preview map) and says so in its context
        """
        from survey.models import CreatorPreferences
        CreatorPreferences.objects.update_or_create(user=self.owner, defaults={'changelog_seen': ''})
        response = self.client.get(self.edit_url)
        self.assertTrue(response.context['suppress_whats_new_card'])
        self.assertNotIn('id="whatsNewCard"', response.content.decode())

    def test_presets_and_foreign_styles_have_no_editor(self):
        """
        GIVEN a preset and a style of another workspace
        WHEN their editor URLs are opened
        THEN both answer 404
        """
        paper = MapStyle.objects.get(organization__isnull=True, key='paper')
        foreign = ready_style(_make_org('Elsewhere3'), name='Theirs')
        for uuid in (paper.uuid, foreign.uuid):
            self.assertEqual(self.client.get(reverse('org_map_style_edit', args=[self.org.slug, uuid])).status_code, 404)

    def test_viewer_is_refused(self):
        """
        GIVEN a member with the viewer role
        WHEN they open the editor or post to preview / save
        THEN every response is 403
        """
        viewer = User.objects.create_user('editviewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username='editviewer', password='pass')
        self.assertEqual(self.client.get(self.edit_url).status_code, 403)
        self.assertEqual(self.post_json(self.preview_url, self.values()).status_code, 403)
        self.assertEqual(self.post_json(self.save_url, {'settings': self.values()}).status_code, 403)

    def test_preview_endpoint(self):
        """
        GIVEN the base style served from cache
        WHEN the editor posts settings without POI
        THEN the answer is a MapLibre style with no poi_label layer and the token in its sources
        """
        with mock.patch.object(preview, 'base_style', return_value=BASE):
            response = self.post_json(self.preview_url, self.values(poi=False))
        self.assertEqual(response.status_code, 200)
        style = response.json()['style']
        self.assertFalse([l for l in style['layers'] if l.get('source-layer') == 'poi_label'])
        self.assertIn('access_token=', style['sources']['composite']['url'])

    def test_preview_unavailable(self):
        """
        GIVEN the base style cannot be fetched
        WHEN the editor posts settings
        THEN the answer is 503 with an error key
        """
        with mock.patch.object(preview, 'base_style', side_effect=preview.PreviewUnavailable('down')):
            response = self.post_json(self.preview_url, self.values())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error'], 'preview unavailable')

    def test_library_card_links_to_the_editor(self):
        """
        GIVEN the library page
        WHEN it renders
        THEN the workspace style's card carries Edit and no rename form, and a preset's card carries no Edit
        """
        html = self.client.get(reverse('org_map_styles', args=[self.org.slug])).content.decode()
        self.assertIn(self.edit_url, html)
        self.assertNotIn('/rename/', html)
        paper = MapStyle.objects.get(organization__isnull=True, key='paper')
        self.assertNotIn(f'/map-styles/{paper.uuid}/edit/', html)


class SaveTest(_EditorFixture):
    """Spec: map-style-editor / Requirement: Save publishes a new version and leaves live surveys where they are."""

    def test_save_creates_version_2(self):
        """
        GIVEN a style with one ready version and a published survey pinned to it
        WHEN an editor saves changed settings
        THEN version 2 is pending with those settings, the task is enqueued, the name is kept,
             and the survey still resolves to version 1
        """
        self.survey.status = 'published'
        self.survey.basemaps = [self.style.basemap_key]
        self.survey.default_basemap = self.style.basemap_key
        basemap_registry.pin_latest(self.survey)
        self.survey.save()
        with mock.patch.object(style_tasks.publish_map_style_version, 'delay') as delay, \
                self.captureOnCommitCallbacks(execute=True):
            response = self.post_json(self.save_url, {'name': 'House v2', 'settings': self.values(park='#cfe6b8', poi=True)})
        self.assertEqual(response.status_code, 200, response.content)
        version = self.style.versions.get(number=2)
        self.assertEqual(version.status, MapStyleVersion.PENDING)
        self.assertEqual(version.settings['park'], '#cfe6b8')
        self.assertNotIn('poi', version.settings)
        delay.assert_called_once_with(version.pk)
        self.style.refresh_from_db()
        self.assertEqual(self.style.name, 'House v2')
        self.assertEqual(basemap_registry.resolve(self.style.basemap_key, self.org, self.survey.basemap_pins).version, 1)
        MapStyleVersion.objects.filter(pk=version.pk).update(status=MapStyleVersion.READY, mapbox_style_id='artemkonuchov/house0002')
        self.assertEqual(basemap_registry.resolve(self.style.basemap_key, self.org, self.survey.basemap_pins).version, 1)
        self.assertEqual(basemap_registry.resolve(self.style.basemap_key, self.org, None).version, 2)

    def test_save_while_pending(self):
        """
        GIVEN the latest version is pending
        WHEN a save is posted
        THEN the response is 409 and no version is created
        """
        MapStyleVersion.objects.create(style=self.style, number=2, settings={}, status=MapStyleVersion.PENDING)
        response = self.post_json(self.save_url, {'settings': self.values()})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.style.versions.count(), 2)

    def test_bad_colour_is_refused(self):
        """
        GIVEN a save with a colour that is not #rrggbb
        WHEN it is posted
        THEN the response is 400 naming the field and no version is created
        """
        response = self.post_json(self.save_url, {'settings': self.values(water='blue')})
        self.assertEqual(response.status_code, 400)
        self.assertIn('water', response.json()['errors'])
        self.assertEqual(self.style.versions.count(), 1)

    def test_free_workspace_with_spent_trial(self):
        """
        GIVEN a Free workspace whose map_styles trial allowance is spent
        WHEN a save is posted
        THEN the Pro-required page answers and no version is created
        """
        from billing.models import Subscription
        Subscription.objects.filter(organization=self.org).delete()
        trial_used_elsewhere(self.org)
        response = self.post_json(self.save_url, {'settings': self.values()})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.style.versions.count(), 1)
        self.assertEqual(self.client.get(self.edit_url).status_code, 200)  # the page still opens, Save is off


class RepinTest(_EditorFixture):
    """Spec: map-style-editor / Requirement: Live base-map edits re-pin the survey."""

    def _settings_data(self, **extra):
        data = {'name': 'edit_survey', 'redirect_url': '#', 'visibility': 'private', 'show_branding': 'on',
                'basemaps': json.dumps(['streets', self.style.basemap_key]), 'default_basemap': self.style.basemap_key}
        data.update(extra)
        return data

    def test_settings_edit_on_a_live_survey(self):
        """
        GIVEN a published survey with empty pins
        WHEN its base maps are saved through the settings service and version 2 then becomes ready
        THEN the survey's pins name version 1 and its respondent page keeps version 1's tiles
        """
        self.survey.status = 'published'
        self.survey.save()
        svc_surveys.update_settings(Actor(user=self.owner), self.survey, self._settings_data())
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.basemap_pins, {str(self.style.uuid): 1})
        ready_style(self.org, mapbox_id='artemkonuchov/house0002', number=2, style=self.style)
        response = self.client.get(f'/surveys/{self.survey.uuid}/{self.section.name}/')
        self.assertContains(response, 'artemkonuchov/house0001/')
        self.assertNotContains(response, 'artemkonuchov/house0002/')

    def test_section_override_on_a_live_survey(self):
        """
        GIVEN a published survey with empty pins
        WHEN a section's override is set to the style through the sections service
        THEN the survey's pins name the style's ready version
        """
        self.survey.status = 'published'
        self.survey.save()
        svc_sections.set_map(Actor(user=self.owner), self.section, lat=55.6, lng=12.5, zoom=12,
                             override_basemap=self.style.basemap_key)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.basemap_pins, {str(self.style.uuid): 1})

    def test_draft_is_not_pinned(self):
        """
        GIVEN a draft survey
        WHEN the same settings edit is made
        THEN its pins stay empty
        """
        svc_surveys.update_settings(Actor(user=self.owner), self.survey, self._settings_data())
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.basemap_pins, {})


class PrintTabTest(_EditorFixture):
    """Spec: map-style-editor / Requirement: The print tab shows the last saved version."""

    def test_print_frame_state(self):
        """
        GIVEN a style whose latest ready version is artemkonuchov/house0001 and a positioned survey
        WHEN the editor renders
        THEN its state carries that style id, the survey's frame and the static frame size,
             which the page turns into a Static Images URL with fresh=true
        """
        from django.contrib.gis.geos import Point
        self.survey.start_map_postion = Point(12.57, 55.68)
        self.survey.start_map_zoom = 13
        self.survey.save()
        html = self.client.get(self.edit_url).content.decode()
        state = json.loads(html.split('<script id="mse-state"')[1].split('</script>')[0].split('>', 1)[1])
        self.assertEqual(state['version']['ready_style_id'], 'artemkonuchov/house0001')
        self.assertEqual(state['surveys'][0]['uuid'], str(self.survey.uuid))
        self.assertEqual((state['surveys'][0]['lat'], state['surveys'][0]['lng'], state['surveys'][0]['zoom']), (55.68, 12.57, 13))
        self.assertEqual(state['frame'], [900, 550])
        with open('survey/assets/js/map_style_editor.js') as handle:
            script = handle.read()
        self.assertIn('fresh=true', script)
        self.assertIn('/static/', script)


class ContrastTest(SimpleTestCase):
    """Spec: map-style-editor / Requirement: Contrast warnings are advice, not a gate."""

    def test_pale_parks_on_white(self):
        """
        GIVEN land #ffffff and parks #f4f9f0
        WHEN the greyscale luminance difference is computed the way the page does
        THEN it is below 0.08 (a warning) while Paper A's own parks #dcefd2 are not, the page uses
             that threshold, and the generator still accepts the settings
        """
        from survey.map_styles.generator import parse_color, to_grey_hex

        def grey(hex_colour):
            return int(to_grey_hex(*parse_color(hex_colour))[1:3], 16) / 255

        self.assertLess(abs(grey('#ffffff') - grey('#f4f9f0')), 0.08)
        self.assertGreater(abs(grey('#ffffff') - grey('#dcefd2')), 0.08)
        self.assertGreater(abs(grey('#ffffff') - grey('#2f8f86')), 0.08)
        with open('survey/assets/js/map_style_editor.js') as handle:
            self.assertIn('< 0.08', handle.read())
        cleaned, errors = controls.clean_settings({'land': '#ffffff', 'park': '#f4f9f0', 'water': '#cfe2f2', 'boundary': '#9a9a9a',
                                                   'labels_major': '#333333', 'labels_minor': '#777777'})
        self.assertEqual(errors, {})
        self.assertEqual(cleaned['park'], '#f4f9f0')
