"""Tests for the `map-style-library` capability (change map-styles-library, #542; epic #545).

Workspace map styles as rows: the resolver and provider table every surface reads, the
presets, version pinning, the library page and its actions, the Pro gate, and the Celery
publishing task (run inline with a fake Styles API client).
"""
import glob
import os
import re
from io import BytesIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from billing.tests.helpers import make_sub, trial_used_elsewhere
from survey import basemaps as basemap_registry
from survey.map_styles import tasks as style_tasks
from survey.map_styles.generator import MapboxApiError
from survey.models import (MapStyle, MapStyleVersion, Membership, PublicResultsBlock, PublicResultsPage,
                           SurveyCollaborator, SurveyHeader, SurveySection)
from survey.print import static_map
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.services.context import Actor
from survey.services import publishing as svc_publishing
from survey.tests.helpers import _make_org, _make_survey_with_section
from survey.versioning import clone_survey_for_draft, publish_draft

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(TESTS_DIR))


def ready_style(org, name='House style', mapbox_id='artemkonuchov/ready0001', number=1, settings=None,
                style=None):
    """A workspace style with one ready version (the shape the migration and the task leave)."""
    style = style or MapStyle.objects.create(organization=org, name=name, base='mapbox/streets-v12')
    MapStyleVersion.objects.create(style=style, number=number, settings={'park': '#dcefd2'} if settings is None else settings,
                                   mapbox_style_id=mapbox_id, status=MapStyleVersion.READY)
    return style


