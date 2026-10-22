"""`api-access-rights`: scope ∩ organisation role ∩ survey role; 404, never 403."""
import uuid

from django.test import RequestFactory, TestCase

from survey.models import Membership, SurveyCollaborator

from .. import auth, rights, scopes
from ..decorators import api_endpoint
from ..errors import ApiError
from ..models import AUDIENCE_API
from .helpers import LOCMEM, bearer, make_free_org, make_member, make_org, make_survey, make_user, mint


def principal_for(user, **kw):
    value, _ = mint(user, **kw)
    return auth.authenticate(RequestFactory().get('/', **bearer(value)), AUDIENCE_API)


@LOCMEM
class ScopeTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()

    def test_require_scope(self):
        """
        GIVEN a read-only token
        WHEN surveys:write is required
        THEN 403 scope_missing naming the scope
        """
        p = principal_for(self.owner, scopes_=(scopes.SURVEYS_READ,))
        with self.assertRaises(ApiError) as cm:
            rights.require_scope(p, scopes.SURVEYS_WRITE)
        self.assertEqual(cm.exception.status, 403)
        self.assertEqual(cm.exception.extra['scope'], 'surveys:write')
        rights.require_scope(p, scopes.SURVEYS_READ)

    def test_decorator_checks_scopes_before_the_view(self):
        """
        GIVEN an endpoint declared with scopes=("surveys:write",) and a read-only token
        WHEN called
        THEN 403 scope_missing and the view body never ran
        """
        ran = []

        @api_endpoint(AUDIENCE_API, scopes=(scopes.SURVEYS_WRITE,))
        def view(request):
            ran.append(1)
            return {}

        value, _ = mint(self.owner, scopes_=(scopes.SURVEYS_READ,))
        response = view(RequestFactory().post('/api/v1/x', **bearer(value)))
        self.assertEqual(response.status_code, 403)
        self.assertIn('"scope_missing"', response.content.decode())
        self.assertEqual(ran, [])

    def test_unknown_scope_is_not_valid(self):
        """
        GIVEN a scope string not in the registry
        WHEN validated
        THEN is_valid is False and normalize raises
        """
        self.assertFalse(scopes.is_valid('admin:all'))
        with self.assertRaises(ValueError):
            scopes.normalize(['admin:all'])
        self.assertEqual(scopes.to_string(['surveys:write', 'surveys:read']), 'surveys:read surveys:write')


@LOCMEM
class SurveyLookupTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.survey, self.section, self.question = make_survey(self.org)
        self.other_org, self.other_owner = make_free_org('Other', 'other_owner')
        self.other_survey, self.other_section, self.other_question = make_survey(self.other_org, 'other')

    def _404(self, fn, *args, **kw):
        with self.assertRaises(ApiError) as cm:
            fn(*args, **kw)
        self.assertEqual(cm.exception.status, 404)
        return cm.exception.as_response().content

    def test_owner_sees_own_survey(self):
        """
        GIVEN the organisation owner's token
        WHEN survey_for asks for the survey at editor level
        THEN it is returned
        """
        p = principal_for(self.owner)
        self.assertEqual(rights.survey_for(p, self.survey.uuid, min_role='editor'), self.survey)

    def test_other_workspace_is_404_identical_to_unknown(self):
        """
        GIVEN a token of a user outside the survey's organisation
        WHEN the survey is requested
        THEN 404, byte-identical to the response for a random uuid
        """
        p = principal_for(self.other_owner)
        existing = self._404(rights.survey_for, p, self.survey.uuid)
        random = self._404(rights.survey_for, p, uuid.uuid4())
        self.assertEqual(existing, random)

    def test_viewer_below_min_role_is_404(self):
        """
        GIVEN a viewer-role member with a surveys:write token
        WHEN survey_for asks for editor level
        THEN 404 (and the survey at viewer level is fine)
        """
        viewer = make_member(self.org, 'viewer_user', role='viewer')
        p = principal_for(viewer)
        self.assertEqual(rights.survey_for(p, self.survey.uuid, 'viewer'), self.survey)
        self._404(rights.survey_for, p, self.survey.uuid, 'editor')

    def test_editor_member_without_collaboration_is_404(self):
        """
        GIVEN an editor-role member who is not a collaborator on the survey
        WHEN the survey is requested
        THEN 404 -- editor members only reach their own surveys
        """
        editor = make_member(self.org, 'editor_user', role='editor')
        p = principal_for(editor)
        self._404(rights.survey_for, p, self.survey.uuid)
        SurveyCollaborator.objects.create(user=editor, survey=self.survey, role='editor')
        self.assertEqual(rights.survey_for(p, self.survey.uuid, 'editor'), self.survey)

    def test_bound_token_refuses_other_workspace(self):
        """
        GIVEN a user who is a member of A and B, with a token bound to A
        WHEN a survey of B is requested
        THEN 404
        """
        Membership.objects.create(user=self.owner, organization=self.other_org, role='owner')
        p = principal_for(self.owner, organization=self.org)
        self.assertEqual(rights.survey_for(p, self.survey.uuid), self.survey)
        self._404(rights.survey_for, p, self.other_survey.uuid)
        self.assertEqual(p.organization, self.org)

    def test_trashed_survey_is_404(self):
        """
        GIVEN a survey in the trash
        WHEN requested
        THEN 404
        """
        from django.utils import timezone
        self.survey.deleted_at = timezone.now()
        self.survey.save(update_fields=['deleted_at'])
        self._404(rights.survey_for, principal_for(self.owner), self.survey.uuid)

    def test_section_and_question_are_scoped_to_the_survey(self):
        """
        GIVEN section/question ids of another survey
        WHEN looked up under this survey
        THEN 404; the right ids resolve
        """
        p = principal_for(self.owner)
        self.assertEqual(rights.section_for(p, self.survey, self.section.pk), self.section)
        self.assertEqual(rights.question_for(p, self.survey, self.question.pk), self.question)
        self._404(rights.section_for, p, self.survey, self.other_section.pk)
        self._404(rights.question_for, p, self.survey, self.other_question.pk)
        self._404(rights.section_for, p, self.survey, 999999)
