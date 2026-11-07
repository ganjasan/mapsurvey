"""Tests for the `responses-cluster-map` capability (openspec/specs/responses-cluster-map/spec.md).

Change cluster-map (#563): Point answer layers on the Responses Map pane can be shown as
clusters -- a derived `cluster` slot of the LayerManager, like heat and coverage. The page
is the contract (the drawing happens in the browser), so the tests read the rendered page.
"""
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, Polygon
from django.test import TestCase

from survey.models import Answer, Membership, Question, SurveyHeader, SurveySection, SurveySession
from survey.tests.helpers import _make_org


class ClusterMapTest(TestCase):
    """Spec responses-cluster-map: the plugin, the slot API, the menu entry and the
    filter/visibility paths are on the Responses page whenever a point layer is."""

    def setUp(self):
        self.user = User.objects.create_user(username='clu_owner', password='pass')
        self.org = _make_org('CluOrg')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name='clu_survey', organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True)
        self.client.login(username='clu_owner', password='pass')
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

    def _point_question(self):
        q = Question.objects.create(
            survey_section=self.section, code='Q_PT', name='Where?', input_type='point', order_number=1)
        self._answer(q, point=Point(36.30, 33.51))
        self._answer(q, point=Point(36.28, 33.50))
        return q

    def test_point_layer_offers_create_clusters(self):
        """
        GIVEN a survey with a point question that has answers
        WHEN the Responses page renders
        THEN the markercluster plugin is loaded, the LayerManager carries the cluster slot API,
             and the point layer's menu offers Create Clusters next to Create Heatmap
        """
        self._point_question()
        html = self._page()
        self.assertIn('leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js', html)
        self.assertIn('leaflet.markercluster@1.5.3/dist/MarkerCluster.css', html)
        self.assertIn('LayerManager.prototype.createClusters = function(sourceId)', html)
        self.assertIn('LayerManager.prototype.removeClusters = function(cluId)', html)
        self.assertIn("'cluster:' + sourceId", html)
        self.assertIn("' Create Clusters'", html)
        self.assertIn("' Clusters exist'", html)
        self.assertIn('if (window.layerManager.canClusters(sourceId)) _appendClusterMenuItem(menu, sourceId);', html)
        self.assertIn("' Create Heatmap'", html)

    def test_clusters_are_for_plain_point_layers_only(self):
        """
        GIVEN the cluster gate on the Responses page
        WHEN a layer is a line, polygon or spray layer
        THEN canClusters refuses it: only non-spray Point layers with answers qualify
        """
        poly = Question.objects.create(
            survey_section=self.section, code='Q_PG', name='Area?', input_type='polygon', order_number=1)
        self._answer(poly, polygon=Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))))
        html = self._page()
        self.assertIn("src.geomType === 'Point' && !src.spray", html)
        # Shape layers keep the coverage branch; the cluster entry sits in the Point branch only.
        menu = html[html.index('function _showLayerMenu(sourceId, anchorEl)'):]
        menu = menu[:menu.index('// Position near anchor')]
        self.assertLess(menu.index('_appendCoverageMenuItem(menu, sourceId);'),
                        menu.index('} else {'))
        self.assertGreater(menu.index('_appendClusterMenuItem(menu, sourceId)'), menu.index('} else {'))

    def test_creating_hides_the_source_and_removing_restores_it(self):
        """
        GIVEN the cluster slot lifecycle
        WHEN clusters are created or removed
        THEN creation hides the source layer and removal shows it again,
             and the panel re-syncs the source row's checkbox both times
        """
        self._point_question()
        html = self._page()
        create = html[html.index('LayerManager.prototype.createClusters'):]
        create = create[:create.index('LayerManager.prototype.removeClusters')]
        self.assertIn('this.setLayerVisible(sourceId, false);', create)
        remove = html[html.index('LayerManager.prototype.removeClusters'):]
        remove = remove[:remove.index('LayerManager.prototype._rebuildClusters')]
        self.assertIn('this.setLayerVisible(slot.sourceId, true);', remove)
        self.assertEqual(html.count('_syncLegendCheckbox(sourceId);'), 1)
        self.assertIn('_syncLegendCheckbox(slot.sourceId);', html)

    def test_single_points_share_the_source_click_behaviour(self):
        """
        GIVEN a cluster layer's own markers
        WHEN a single point is clicked
        THEN it goes through the same handler as a source point (select + popup / open response)
        """
        self._point_question()
        html = self._page()
        self.assertIn('function bindAnswerClick(map, featureLayer, f, sid)', html)
        self.assertIn('bindAnswerClick(map, featureLayer, f, sid);', html)
        self.assertIn('bindAnswerClick(map, marker, entry.feature, entry.sid);', html)

    def test_filter_and_visibility_reach_the_cluster_slot(self):
        """
        GIVEN the LayerManager on the Responses page
        WHEN the session filter or the clusters row's visibility changes
        THEN the cluster slot is rebuilt for the responses in scope
        """
        self._point_question()
        html = self._page()
        set_filter = html[html.index('LayerManager.prototype.setFilter = function(sids)'):]
        set_filter = set_filter[:set_filter.index('LayerManager.prototype.setLayerVisible')]
        self.assertIn("slot.type === 'cluster' && slot.visible", set_filter)
        self.assertIn('this._rebuildClusters(slot);', set_filter)
        visible = html[html.index('LayerManager.prototype.setLayerVisible'):]
        visible = visible[:visible.index('LayerManager.prototype.reorder')]
        self.assertIn("slot.type === 'cluster'", visible)
        self.assertIn('return sids === null || sids.has(entry.sid);', html)

    def test_layer_menu_does_not_swallow_the_next_map_click(self):
        """
        GIVEN the layer menu, which is appended to <body>, outside the map
        WHEN the creator picks an entry (Create Clusters / Create Heatmap)
        THEN the menu does not use L.DomEvent.disableClickPropagation, whose "skip the next
             click" flag only the map clears -- with it the first click on a cluster did not zoom
        """
        self._point_question()
        html = self._page()
        menu = html[html.index('function _showLayerMenu(sourceId, anchorEl)'):]
        menu = menu[:menu.index('// Position near anchor')]
        self.assertNotIn('L.DomEvent.disableClickPropagation(menu);', menu)
        self.assertIn('document.body.appendChild(menu);', html)

    def test_cluster_icon_markup_carries_no_respondent_text(self):
        """
        GIVEN the cluster icon builder
        WHEN it builds the counted circle
        THEN its markup is made of a number and a validated hex colour only
        """
        self._point_question()
        html = self._page()
        self.assertIn("var safe = HEX_COLOR.test(color || '') ? color : '#4f46e5';", html)
        self.assertIn("'<div style=\"--clu:' + safe + '\">' + Number(count) + '</div>'", html)
