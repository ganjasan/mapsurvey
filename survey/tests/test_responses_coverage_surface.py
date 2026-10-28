"""Tests for the `responses-coverage-surface` capability (openspec/specs/responses-coverage-surface/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, LineString, Polygon
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.tests.helpers import _make_org


class CoverageSurfaceTest(TestCase):
    """Spec responses-coverage-surface: line and polygon answer layers on the
    Responses Map pane can be turned into a coverage surface -- the share of
    respondents covering each cell -- through the same L.SprayAgreementLayer
    the spray clouds use. The page is the contract: the LayerManager API, the
    menu gating and the sized-map guard must be on it whenever a shape layer is.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='cov_owner', password='pass')
        self.org = _make_org('CovOrg')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name='cov_survey', organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True)
        self.client.login(username='cov_owner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _answer(self, question, **geom):
        session = SurveySession.objects.create(survey=self.survey)
        return Answer.objects.create(survey_session=session, question=question, **geom)

    def _page(self):
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_shape_layers_carry_the_coverage_api_and_menu_gating(self):
        """
        GIVEN a survey with a polygon question and a line question that have answers
        WHEN the Responses page renders
        THEN the Map pane carries createCoverage/removeCoverage, the menu offers Create Coverage
             for non-point sources, and the row states the count as "N of M respondents"
        """
        poly = Question.objects.create(
            survey_section=self.section, code='Q_PG', name='Centre?', input_type='polygon', order_number=1)
        line = Question.objects.create(
            survey_section=self.section, code='Q_LN', name='Route?', input_type='line', order_number=2)
        self._answer(poly, polygon=Polygon(((13.40, 52.52), (13.41, 52.52), (13.41, 52.53), (13.40, 52.52))))
        self._answer(line, line=LineString((13.40, 52.52), (13.42, 52.53)))
        html = self._page()
        self.assertIn('LayerManager.prototype.createCoverage = function(sourceId)', html)
        self.assertIn('LayerManager.prototype.removeCoverage = function(covId)', html)
        self.assertIn("'coverage:' + sourceId", html)
        self.assertIn('L.SprayAgreementLayer.membersFromFeatures(', html)
        # The menu button appears for shape sources, and its entry is the coverage one.
        self.assertIn('window.layerManager.canCoverage(id)', html)
        self.assertIn("' Create Coverage'", html)
        self.assertIn("' Coverage exists'", html)
        self.assertIn("src.geomType !== 'Point'", html)
        self.assertIn(" of ' + st.respondents + ' respondent'", html)
        # Corridor and cell size are the popover's sliders; the corridor only for lines.
        self.assertIn("key: 'corridorMeters'", html)
        self.assertIn("key: 'cellMeters'", html)
        self.assertIn('if (slot.isLine) {', html)

    def test_filter_and_visibility_reach_the_coverage_slot(self):
        """
        GIVEN the LayerManager on the Responses page
        WHEN the session filter or a row's visibility changes
        THEN coverage slots are rebuilt through the same paths heat slots are
        """
        poly = Question.objects.create(
            survey_section=self.section, code='Q_PG', name='Centre?', input_type='polygon', order_number=1)
        self._answer(poly, polygon=Polygon(((13.40, 52.52), (13.41, 52.52), (13.41, 52.53), (13.40, 52.52))))
        html = self._page()
        set_filter = html.index('LayerManager.prototype.setFilter = function(sids)')
        set_visible = html.index('LayerManager.prototype.setLayerVisible = function(id, visible)')
        reorder = html.index('LayerManager.prototype.reorder = function(newOrder)')
        self.assertIn("slot.type === 'coverage'", html[set_filter:set_visible])
        self.assertIn("slot.type === 'coverage'", html[set_visible:reorder])
        self.assertIn('surface.setFilter(this._sids === null ? null : this._sids)', html)

    def test_coverage_creation_waits_for_a_sized_map(self):
        """
        GIVEN the Map pane starts hidden at 0x0
        WHEN coverage is created from the layer menu
        THEN the surface joins the map through whenMapSized, and the layer's own redraw
             returns early without a size
        """
        line = Question.objects.create(
            survey_section=self.section, code='Q_LN', name='Route?', input_type='line', order_number=1)
        self._answer(line, line=LineString((13.40, 52.52), (13.42, 52.53)))
        html = self._page()
        create_at = html.index('LayerManager.prototype.createCoverage = function(sourceId)')
        remove_at = html.index('LayerManager.prototype.removeCoverage = function(covId)')
        self.assertIn('whenMapSized(function() { self._rebuildCoverage(slot); });', html[create_at:remove_at])
        import pathlib
        from django.contrib.staticfiles import finders
        js = pathlib.Path(finders.find('js/spray_layer.js')).read_text()
        self.assertIn("if (!(size.x > 0 && size.y > 0)) { return this; }", js)

    def test_agreement_layer_rasterises_shapes_and_keeps_the_cloud_path(self):
        """
        GIVEN the shared agreement layer source
        WHEN it is read
        THEN shapes bin through an even-odd canvas rasteriser with a metre corridor, clouds
             still bin dot by dot, and every member counts once per cell
        """
        import pathlib
        from django.contrib.staticfiles import finders
        js = pathlib.Path(finders.find('js/spray_layer.js')).read_text()
        self.assertIn('corridorMeters: 20,', js)
        self.assertIn("ctx.fill('evenodd');", js)
        self.assertIn('ctx.lineWidth = Math.max(1, corridorCells);', js)
        self.assertIn('if (data[(py * w + px) * 4 + 3] < 128) { continue; }', js)
        self.assertIn('L.SprayAgreementLayer.membersFromFeatures = function (features)', js)
        self.assertIn('L.SprayAgreementLayer.cloudsFromFeatures = function (features)', js)
        self.assertIn("this.fire('stats', this._stats);", js)
        # One binning seam for both styles.
        self.assertEqual(js.count('var bins = this._bin('), 2)

    def test_respondents_count_once_and_coverage_scales_to_the_strongest_cell(self):
        """
        GIVEN the agreement layer used by coverage (change coverage-contrast, #370)
        WHEN its binning and opacity code is read
        THEN members are grouped by id before binning, opacity goes through the one
             alphaFor curve with scale/gamma/minCount, spray keeps the 'share' default
             and coverage asks for 'max'
        """
        import pathlib
        from django.contrib.staticfiles import finders
        js = pathlib.Path(finders.find('js/spray_layer.js')).read_text()
        self.assertIn('var groups = new Map();', js)
        self.assertIn('groups.forEach(function (members) {', js)
        self.assertIn('L.SprayAgreementLayer.alphaFor = function (count, n, max, o) {', js)
        self.assertIn("var a = L.SprayAgreementLayer.alphaFor(count, n, max, opts);", js)
        self.assertIn("scale: 'share',", js)
        self.assertIn("if (o.scale === 'max') {", js)
        self.assertNotIn('var a = lo + (hi - lo) * (count / n);', js)
        q = Question.objects.create(survey_section=self.section, code='Q_AREA',
                                    name='Areas', input_type='polygon')
        self._answer(q, polygon=Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)), srid=4326))
        html = self._page()
        self.assertIn("pane: paneName, scale: 'max', maxAlpha: 0.9 });", html)
        # The cell slider reaches the automatic cell, however large the source.
        self.assertIn("var cellMax = Math.max(1000, Math.ceil(cellVal * 2 / 1000) * 1000);", html)

    def test_coverage_settings_offer_contrast_minimum_and_a_curve_preview(self):
        """
        GIVEN a survey with a polygon question that has answers
        WHEN the Responses page is rendered
        THEN the coverage settings carry the Contrast and minimum-respondents controls,
             contrast maps to the curve exponent, and the preview draws through alphaFor
        """
        q = Question.objects.create(survey_section=self.section, code='Q_AREA',
                                    name='Areas', input_type='polygon')
        self._answer(q, polygon=Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)), srid=4326))
        html = self._page()
        self.assertIn("key: 'contrast', label: 'Contrast', min: -100, max: 100", html)
        self.assertIn("key: 'minCount', label: 'Min. people', min: 1", html)
        self.assertIn('{ gamma: Math.pow(4, v / 100) }', html)
        self.assertIn('function _drawCoverageCurve(el, slot) {', html)
        self.assertIn('L.SprayAgreementLayer.alphaFor(c, n, max, o)', html)

    def test_point_only_survey_keeps_the_heatmap_entry(self):
        """
        GIVEN a survey whose only geo question is a point question
        WHEN the Responses page renders
        THEN the heat menu entry is still there and point sources are routed to it
        """
        pt = Question.objects.create(
            survey_section=self.section, code='Q_PT', name='Where?', input_type='point', order_number=1)
        self._answer(pt, point=Point(13.405, 52.52))
        html = self._page()
        self.assertIn("' Create Heatmap'", html)
        self.assertIn('_appendHeatMenuItem(menu, sourceId);', html)