class _LibraryFixture(TestCase):
    def setUp(self):
        self.org = _make_org('StyleOrg')
        self.owner = User.objects.create_user('styleowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey, self.section = _make_survey_with_section(self.org, 'style_survey', owner=self.owner)
        self.survey.status = 'published'
        self.survey.basemaps = ['streets']
        self.survey.default_basemap = 'streets'
        self.survey.save()
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')
        self.client.login(username='styleowner', password='pass')

    def respondent_html(self):
        response = self.client.get(f'/surveys/{self.survey.uuid}/{self.section.name}/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()


class PresetsAndVersionsTest(_LibraryFixture):
    """Spec: map-style-library / Requirement: A map style is a workspace row with immutable versions."""

    def test_presets_exist_after_migration(self):
        """
        GIVEN the migrated database
        WHEN the presets are read
        THEN five preset styles with no workspace exist, each with version 1 ready, and
             streets, topo and satellite resolve to their providers
        """
        presets = MapStyle.objects.filter(organization__isnull=True)
        self.assertEqual(sorted(presets.values_list('key', flat=True)),
                         ['paper', 'paper_b', 'satellite', 'streets', 'topo'])
        for preset in presets:
            self.assertEqual(preset.latest_ready().number, 1)
        streets = basemap_registry.resolve('streets', None)
        self.assertIn('mapbox/streets-v12', streets.tile_url)
        self.assertEqual((streets.tile_size, streets.zoom_offset), (512, -1))
        self.assertIn('mapbox/outdoors-v12', basemap_registry.resolve('topo', None).tile_url)
        satellite = basemap_registry.resolve('satellite', None)
        self.assertIn('server.arcgisonline.com', satellite.tile_url)
        self.assertEqual(satellite.static_style, 'mapbox/satellite-streets-v12')
        self.assertEqual(satellite.tile_size, 256)

    def test_a_ready_version_is_not_edited(self):
        """
        GIVEN a ready version
        WHEN its settings or Mapbox id are changed and saved
        THEN the save is refused with a validation error, and status alone may change
        """
        style = ready_style(self.org)
        version = MapStyleVersion.objects.get(style=style)
        version.settings = {'park': '#ff0000'}
        with self.assertRaises(ValidationError):
            version.save()
        version = MapStyleVersion.objects.get(style=style)
        version.mapbox_style_id = 'artemkonuchov/other'
        with self.assertRaises(ValidationError):
            version.save()
        version = MapStyleVersion.objects.get(style=style)
        version.error = 'note'
        version.save()  # a non-frozen field is fine


class ResolverAndTableTest(_LibraryFixture):
    """Spec: map-style-library / Requirement: One resolver and one provider table."""

    def test_workspace_style_on_the_respondent_page(self):
        """
        GIVEN a survey enabling the workspace's ready style
        WHEN the respondent page renders
        THEN the provider table has the key with the hosted URL, tileSize 512 and zoomOffset -1,
             and the layer switcher lists the style under its name
        """
        style = ready_style(self.org, name='House style', mapbox_id='artemkonuchov/house01')
        self.survey.basemaps = ['streets', style.basemap_key]
        self.survey.save()
        html = self.respondent_html()
        self.assertIn(f'"{style.basemap_key}"', html)
        self.assertIn('artemkonuchov/house01/tiles/512/', html)
        self.assertIn('"tileSize": 512', html)
        self.assertIn('"zoomOffset": -1', html)
        self.assertIn('"House style"', html)

    def test_another_workspaces_style_does_not_resolve(self):
        """
        GIVEN a survey naming a style owned by a different workspace
        WHEN the respondent page renders and the key is resolved
        THEN the key is absent from the table, the resolver answers None, and the page
             falls back to the first enabled key that resolves
        """
        other = _make_org('OtherOrg')
        foreign = ready_style(other, name='Foreign', mapbox_id='artemkonuchov/foreign1')
        self.survey.basemaps = [foreign.basemap_key, 'topo']
        self.survey.default_basemap = foreign.basemap_key
        self.survey.save()
        self.assertIsNone(basemap_registry.resolve(foreign.basemap_key, self.org))
        self.assertEqual(basemap_registry.first_available(self.survey.basemaps, self.org), 'topo')
        html = self.respondent_html()
        self.assertNotIn('artemkonuchov/foreign1', html)
        self.assertIn('mapbox/outdoors-v12', html)

    def test_no_template_holds_a_mapbox_url(self):
        """
        GIVEN every template under survey/templates/
        WHEN they are scanned
        THEN none names a Mapbox style endpoint or a literal style id
        """
        offenders = []
        for path in glob.glob(os.path.join(REPO, 'survey', 'templates', '**', '*.html'), recursive=True):
            with open(path, errors='replace') as handle:
                body = handle.read()
            if re.search(r'api\.mapbox\.com/styles/v1/|mapbox/(streets|outdoors|satellite)-v1\d|cmw4[a-z0-9]{20}', body):
                offenders.append(os.path.relpath(path, REPO))
        self.assertEqual(offenders, [])

    def test_print_resolves_the_same_key(self):
        """
        GIVEN a survey whose default basemap is a workspace style
        WHEN the printed frame is resolved
        THEN the frame names that version's Mapbox style id and records the key
        """
        style = ready_style(self.org, mapbox_id='artemkonuchov/printme1')
        self.survey.default_basemap = style.basemap_key
        self.survey.basemaps = [style.basemap_key]
        self.survey.save()
        spec = static_map.resolve_frame(self.section, self.survey)
        self.assertEqual(spec.basemap, style.basemap_key)
        self.assertEqual(spec.static_style, 'artemkonuchov/printme1')
        self.assertEqual(static_map.basemap_style('satellite'), 'mapbox/satellite-streets-v12')

    @override_settings(MAPBOX_TILES_URL='https://example.test/{style}/tiles/256/{z}/{x}/{y}.png?t={accessToken}')
    def test_tile_template_is_configurable(self):
        """
        GIVEN MAPBOX_TILES_URL overridden to a 256-px template
        WHEN streets is resolved
        THEN the URL follows the template and the Leaflet options drop the 512-px shape
        """
        streets = basemap_registry.resolve('streets', None)
        self.assertEqual(streets.tile_url, 'https://example.test/mapbox/streets-v12/tiles/256/{z}/{x}/{y}.png?t={accessToken}')
        self.assertNotIn('tileSize', streets.leaflet()['opts'])


class PinningTest(_LibraryFixture):
    """Spec: map-style-library / Requirement: Published surveys pin the version they were published with."""

    def _style_with_two_versions(self):
        style = ready_style(self.org, mapbox_id='artemkonuchov/v1')
        self.survey.basemaps = ['streets', style.basemap_key]
        self.survey.default_basemap = style.basemap_key
        self.survey.save()
        basemap_registry.pin_latest(self.survey)
        self.survey.save(update_fields=['basemap_pins'])
        ready_style(self.org, mapbox_id='artemkonuchov/v2', number=2, style=style)
        return style

    def test_a_new_version_does_not_change_a_live_survey(self):
        """
        GIVEN a published survey pinned to version 1 and a ready version 2
        WHEN the respondent page renders, and again after the survey is published again
        THEN it shows version 1's tiles first and version 2's after the publication
        """
        style = self._style_with_two_versions()
        self.assertEqual(self.survey.basemap_pins, {str(style.uuid): 1})
        self.assertIn('artemkonuchov/v1/', self.respondent_html())
        self.survey.status = 'closed'
        self.survey.save()
        svc_publishing.transition(Actor(user=self.owner), self.survey, 'published')
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.basemap_pins, {str(style.uuid): 2})
        self.assertIn('artemkonuchov/v2/', self.respondent_html())

    def test_draft_shows_the_latest(self):
        """
        GIVEN that survey
        WHEN a draft copy is created
        THEN the draft has no pins and resolves to version 2
        """
        style = self._style_with_two_versions()
        draft = clone_survey_for_draft(self.survey)
        self.assertEqual(draft.basemap_pins, {})
        self.assertEqual(basemap_registry.resolve(style.basemap_key, self.org, draft.basemap_pins).version, 2)

    def test_pins_travel_to_the_archived_version(self):
        """
        GIVEN that survey and a draft copy
        WHEN the draft is published
        THEN the archived header carries the old pins, basemaps and default, and the
             canonical survey is pinned to version 2
        """
        style = self._style_with_two_versions()
        draft = clone_survey_for_draft(self.survey)
        canonical = publish_draft(draft)
        archived = SurveyHeader.objects.get(canonical_survey=canonical, is_canonical=False)
        self.assertEqual(archived.basemap_pins, {str(style.uuid): 1})
        self.assertEqual(archived.basemaps, ['streets', style.basemap_key])
        self.assertEqual(archived.default_basemap, style.basemap_key)
        self.assertEqual(canonical.basemap_pins, {str(style.uuid): 2})


class LibraryPageTest(_LibraryFixture):
    """Spec: map-style-library / Requirement: The library page lists presets and workspace styles."""

    def test_usage_count(self):
        """
        GIVEN three surveys, two of which name the style (one as a section override only)
        WHEN the library page renders
        THEN the card says the style is used in 2 surveys and the presets are marked
        """
        style = ready_style(self.org)
        self.survey.basemaps = ['streets', style.basemap_key]
        self.survey.save()
        second, second_section = _make_survey_with_section(self.org, 'second', owner=self.owner)
        second_section.override_basemap = style.basemap_key
        second_section.save()
        _make_survey_with_section(self.org, 'third', owner=self.owner)
        html = self.client.get(reverse('org_map_styles', args=[self.org.slug])).content.decode()
        self.assertIn('used in 2 surveys', html)
        self.assertEqual(html.count('Preset'), 5)
        self.assertEqual(basemap_registry.usage(self.org), {str(style.uuid): 2})

    def test_pending_version_is_visible_and_not_offered(self):
        """
        GIVEN a style whose only version is pending
        WHEN the library page and the survey settings render
        THEN the card shows Publishing… and polls, and the pickers do not offer the style
        """
        style = MapStyle.objects.create(organization=self.org, name='Soon', base='mapbox/streets-v12')
        MapStyleVersion.objects.create(style=style, number=1, settings={}, status=MapStyleVersion.PENDING)
        html = self.client.get(reverse('org_map_styles', args=[self.org.slug])).content.decode()
        self.assertIn('Publishing…', html)
        self.assertIn('hx-trigger="every 3s"', html)
        self.assertNotIn(style.basemap_key, dict(basemap_registry.choices_for(self.org)))
        self.assertIsNone(basemap_registry.resolve(style.basemap_key, self.org))


class NewStyleTest(_LibraryFixture):
    """Spec: map-style-library / Requirement: New style starts from a preset and opens the editor."""

    def setUp(self):
        super().setUp()
        make_sub(self.org)
        self.new_url = reverse('org_map_style_new', args=[self.org.slug])

    def test_new_style_from_paper_b(self):
        """
        GIVEN a Pro editor
        WHEN they choose New style → Paper B
        THEN "New style" exists with version 1 pending carrying Paper B's settings, the task is enqueued,
             and the response opens its editor
        """
        paper_b = MapStyle.objects.get(organization__isnull=True, key='paper_b')
        with mock.patch.object(style_tasks.publish_map_style_version, 'delay') as delay, \
                self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.new_url, {'base': 'paper_b'})
        style = MapStyle.objects.get(organization=self.org)
        self.assertEqual(style.name, 'New style')
        self.assertEqual(response['Location'], reverse('org_map_style_edit', args=[self.org.slug, style.uuid]))
        version = style.versions.get()
        self.assertEqual((version.number, version.status), (1, MapStyleVersion.PENDING))
        self.assertEqual(version.settings, paper_b.latest_ready().settings)
        delay.assert_called_once_with(version.pk)
        self.assertEqual(self.client.get(response['Location']).status_code, 200)  # the editor opens on a pending style

    def test_second_new_style(self):
        """
        GIVEN an existing "New style"
        WHEN another is created
        THEN it is "New style (2)"
        """
        with mock.patch.object(style_tasks.publish_map_style_version, 'delay'):
            self.client.post(self.new_url, {'base': 'streets'})
            self.client.post(self.new_url, {'base': 'streets'})
        self.assertEqual(sorted(MapStyle.objects.filter(organization=self.org).values_list('name', flat=True)),
                         ['New style', 'New style (2)'])

    def test_menu_lists_rebuildable_presets_only(self):
        """
        GIVEN the library
        WHEN an editor and then a viewer open it
        THEN the editor's New style menu offers streets, paper and paper_b only; the viewer sees no New style;
             a post naming satellite creates nothing
        """
        html = self.client.get(reverse('org_map_styles', args=[self.org.slug])).content.decode()
        menu = html[html.index('id="map-style-new"'):html.index('id="map-style-import"')]
        self.assertEqual(re.findall(r'data-base="([a-z_]+)"', menu), ['streets', 'paper', 'paper_b'])
        self.client.post(self.new_url, {'base': 'satellite'})
        self.assertFalse(MapStyle.objects.filter(organization=self.org).exists())
        viewer = User.objects.create_user('newviewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username='newviewer', password='pass')
        self.assertNotIn('id="map-style-new"', self.client.get(reverse('org_map_styles', args=[self.org.slug])).content.decode())
        self.assertEqual(self.client.post(self.new_url, {'base': 'streets'}).status_code, 403)

    def test_spent_trial(self):
        """
        GIVEN a Free workspace whose map_styles allowance is spent
        WHEN it chooses New style
        THEN the Pro-required page answers and nothing is created
        """
        from billing.models import Subscription
        Subscription.objects.filter(organization=self.org).delete()
        trial_used_elsewhere(self.org)
        self.assertEqual(self.client.post(self.new_url, {'base': 'streets'}).status_code, 403)
        self.assertFalse(MapStyle.objects.filter(organization=self.org).exists())


class LibraryActionsTest(_LibraryFixture):
    """Spec: map-style-library / Requirement: Duplicate, rename and delete; Creating a style is a Pro feature."""

    def setUp(self):
        super().setUp()
        make_sub(self.org)  # Pro: creating styles is allowed
        self.paper = MapStyle.objects.get(organization__isnull=True, key='paper')

    def test_duplicate_publishes_in_the_background(self):
        """
        GIVEN a Pro editor
        WHEN they duplicate Paper A
        THEN a workspace style exists with version 1 pending carrying Paper A's settings,
             the publish task is enqueued, and after the task runs with a fake Styles API
             the version is ready with its own Mapbox id
        """
        with mock.patch.object(style_tasks.publish_map_style_version, 'delay') as delay, \
                self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('org_map_style_duplicate', args=[self.org.slug, self.paper.uuid]))
        self.assertEqual(response.status_code, 302)
        style = MapStyle.objects.get(organization=self.org)
        self.assertEqual(response['Location'], reverse('org_map_style_edit', args=[self.org.slug, style.uuid]))
        self.assertEqual(style.name, 'Paper A copy')
        version = style.versions.get()
        self.assertEqual((version.number, version.status), (1, MapStyleVersion.PENDING))
        self.assertEqual(version.settings, self.paper.latest_ready().settings)
        delay.assert_called_once_with(version.pk)

        fake = mock.Mock()
        fake.get_style.return_value = {'version': 8, 'name': 'base', 'sources': {}, 'layers': [], 'id': 'streets-v12'}
        fake.create.return_value = ({'id': 'newid0001'}, {})
        with mock.patch.object(style_tasks, 'client', return_value=fake):
            style_tasks.publish_map_style_version.apply(args=(version.pk,))
        version.refresh_from_db()
        self.assertEqual((version.status, version.mapbox_style_id), (MapStyleVersion.READY, 'artemkonuchov/newid0001'))
        self.assertNotEqual(version.mapbox_style_id, self.paper.latest_ready().mapbox_style_id)
        self.assertIn(style.basemap_key, dict(basemap_registry.choices_for(self.org)))

    def test_satellite_and_topo_have_no_duplicate(self):
        """
        GIVEN the library page
        WHEN it renders
        THEN Satellite's and Topo's cards carry no Duplicate action and Streets' card does
        """
        html = self.client.get(reverse('org_map_styles', args=[self.org.slug])).content.decode()
        for key, expected in (('satellite', False), ('topo', False), ('streets', True), ('paper', True)):
            uuid = MapStyle.objects.get(organization__isnull=True, key=key).uuid
            self.assertEqual(f'/map-styles/{uuid}/duplicate/' in html, expected, key)

    def test_delete_refused_while_in_use(self):
        """
        GIVEN a style one survey enables
        WHEN an editor deletes it
        THEN nothing changes and the message names the survey
        """
        style = ready_style(self.org)
        self.survey.basemaps = ['streets', style.basemap_key]
        self.survey.save()
        response = self.client.post(reverse('org_map_style_delete', args=[self.org.slug, style.uuid]), follow=True)
        self.assertContains(response, 'style_survey')
        style.refresh_from_db()
        self.assertIsNone(style.archived_at)

    def test_delete_of_an_unused_style(self):
        """
        GIVEN a style no survey references
        WHEN an editor deletes it
        THEN it is archived, leaves the pickers, and the Mapbox delete is enqueued
        """
        style = ready_style(self.org, mapbox_id='artemkonuchov/gone0001')
        with mock.patch.object(style_tasks.delete_mapbox_style, 'delay') as delay, \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('org_map_style_delete', args=[self.org.slug, style.uuid]))
        style.refresh_from_db()
        self.assertIsNotNone(style.archived_at)
        self.assertNotIn(style.basemap_key, dict(basemap_registry.choices_for(self.org)))
        delay.assert_called_once_with('artemkonuchov/gone0001')

    def test_rename(self):
        """
        GIVEN a workspace style
        WHEN an editor renames it
        THEN the new name shows in the pickers; a preset cannot be renamed
        """
        style = ready_style(self.org)
        self.client.post(reverse('org_map_style_rename', args=[self.org.slug, style.uuid]), {'name': 'Our map'})
        self.assertIn((style.basemap_key, 'Our map'), basemap_registry.choices_for(self.org))
        response = self.client.post(reverse('org_map_style_rename', args=[self.org.slug, self.paper.uuid]), {'name': 'X'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(MapStyle.objects.get(pk=self.paper.pk).name, 'Paper A')

    def test_viewer_cannot_act(self):
        """
        GIVEN a member with the viewer role
        WHEN they post to duplicate, rename or delete
        THEN every response is 403 and nothing changes
        """
        style = ready_style(self.org)
        User.objects.create_user('styleviewer', password='pass')
        Membership.objects.create(user=User.objects.get(username='styleviewer'), organization=self.org, role='viewer')
        self.client.login(username='styleviewer', password='pass')
        for name, args in (('org_map_style_duplicate', [self.org.slug, self.paper.uuid]),
                           ('org_map_style_rename', [self.org.slug, style.uuid]),
                           ('org_map_style_delete', [self.org.slug, style.uuid])):
            self.assertEqual(self.client.post(reverse(name, args=args), {'name': 'x'}).status_code, 403, name)
        self.assertEqual(MapStyle.objects.filter(organization=self.org).count(), 1)
        self.assertEqual(self.client.get(reverse('org_map_styles', args=[self.org.slug])).status_code, 200)

    def test_free_workspace_with_spent_trial_is_refused(self):
        """
        GIVEN a Free workspace whose owner's trial is spent
        WHEN a duplicate is posted
        THEN the Pro-required page answers and no row is created
        """
        from billing.models import Subscription
        Subscription.objects.filter(organization=self.org).delete()
        trial_used_elsewhere(self.org)
        response = self.client.post(reverse('org_map_style_duplicate', args=[self.org.slug, self.paper.uuid]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(MapStyle.objects.filter(organization=self.org).exists())

    def test_lapsed_workspace_keeps_its_maps(self):
        """
        GIVEN a Free workspace (no subscription) with a ready style a survey shows
        WHEN the respondent page and the settings choices are read
        THEN the style's tiles are served and the settings still list it
        """
        from billing.models import Subscription
        Subscription.objects.filter(organization=self.org).delete()
        trial_used_elsewhere(self.org)
        style = ready_style(self.org, mapbox_id='artemkonuchov/keepme01')
        self.survey.basemaps = [style.basemap_key]
        self.survey.default_basemap = style.basemap_key
        self.survey.save()
        self.assertIn('artemkonuchov/keepme01', self.respondent_html())
        self.assertIn(style.basemap_key, dict(basemap_registry.choices_for(self.org)))


class PickersAndImportTest(_LibraryFixture):
    """Spec: map-style-library / Requirement: Survey pickers and imports validate against the workspace's keys."""

    def test_settings_offer_the_workspace_styles(self):
        """
        GIVEN a workspace with one ready style
        WHEN the settings form saves basemaps naming it
        THEN the save succeeds, and a key of another workspace is dropped
        """
        from survey.editor_forms import SurveyHeaderForm
        style = ready_style(self.org)
        foreign = ready_style(_make_org('Elsewhere'), name='Not ours')
        form = SurveyHeaderForm({'name': 'style_survey', 'redirect_url': '#', 'visibility': 'private',
                                 'basemaps': ['streets', style.basemap_key, foreign.basemap_key],
                                 'default_basemap': style.basemap_key, 'show_branding': True},
                                instance=self.survey)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['basemaps'], ['streets', style.basemap_key])
        self.assertEqual(form.cleaned_data['default_basemap'], style.basemap_key)
        keys = [k for k, _ in form.fields['default_basemap'].choices]
        self.assertEqual(keys[:5], ['streets', 'satellite', 'topo', 'paper', 'paper_b'])
        self.assertIn(style.basemap_key, keys)
        self.assertNotIn(foreign.basemap_key, keys)

    def test_section_override_is_validated(self):
        """
        GIVEN a style of another workspace
        WHEN set_map receives its key as the section override
        THEN the service refuses, and a preset key is accepted
        """
        from survey.services import sections as svc_sections
        from survey.services.errors import ValidationFailed
        foreign = ready_style(_make_org('Elsewhere2'), name='Not ours')
        self.survey.status = 'draft'
        self.survey.save()
        with self.assertRaises(ValidationFailed):
            svc_sections.set_map(Actor(user=self.owner), self.section, lat=1, lng=2, zoom=3,
                                 override_basemap=foreign.basemap_key)
        svc_sections.set_map(Actor(user=self.owner), self.section, lat=1, lng=2, zoom=3, override_basemap='topo')
        self.section.refresh_from_db()
        self.assertEqual(self.section.override_basemap, 'topo')

    def test_public_results_block_offers_workspace_styles(self):
        """
        GIVEN a workspace style and a results page map block
        WHEN the public page renders
        THEN its provider table carries the style and the block's key is honoured
        """
        style = ready_style(self.org, mapbox_id='artemkonuchov/public01')
        page = PublicResultsPage.objects.create(survey=self.survey, slug='style-results', is_published=True)
        PublicResultsBlock.objects.create(page=page, block_type='text', order=0, basemap=style.basemap_key)
        html = self.client.get('/r/style-results/').content.decode()
        self.assertIn('artemkonuchov/public01', html)
        self.assertIn(style.basemap_key, dict(basemap_registry.choices_for(self.org)))

    def test_import_into_another_workspace(self):
        """
        GIVEN a ZIP exported with a workspace style as default and a section override
        WHEN it is imported into a workspace without that style
        THEN both become streets and the report says the style was not available
        """
        style = ready_style(self.org)
        self.survey.basemaps = ['streets', style.basemap_key]
        self.survey.default_basemap = style.basemap_key
        self.survey.save()
        self.section.override_basemap = style.basemap_key
        self.section.save()
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf)
        buf.seek(0)
        other = _make_org('Importer')
        imported, warnings = import_survey_from_zip(buf, organization=other, created_by=self.owner)
        self.assertEqual(imported.basemaps, ['streets'])
        self.assertEqual(imported.default_basemap, 'streets')
        self.assertEqual(SurveySection.objects.get(survey_header=imported).override_basemap, 'streets')
        self.assertTrue(any('not available in this workspace' in w for w in warnings), warnings)

    def test_import_into_the_same_workspace_keeps_the_style(self):
        """
        GIVEN the same ZIP
        WHEN it is imported into the workspace that owns the style
        THEN the keys are kept
        """
        style = ready_style(self.org)
        self.survey.basemaps = ['streets', style.basemap_key]
        self.survey.default_basemap = style.basemap_key
        self.survey.save()
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf)
        buf.seek(0)
        imported, _ = import_survey_from_zip(buf, organization=self.org, created_by=self.owner)
        self.assertEqual(imported.default_basemap, style.basemap_key)


class PublishingTaskTest(_LibraryFixture):
    """Spec: map-style-library / Requirement: Publishing runs in Celery on its own queue."""

    def _pending(self):
        style = MapStyle.objects.create(organization=self.org, name='Pending', base='mapbox/streets-v12')
        return MapStyleVersion.objects.create(style=style, number=1, settings={'park': '#dcefd2'})

    def test_mapbox_refuses(self):
        """
        GIVEN a Styles API answering 429 on every create
        WHEN the task runs past its retries
        THEN the version is failed with the response in error, and the card offers Try again
        """
        version = self._pending()
        fake = mock.Mock()
        fake.get_style.return_value = {'version': 8, 'name': 'b', 'sources': {}, 'layers': []}
        fake.create.side_effect = MapboxApiError('POST', '/styles/v1/x', 429, 'Too Many Requests')
        with mock.patch.object(style_tasks, 'client', return_value=fake):
            style_tasks.publish_map_style_version.apply(args=(version.pk,))
        version.refresh_from_db()
        self.assertEqual(version.status, MapStyleVersion.FAILED)
        self.assertIn('429', version.error)
        html = self.client.get(reverse('org_map_styles', args=[self.org.slug])).content.decode()
        self.assertIn('/retry/', html)

    def test_routes_and_worker_queue(self):
        """
        GIVEN the Celery settings, run_dev.sh and render.yaml
        WHEN they are read
        THEN both tasks route to `styles` and both worker command lines consume it
        """
        from django.conf import settings
        self.assertEqual(settings.CELERY_TASK_ROUTES['survey.map_styles.tasks.publish_map_style_version'], {'queue': 'styles'})
        self.assertEqual(settings.CELERY_TASK_ROUTES['survey.map_styles.tasks.delete_mapbox_style'], {'queue': 'styles'})
        for name in ('run_dev.sh', 'render.yaml'):
            with open(os.path.join(REPO, name)) as handle:
                self.assertIn('-Q celery,styles', handle.read(), name)

    def test_token_stays_on_the_worker(self):
        """
        GIVEN the templates and the mapbox context processor
        WHEN they are scanned
        THEN none references MAPBOX_STYLES_TOKEN
        """
        from survey.context_processors import mapbox
        self.assertNotIn('MAPBOX_STYLES_TOKEN', str(mapbox(None)))
        offenders = []
        for path in glob.glob(os.path.join(REPO, 'survey', 'templates', '**', '*.html'), recursive=True):
            with open(path, errors='replace') as handle:
                if 'MAPBOX_STYLES_TOKEN' in handle.read():
                    offenders.append(os.path.relpath(path, REPO))
        self.assertEqual(offenders, [])
