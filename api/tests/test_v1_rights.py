"""`rest-api-v1`: every route authenticates, scopes, gates and looks nested ids
up through their survey (security checklist of #380)."""
from django.test import TestCase

from survey.models import Membership, Question, SurveyCollaborator, SurveySection

from .. import scopes
from .helpers import LOCMEM, V1Client, make_free_org, make_member, make_pro_org, make_v1_survey, mint


@LOCMEM
class V1RightsTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.token, _ = mint(self.owner)
        self.api = V1Client(self.client, self.token)

    def test_read_only_token_cannot_write_even_with_a_bad_body(self):
        """
        GIVEN a token with only surveys:read
        WHEN it POSTs a section with a malformed body
        THEN 403 scope_missing naming surveys:write -- the scope is checked before the body
        """
        token, _ = mint(self.owner, scopes_=(scopes.SURVEYS_READ,))
        response = self.api.call('POST', f'/surveys/{self.survey.uuid}/sections', {'nope': 1}, token=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'scope_missing')
        self.assertEqual(response.json()['scope'], 'surveys:write')
        self.assertEqual(SurveySection.objects.filter(survey_header=self.survey).count(), 1)

    def test_responses_need_their_own_scope(self):
        """
        GIVEN a token without responses:read
        WHEN it lists responses
        THEN 403 scope_missing
        """
        token, _ = mint(self.owner, scopes_=(scopes.SURVEYS_READ, scopes.SURVEYS_WRITE))
        response = self.api.get(f'/surveys/{self.survey.uuid}/responses', token=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['scope'], 'responses:read')

    def test_survey_of_another_workspace_is_404(self):
        """
        GIVEN a survey in a Pro workspace the caller is not a member of
        WHEN the caller reads it
        THEN 404 not_found, as for a uuid that does not exist
        """
        other_org, other_owner = make_pro_org('Other', 'other_owner')
        other, _ = make_v1_survey(other_org, other_owner, 'other')
        response = self.api.get(f'/surveys/{other.uuid}')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error'], 'not_found')

    def test_question_under_the_wrong_survey_is_404(self):
        """
        GIVEN the caller owns surveys A and B
        WHEN it patches B's question under A's path
        THEN 404 and the question is unchanged
        """
        b, b_section = make_v1_survey(self.org, self.owner, 'b')
        q = Question.objects.create(survey_section=b_section, name='Keep', input_type='text', order_number=1)
        response = self.api.patch(f'/surveys/{self.survey.uuid}/questions/{q.pk}', {'name': 'Changed'})
        self.assertEqual(response.status_code, 404)
        q.refresh_from_db()
        self.assertEqual(q.name, 'Keep')

    def test_viewer_cannot_write(self):
        """
        GIVEN a workspace viewer with a surveys:write token
        WHEN it patches a section
        THEN 403 forbidden_role and nothing changes
        """
        viewer = make_member(self.org, 'viewer_user', role='viewer')
        token, _ = mint(viewer)
        response = self.api.patch(f'/surveys/{self.survey.uuid}/sections/{self.section.pk}',
                                  {'title': 'Hacked'}, token=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'forbidden_role')
        self.section.refresh_from_db()
        self.assertEqual(self.section.title, 'Section 1')

    def test_editor_collaborator_cannot_change_settings(self):
        """
        GIVEN an org editor who collaborates on the survey as editor
        WHEN it renames the survey (an owner-only setting)
        THEN 403 forbidden_role; the thanks page (editor role) is allowed
        """
        editor = make_member(self.org, 'editor_user', role='editor')
        SurveyCollaborator.objects.create(user=editor, survey=self.survey, role='editor')
        token, _ = mint(editor)
        self.assertEqual(self.api.patch(f'/surveys/{self.survey.uuid}', {'name': 'x'}, token=token).status_code, 403)
        response = self.api.patch(f'/surveys/{self.survey.uuid}', {'thanks_html': {'en': '<p>Thanks</p>'}},
                                  token=token)
        self.assertEqual(response.status_code, 200, response.content)

    def test_free_workspace_is_pro_required(self):
        """
        GIVEN a survey in a Free workspace the caller owns, whose owners used their Pro trial
        WHEN the caller reads it
        THEN 403 pro_required with the workspace's upgrade link
        """
        from billing.tests.helpers import trial_used_elsewhere
        free, _ = make_free_org('Free', 'free_owner2')
        Membership.objects.create(user=self.owner, organization=free, role='owner')
        trial_used_elsewhere(free)
        survey, _ = make_v1_survey(free, self.owner, 'free')
        response = self.api.get(f'/surveys/{survey.uuid}')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'pro_required')
        self.assertIn('/billing/', response.json()['upgrade_url'])

    def test_no_bearer_is_401_with_resource_metadata(self):
        """
        GIVEN no Authorization header
        WHEN /surveys is requested
        THEN 401 invalid_token whose WWW-Authenticate names the protected-resource metadata
        """
        response = self.client.get('/api/v1/surveys')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_token')
        self.assertIn('resource_metadata="', response['WWW-Authenticate'])
        self.assertIn('/.well-known/oauth-protected-resource/api/', response['WWW-Authenticate'])
