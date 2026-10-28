"""Tests for the `basemap-providers` capability (openspec/specs/basemap-providers/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from io import BytesIO
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, SurveyCollaborator
from survey.serialization import serialize_survey_to_dict, export_survey_to_zip, import_survey_from_zip
from survey.versioning import clone_survey_for_draft
from survey.tests.helpers import _make_org


class BasemapTest(TestCase):
    """Tests for satellite/topographic basemap options."""

    def setUp(self):
        self.org = _make_org('BasemapOrg')
        self.user = User.objects.create_user(username='bmuser', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='basemap_test', organization=self.org, created_by=self.user,
            status='published', basemaps=['satellite', 'topo'],
        )
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section',
            code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Mark a point', input_type='point',
        )

    def test_basemaps_field_defaults_to_all_three(self):
        """
        GIVEN a new SurveyHeader with no basemaps specified
        WHEN the survey is created
        THEN basemaps defaults to all three layers
        """
        survey = SurveyHeader.objects.create(
            name='default_bm', organization=self.org, created_by=self.user,
        )
        self.assertEqual(survey.basemaps, ['streets', 'satellite', 'topo'])

    def test_respondent_page_renders_satellite_tile_url(self):
        """
        GIVEN a survey with basemaps=["satellite", "topo"]
        WHEN the respondent loads the section page
        THEN the HTML contains the Esri satellite tile URL
        """
        resp = self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.assertContains(resp, 'server.arcgisonline.com')

    def test_respondent_page_renders_topo_tile_url(self):
        """
        GIVEN a survey with basemaps=["satellite", "topo"]
        WHEN the respondent loads the section page
        THEN the HTML contains the Mapbox Outdoors tile URL
        """
        resp = self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.assertContains(resp, 'mapbox/outdoors-v12')

    @override_settings(MAPBOX_OUTDOORS_URL='https://example.test/custom-topo/{z}/{x}/{y}.png')
    def test_topo_tile_url_comes_from_settings(self):
        """
        GIVEN MAPBOX_OUTDOORS_URL overridden to a custom style URL
        WHEN the respondent loads the section page
        THEN the rendered topo layer uses that URL, proving no template literal remains
        """
        resp = self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.assertContains(resp, 'https://example.test/custom-topo/')

    def test_respondent_page_uses_no_volunteer_tile_servers(self):
        """
        GIVEN a survey with every basemap enabled
        WHEN the respondent loads the section page
        THEN the HTML requests tiles from neither OSM's nor OpenTopoMap's volunteer servers

        Guard for the tile usage policy: a creator once got a Response Map tiled
        entirely with OSM's "Access blocked - 403" placeholder.
        """
        self.survey.basemaps = ['streets', 'satellite', 'topo']
        self.survey.save()
        resp = self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.assertNotContains(resp, 'tile.openstreetmap.org')
        self.assertNotContains(resp, 'tile.opentopomap.org')

    def test_empty_basemaps_falls_back_to_streets_in_js(self):
        """
        GIVEN a survey with basemaps=[]
        WHEN the respondent loads the section page
        THEN the JS fallback renders streets
        """
        self.survey.basemaps = []
        self.survey.save()
        resp = self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.assertContains(resp, "['streets']")

    def test_serialization_includes_basemaps(self):
        """
        GIVEN a survey with basemaps=["satellite", "topo"]
        WHEN serialize_survey_to_dict is called
        THEN the result includes basemaps key with the list
        """
        result = serialize_survey_to_dict(self.survey)
        self.assertEqual(result['basemaps'], ['satellite', 'topo'])

    def test_import_preserves_basemaps(self):
        """
        GIVEN an exported survey with basemaps=["satellite"]
        WHEN imported via import_survey_from_zip
        THEN the new SurveyHeader has basemaps=["satellite"]
        """
        self.survey.basemaps = ['satellite']
        self.survey.save()
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf)
        buf.seek(0)
        imported, warnings = import_survey_from_zip(buf, organization=self.org, created_by=self.user)
        self.assertEqual(imported.basemaps, ['satellite'])

    def test_clone_copies_basemaps(self):
        """
        GIVEN a published survey with basemaps=["satellite", "topo"]
        WHEN clone_survey_for_draft is called
        THEN the draft has the same basemaps
        """
        from survey.versioning import clone_survey_for_draft
        draft = clone_survey_for_draft(self.survey)
        self.assertEqual(draft.basemaps, ['satellite', 'topo'])

    def test_editor_settings_saves_basemaps(self):
        """
        GIVEN a logged-in survey owner
        WHEN basemaps are submitted via the settings form
        THEN the survey's basemaps field is updated
        """
        self.client.login(username='bmuser', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/settings/'
        resp = self.client.post(url, {
            'name': self.survey.name,
            'redirect_url': '#',
            'available_languages': '[]',
            'visibility': 'private',
            'thanks_html': '{}',
            'basemaps': '["streets", "satellite"]',
        })
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.basemaps, ['streets', 'satellite'])

    def test_default_basemap_auto_fixed_when_unset(self):
        """
        GIVEN a survey settings POST that omits default_basemap entirely
        WHEN the form is validated
        THEN default_basemap is auto-set to the first enabled basemap
        instead of being saved as NULL.
        """
        self.client.login(username='bmuser', password='pass')
        self.survey.default_basemap = None
        self.survey.save(update_fields=['default_basemap'])

        url = f'/editor/surveys/{self.survey.uuid}/settings/'
        self.client.post(url, {
            'name': self.survey.name,
            'redirect_url': '#',
            'available_languages': '[]',
            'visibility': 'private',
            'thanks_html': '{}',
            'basemaps': '["satellite", "topo"]',
        })
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.default_basemap, 'satellite')

    def test_default_basemap_reassigned_when_removed_from_basemaps(self):
        """
        GIVEN a survey whose default_basemap is "satellite"
        WHEN the owner removes "satellite" from basemaps but submits the
            stale default_basemap value with the form
        THEN default_basemap is reassigned to the first remaining basemap.
        """
        self.client.login(username='bmuser', password='pass')
        self.survey.basemaps = ['satellite', 'topo']
        self.survey.default_basemap = 'satellite'
        self.survey.save(update_fields=['basemaps', 'default_basemap'])

        url = f'/editor/surveys/{self.survey.uuid}/settings/'
        self.client.post(url, {
            'name': self.survey.name,
            'redirect_url': '#',
            'available_languages': '[]',
            'visibility': 'private',
            'thanks_html': '{}',
            'basemaps': '["streets", "topo"]',
            'default_basemap': 'satellite',
        })
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.default_basemap, 'streets')
        self.assertEqual(self.survey.basemaps, ['streets', 'topo'])

    def test_default_basemap_select_drops_empty_option(self):
        """
        GIVEN a logged-in survey owner viewing the settings page
        WHEN the default_basemap select is rendered
        THEN there is no empty/blank option in the dropdown.
        """
        self.client.login(username='bmuser', password='pass')
        resp = self.client.get(f'/editor/surveys/{self.survey.uuid}/settings/')
        self.assertNotIn('<option value="" selected>---------</option>', resp.content.decode())
        self.assertNotIn('<option value="">---------</option>', resp.content.decode())


class VolunteerTileServerGuardTest(TestCase):
    """No creator surface requests tiles from a volunteer-run server.

    basemap-mapbox-outdoors moved every basemap to Mapbox, but the report that
    prompted it came from Responses -> Overview, whose thumbnail map never went
    through basemap_layers.html and kept a hard-coded tile.openstreetmap.org
    literal. The same literal sat in the reference-layer style preview. These
    tests render the two pages the original guards did not.
    """

    VOLUNTEER_HOSTS = ('tile.openstreetmap.org', 'tile.opentopomap.org')

    def setUp(self):
        self.org = _make_org('TileGuardOrg')
        self.owner = User.objects.create_user('tileguard', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='tileguard', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.survey = SurveyHeader.objects.create(
            name='tile_guard', organization=self.org, created_by=self.owner, status='published',
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')
        section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        q = Question.objects.create(
            survey_section=section, name='Where', code='q1', input_type='point', order_number=1,
        )
        sess = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=sess, question=q, point=Point(13.405, 52.52))

    @override_settings(RESPONSES_V2=True, MAPBOX_URL='https://example.test/streets/{z}/{x}/{y}')
    def test_responses_overview_thumbnail_uses_mapbox(self):
        """
        GIVEN a survey owner, Responses v2 on and MAPBOX_URL overridden
        WHEN they open Responses, whose Overview pane renders a view-only thumbnail map
        THEN the page carries the overridden Mapbox URL and names no volunteer tile host
        """
        r = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'editor/partials/analytics_overview_pane.html')
        self.assertContains(r, 'https://example.test/streets/')
        for host in self.VOLUNTEER_HOSTS:
            self.assertNotContains(r, host)

    def test_survey_settings_panel_uses_no_volunteer_tile_server(self):
        """
        GIVEN a survey owner
        WHEN they load the survey settings panel, whose reference-layer cards carry a style preview map
        THEN the rendered HTML names no volunteer tile host
        """
        r = self.client.get(f'/editor/surveys/{self.survey.uuid}/settings-panel/')
        self.assertEqual(r.status_code, 200)
        for host in self.VOLUNTEER_HOSTS:
            self.assertNotContains(r, host)


class VolunteerTileServerSweepTest(SimpleTestCase):
    """A literal on a surface no page test renders must still fail the suite."""

    VOLUNTEER_HOSTS = ('tile.openstreetmap.org', 'tile.opentopomap.org')

    def test_no_template_or_script_names_a_volunteer_tile_host(self):
        """
        GIVEN every template and first-party script under survey/
        WHEN each is scanned for volunteer tile hosts
        THEN none names tile.openstreetmap.org or tile.opentopomap.org
        """
        import pathlib
        app = pathlib.Path(__file__).resolve().parent.parent
        offenders = []
        for root in (app / 'templates', app / 'assets' / 'js'):
            for path in sorted(root.rglob('*')):
                if path.suffix not in ('.html', '.js') or path.name.endswith('.min.js'):
                    continue
                text = path.read_text(encoding='utf-8', errors='ignore')
                for host in self.VOLUNTEER_HOSTS:
                    if host in text:
                        offenders.append(f'{path.relative_to(app)}: {host}')
        self.assertEqual(offenders, [], 'volunteer tile host referenced in: ' + ', '.join(offenders))
