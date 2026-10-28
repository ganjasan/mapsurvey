"""Tests for the `shared-map-moderation` capability (openspec/specs/shared-map-moderation/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
import json
from survey.models import Question, SurveySession, Answer, Membership, SurveyCollaborator
from survey.analytics import SessionValidationService
from survey.tests.helpers import _mark, _react, _shared_map_survey


class SharedMapModerationTest(TestCase):
    """Status, approve-first, comment hide, the Responses block, session-status
    coupling (spec shared-map-moderation, task 4)."""

    def setUp(self):
        from django.contrib.auth.models import User
        from survey.layers import sync_question_layer
        self.f = _shared_map_survey("shared_map_mod")
        self.owner = User.objects.create_user('modowner', 'm@example.com', 'pw')
        Membership.objects.create(user=self.owner, organization=self.f['survey'].organization, role='admin')
        self.a = SurveySession.objects.create(survey=self.f['survey'])
        _mark(self.a, self.f['q1'], 13.4, 52.5, why="A's bin")
        sync_question_layer(self.f['layer'], self.a)
        self.obj = self.f['layer'].items.get()
        self.b = SurveySession.objects.create(survey=self.f['survey'])
        _react(self.b, self.f['obj'], self.obj, up=True, comment="Bags every morning")
        self.comment = Answer.objects.get(text="Bags every morning")
        self.client.login(username='modowner', password='pw')
        self.status_url = reverse('analytics_object_status', kwargs={'survey_uuid': self.f['survey'].uuid,
                                                                     'layer_id': self.f['layer'].pk, 'key': self.obj.key})
        self.comment_url = reverse('analytics_comment_hidden', kwargs={'survey_uuid': self.f['survey'].uuid,
                                                                       'answer_id': self.comment.pk})
        self.dashboard = reverse('editor_survey_analytics', kwargs={'survey_uuid': self.f['survey'].uuid})

    def _respondent_keys(self):
        other = Client()
        other.get(reverse('section', kwargs={'survey_slug': str(self.f['survey'].uuid), 'section_name': 's1'}))
        url = reverse('survey_layer_geojson', kwargs={'survey_slug': str(self.f['survey'].uuid), 'layer_id': self.f['layer'].pk})
        return [f['properties']['_key'] for f in json.loads(other.get(url).content)['features']]

    def test_hide_show_approve_transitions(self):
        """
        GIVEN a visible mark with a reaction
        WHEN the owner hides it, shows it, and approves a pending one
        THEN respondents see it exactly when it is visible, and the reaction survives throughout
        """
        self.assertEqual(self._respondent_keys(), [self.obj.key])
        self.assertEqual(self.client.post(self.status_url, {'status': 'hidden'}).json()['status'], 'hidden')
        self.assertEqual(self._respondent_keys(), [])
        self.assertEqual(self.obj.answers.count(), 2)   # B's vote and comment survive the hide
        self.client.post(self.status_url, {'status': 'visible'})
        self.assertEqual(self._respondent_keys(), [self.obj.key])
        self.client.post(self.status_url, {'status': 'pending'})
        self.assertEqual(self._respondent_keys(), [])
        self.client.post(self.status_url, {'status': 'visible'})
        self.assertEqual(self._respondent_keys(), [self.obj.key])
        self.assertEqual(self.client.post(self.status_url, {'status': 'bogus'}).status_code, 400)

    def test_comment_hide_affects_card_not_export(self):
        """
        GIVEN one comment on the mark
        WHEN the owner hides it
        THEN the respondent card and count drop it, the Responses block still lists it, and show restores it
        """
        Question.objects.filter(pk=self.f['cmt'].pk).update(share_with_respondents=True)
        from survey.object_stats import shared_map_tallies
        self.f['layer'].show_comments = True
        self.f['layer'].save()
        self.assertEqual(self.client.post(self.comment_url, {'hidden': '1'}).json()['hidden'], True)
        self.assertEqual(shared_map_tallies(self.f['layer'])[self.obj.key]['comments'], 0)
        html = self.client.get(self.dashboard).content.decode()
        self.assertIn('Bags every morning', html)
        self.client.post(self.comment_url, {'hidden': '0'})
        self.assertEqual(shared_map_tallies(self.f['layer'])[self.obj.key]['comments'], 1)

    def test_responses_block_markup(self):
        """
        GIVEN a shared-map question with one visible mark and one comment
        WHEN the owner opens Responses
        THEN the per-object table carries the moderation chips, the status badge, the actions and the comment row
        """
        html = self.client.get(self.dashboard).content.decode()
        self.assertIn('data-shared-map', html)
        self.assertIn('data-mod-filter="pending"', html)
        self.assertIn('shared-map-status--visible', html)
        self.assertIn(f'data-mod-comments-for="{self.obj.key}"', html)
        self.assertIn('Bags every morning', html)
        self.assertNotIn('alert-warning py-1 px-2" style="font-size:.8rem;" data-mod-warning', html)

    def test_min_warning(self):
        """
        GIVEN approve-first is on, the only mark is pending and the question requires 1 object
        WHEN the owner opens Responses
        THEN the warning is rendered
        """
        self.f['layer'].approve_first = True
        self.f['layer'].save()
        self.f['obj'].min_objects = 1
        self.f['obj'].save()
        self.client.post(self.status_url, {'status': 'pending'})
        html = self.client.get(self.dashboard).content.decode()
        self.assertIn('alert-warning py-1 px-2" style="font-size:.8rem;" data-mod-warning', html)

    def test_session_status_drives_creator_map(self):
        """
        GIVEN A's mark is in the creator's cached layer GeoJSON
        WHEN A's session is put on hold, then approved again
        THEN the mark leaves and returns the creator GeoJSON without any object status change
        """
        from survey.analytics import SessionValidationService
        svc = SessionValidationService()
        svc.set_status(self.a, 'on_hold')
        self.f['layer'].refresh_from_db()
        self.assertNotIn(self.obj.key, self.f['layer'].geojson)
        svc.set_status(self.a, 'approved')
        self.f['layer'].refresh_from_db()
        self.assertIn(self.obj.key, self.f['layer'].geojson)
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.status, 'visible')

    def test_viewer_cannot_moderate(self):
        """
        GIVEN a collaborator with the viewer role
        WHEN they post a status change
        THEN it is refused and the mark is untouched
        """
        from django.contrib.auth.models import User
        viewer = User.objects.create_user('viewer', 'v@example.com', 'pw')
        SurveyCollaborator.objects.create(survey=self.f['survey'], user=viewer, role='viewer')
        other = Client()
        other.login(username='viewer', password='pw')
        response = other.post(self.status_url, {'status': 'hidden'})
        self.assertIn(response.status_code, (302, 403, 404))
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.status, 'visible')
