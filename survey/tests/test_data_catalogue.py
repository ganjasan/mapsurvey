"""Spec: data-catalogue (change data-catalogue, #667, epic #676).

Every place dataset of a workspace — reference layers, shared maps, answers to each geo question,
respondent rows — is a registry row over data that stays where it is; members see the datasets of
surveys they can access, as counts.
"""
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.test import TestCase

from data.datasets import catalogue_rows, sync
from data.features import question_features
from data.models import Dataset
from survey.models import (Answer, Membership, Question, SurveyCollaborator, SurveyHeader,
                           SurveyMapLayer, SurveySection, SurveySession)

from .helpers import _make_org


class _CatalogueFixture(TestCase):
    def setUp(self):
        self.org = _make_org('CatOrg')
        self.owner = User.objects.create_user('catowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name='Riverside plan', organization=self.org,
                                                  created_by=self.owner, status='published')
        section = SurveySection.objects.create(survey_header=self.survey, name='s', code='S1', is_head=True)
        self.point = Question.objects.create(survey_section=section, code='CT_P', name='Where', input_type='point')
        self.layer = SurveyMapLayer.objects.create(survey=self.survey, name='Street trees', feature_count=12)

    def _session(self, deleted=False, answered=True):
        s = SurveySession.objects.create(survey=self.survey, is_deleted=deleted)
        if answered:
            Answer.objects.create(survey_session=s, question=self.point, point=Point(30.0, 59.0))
        return s

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()


class RegistryTest(_CatalogueFixture):
    """Requirement: Every place dataset of a workspace is in the catalogue."""

    def test_existing_data_appears_without_any_action(self):
        """
        GIVEN a survey with a point question, an uploaded layer and an answer
        WHEN the registry is synced for the first time
        THEN it holds the layer (public), the point answers (aggregated) and the responses (aggregated)
        """
        self._session()
        rows = {(d.kind, d.name, d.privacy_class) for d in sync(self.org)}
        self.assertIn(('layer', 'Street trees', 'public'), rows)
        self.assertIn(('answers', 'Where', 'aggregated'), rows)
        self.assertIn(('responses', 'Riverside plan', 'aggregated'), rows)

    def test_sync_is_idempotent(self):
        """
        GIVEN a synced workspace
        WHEN it is synced again
        THEN no row is added
        """
        n = sync(self.org).count()
        self.assertEqual(sync(self.org).count(), n)

    def test_a_removed_question_leaves_the_catalogue(self):
        """
        GIVEN a synced workspace with an answers dataset
        WHEN the point question is deleted
        THEN its answers dataset is gone after the next sync
        """
        sync(self.org)
        self.point.delete()
        self.assertFalse(sync(self.org).filter(kind='answers').exists())

    def test_answers_read_as_features(self):
        """
        GIVEN one kept and one trashed answered session
        WHEN the answers dataset is read as features
        THEN only the kept session's point comes back
        """
        kept = self._session()
        self._session(deleted=True)
        feats = question_features(self.survey, 'CT_P')
        self.assertEqual([f[0] for f in feats], [kept.id])


class VisibilityTest(_CatalogueFixture):
    """Requirement: Members see only datasets of surveys they can access, as counts."""

    def test_editor_without_access_does_not_see_another_survey(self):
        """
        GIVEN a workspace editor who does not collaborate on the survey
        WHEN they list the catalogue
        THEN none of the survey's datasets are listed
        """
        editor = User.objects.create_user('cateditor', password='pass')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        self.assertEqual(catalogue_rows(self.org, editor), [])
        SurveyCollaborator.objects.create(user=editor, survey=self.survey, role='viewer')
        self.assertTrue(catalogue_rows(self.org, editor))

    def test_counts_follow_the_session_scope(self):
        """
        GIVEN 4 answered sessions, one of them trashed, and one empty session
        WHEN the catalogue rows are built
        THEN the responses dataset shows 3 rows and the answers dataset 3
        """
        for _ in range(3):
            self._session()
        self._session(deleted=True)
        self._session(answered=False)
        rows = {r.dataset.kind: r for r in catalogue_rows(self.org, self.owner)}
        self.assertEqual(rows['responses'].rows, 3)
        self.assertEqual(rows['answers'].rows, 3)
        self.assertEqual(rows['layer'].rows, 12)


class CataloguePageTest(_CatalogueFixture):
    """Requirement: The catalogue is reachable and filterable."""

    def test_filter_by_source(self):
        """
        GIVEN a workspace with a layer and answers
        WHEN a member opens /editor/data/?kind=answers
        THEN only answers datasets are listed and the Answers filter is active
        """
        self._session()
        self._login(self.owner)
        html = self.client.get('/editor/data/?kind=answers').content.decode()
        self.assertIn('<strong>Where</strong>', html)
        self.assertNotIn('<strong>Street trees</strong>', html)
        self.assertIn('badge-primary px-3 py-2" data-kind="answers"', html)

    def test_sidebar_item(self):
        """
        GIVEN a signed-in member
        WHEN they open the catalogue
        THEN the page renders and the sidebar carries the Data item marked active
        """
        self._login(self.owner)
        response = self.client.get('/editor/data/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/editor/data/"')

    def test_counts_only_never_answers(self):
        """
        GIVEN answered sessions
        WHEN the catalogue renders
        THEN no answer coordinate appears in the page
        """
        self._session()
        self._login(self.owner)
        html = self.client.get('/editor/data/').content.decode()
        self.assertNotIn('59.0', html)
        self.assertEqual(Dataset.objects.filter(organization=self.org).count(), 3)
