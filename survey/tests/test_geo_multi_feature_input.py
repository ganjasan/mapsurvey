"""Tests for the `geo-multi-feature-input` capability (openspec/specs/geo-multi-feature-input/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
import json
from survey.models import SurveyHeader, SurveySection, Question, Answer, Membership
from survey.tests.helpers import _make_org


class GeoMultiFeatureTest(TestCase):
    """Tests for per-question feature-count limits and the multi-feature widget."""

    def setUp(self):
        self.org = _make_org('GeoMultiOrg')
        self.user = User.objects.create_user(username='geomulti', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='geomulti_survey', organization=self.org,
            redirect_url='/thanks/', status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section One',
            code='S1', is_head=True,
        )
        self.point_q = Question.objects.create(
            survey_section=self.section, name='Problem spots',
            input_type='point', order_number=1,
        )
        self.text_q = Question.objects.create(
            survey_section=self.section, name='Comment',
            input_type='text', order_number=2,
        )

    def _login(self):
        self.client.login(username='geomulti', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        # Structural edits are blocked on a published survey; editor tests run
        # against draft, respondent tests keep the published status from setUp.
        self.survey.status = 'draft'
        self.survey.save(update_fields=['status'])

    def _edit_post(self, question, extra):
        data = {'name': question.name, 'input_type': question.input_type, 'color': '#000000'}
        data.update(extra)
        return self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{question.id}/edit/', data,
        )

    def _point_feature(self, x, y):
        return json.dumps({
            'type': 'Feature',
            'properties': {'question_id': self.point_q.code},
            'geometry': {'type': 'Point', 'coordinates': [x, y]},
        })

    # --- Editor round-trip ---

    def test_editor_saves_feature_limits(self):
        """
        GIVEN a point question
        WHEN the editor saves it with vs_min_features=1 and vs_max_features=5
        THEN validation_settings contains both as ints and the reopened modal shows them
        """
        self._login()
        response = self._edit_post(self.point_q, {'vs_min_features': '1', 'vs_max_features': '5'})
        self.assertEqual(response.status_code, 200)
        self.point_q.refresh_from_db()
        self.assertEqual(self.point_q.validation_settings.get('min_features'), 1)
        self.assertEqual(self.point_q.validation_settings.get('max_features'), 5)
        modal = self.client.get(f'/editor/surveys/{self.survey.uuid}/questions/{self.point_q.id}/edit/')
        self.assertContains(modal, 'vs_min_features')
        self.assertContains(modal, 'value="1"')
        self.assertContains(modal, 'value="5"')

    def test_editor_blank_clears_feature_limits(self):
        """
        GIVEN a point question with saved feature limits
        WHEN the editor saves it with both inputs blank
        THEN neither key remains in validation_settings
        """
        self._login()
        self.point_q.validation_settings = {'min_features': 1, 'max_features': 5}
        self.point_q.save()
        self._edit_post(self.point_q, {'vs_min_features': '', 'vs_max_features': ''})
        self.point_q.refresh_from_db()
        self.assertNotIn('min_features', self.point_q.validation_settings)
        self.assertNotIn('max_features', self.point_q.validation_settings)

    def test_editor_rejects_max_below_min(self):
        """
        GIVEN a point question
        WHEN the editor saves max_features below min_features
        THEN a form error renders and nothing is saved
        """
        self._login()
        response = self._edit_post(self.point_q, {'vs_min_features': '4', 'vs_max_features': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max places must be greater than or equal to min places.')
        self.point_q.refresh_from_db()
        self.assertNotIn('max_features', self.point_q.validation_settings)

    def test_editor_ignores_feature_limits_on_non_geo(self):
        """
        GIVEN a text question
        WHEN the editor saves it with feature-limit inputs present
        THEN validation_settings never gains the keys
        """
        self._login()
        self._edit_post(self.text_q, {'vs_min_features': '1', 'vs_max_features': '5'})
        self.text_q.refresh_from_db()
        self.assertNotIn('min_features', self.text_q.validation_settings)
        self.assertNotIn('max_features', self.text_q.validation_settings)

    # --- Widget rendering ---

    def test_widget_renders_limit_attributes_and_containers(self):
        """
        GIVEN a point question with feature limits
        WHEN the respondent section page renders
        THEN the draw button carries data-min/max-features and the in-button progress container,
        and no per-feature list container renders (managed on the map instead)
        """
        self.point_q.validation_settings = {'min_features': 1, 'max_features': 5}
        self.point_q.save()
        response = self.client.get(f'/surveys/{self.survey.name}/{self.section.name}/')
        self.assertContains(response, 'data-min-features="1"')
        self.assertContains(response, 'data-max-features="5"')
        self.assertContains(response, 'geo-progress')
        self.assertContains(response, 'data-orig-subtitle')
        self.assertNotContains(response, 'geo-features')

    def test_widget_omits_limit_attributes_when_unset(self):
        """
        GIVEN a point question without feature limits
        WHEN the respondent section page renders
        THEN the draw button carries no data-min/max-features attributes
        (the bare attribute name also lives in the base template's JS selectors,
        so the assertion targets the attribute-with-value form)
        """
        response = self.client.get(f'/surveys/{self.survey.name}/{self.section.name}/')
        self.assertNotContains(response, 'data-min-features="')
        self.assertNotContains(response, 'data-max-features="')

    # --- Server clamp ---

    def test_post_clamps_features_to_max(self):
        """
        GIVEN a point question with max_features=2
        WHEN a section POST carries three features (a tampered submission)
        THEN only the first two are stored as answers
        """
        self.point_q.validation_settings = {'max_features': 2}
        self.point_q.save()
        self.client.get(f'/surveys/{self.survey.name}/{self.section.name}/')
        session_id = self.client.session['survey_session_id']
        payload = '|'.join([
            self._point_feature(30.1, 60.1),
            self._point_feature(30.2, 60.2),
            self._point_feature(30.3, 60.3),
        ]) + '|'
        self.client.post(
            f'/surveys/{self.survey.name}/{self.section.name}/',
            {self.point_q.code: payload},
        )
        self.assertEqual(
            Answer.objects.filter(survey_session_id=session_id, question=self.point_q).count(), 2,
        )

    def test_post_without_limit_stores_all_features(self):
        """
        GIVEN a point question with no feature limits
        WHEN a section POST carries three features
        THEN all three are stored as answers
        """
        self.client.get(f'/surveys/{self.survey.name}/{self.section.name}/')
        session_id = self.client.session['survey_session_id']
        payload = '|'.join([
            self._point_feature(30.1, 60.1),
            self._point_feature(30.2, 60.2),
            self._point_feature(30.3, 60.3),
        ]) + '|'
        self.client.post(
            f'/surveys/{self.survey.name}/{self.section.name}/',
            {self.point_q.code: payload},
        )
        self.assertEqual(
            Answer.objects.filter(survey_session_id=session_id, question=self.point_q).count(), 3,
        )
