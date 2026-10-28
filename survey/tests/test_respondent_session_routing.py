"""Tests for the `respondent-session-routing` capability (openspec/specs/respondent-session-routing/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer


class RespondentSessionRoutingTest(TestCase):
    """A stale survey_session_id cookie must never 500 a respondent URL.

    The cookie is one site-wide value; a respondent who finishes survey A and
    opens survey B by direct section link used to hit an unhandled
    SurveySection.DoesNotExist (support report, 2026-08-25).
    """

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="Session Routing Org")
        self.survey_a = SurveyHeader.objects.create(
            name="routing_a", organization=self.org, status='published',
        )
        self.section_a = SurveySection.objects.create(
            survey_header=self.survey_a, name="section_1", title="A one",
            code="RA1", is_head=True,
        )
        self.survey_b = SurveyHeader.objects.create(
            name="routing_b", organization=self.org, status='published',
        )
        self.section_b = SurveySection.objects.create(
            survey_header=self.survey_b, name="section_2", title="B one",
            code="RB1", is_head=True,
        )
        self.text_q = Question.objects.create(
            survey_section=self.section_b, name="Comment",
            input_type="text", order_number=1,
        )

    def _set_cookie_session(self, survey_session):
        s = self.client.session
        s['survey_session_id'] = survey_session.id
        s.save()

    def test_foreign_session_is_replaced_on_get(self):
        """
        GIVEN a cookie naming a session that belongs to survey A
        WHEN the respondent opens a section of survey B by direct link
        THEN the section renders with 200 and a fresh session for B is created
        """
        foreign = SurveySession.objects.create(survey=self.survey_a)
        self._set_cookie_session(foreign)

        response = self.client.get(f'/surveys/{self.survey_b.uuid}/section_2/')

        self.assertEqual(response.status_code, 200)
        new_id = self.client.session['survey_session_id']
        self.assertNotEqual(new_id, foreign.id)
        self.assertEqual(SurveySession.objects.get(pk=new_id).survey_id, self.survey_b.id)

    def test_foreign_session_post_lands_in_new_session(self):
        """
        GIVEN a cookie naming a session that belongs to survey A
        WHEN the respondent submits survey B's section
        THEN the answers are saved into a session of survey B, not a 500
        """
        foreign = SurveySession.objects.create(survey=self.survey_a)
        self._set_cookie_session(foreign)

        response = self.client.post(
            f'/surveys/{self.survey_b.uuid}/section_2/',
            {self.text_q.code: 'hello from B'},
        )

        self.assertEqual(response.status_code, 302)
        answer = Answer.objects.get(question=self.text_q)
        self.assertEqual(answer.survey_session.survey_id, self.survey_b.id)
        self.assertNotEqual(answer.survey_session_id, foreign.id)

    def test_soft_deleted_session_is_not_continued(self):
        """
        GIVEN a cookie naming a session the creator soft-deleted
        WHEN the respondent opens a section of the same survey
        THEN a fresh session is created instead of writing into the trash
        """
        trashed = SurveySession.objects.create(survey=self.survey_b, is_deleted=True)
        self._set_cookie_session(trashed)

        response = self.client.get(f'/surveys/{self.survey_b.uuid}/section_2/')

        self.assertEqual(response.status_code, 200)
        new_id = self.client.session['survey_session_id']
        self.assertNotEqual(new_id, trashed.id)
        self.assertFalse(SurveySession.objects.get(pk=new_id).is_deleted)

    def test_archived_version_session_keeps_version_routing(self):
        """
        GIVEN a session pinned to an archived version of the survey
        WHEN the respondent opens a section that exists in that version
        THEN the archived version's section is served under the same session
        """
        archived = SurveyHeader.objects.create(
            name="routing_b", organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey_b, version_number=1,
        )
        SurveySection.objects.create(
            survey_header=archived, name="old_section", title="Old",
            code="RBV1", is_head=True,
        )
        pinned = SurveySession.objects.create(survey=archived)
        self._set_cookie_session(pinned)

        response = self.client.get(f'/surveys/{self.survey_b.uuid}/old_section/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['survey_session_id'], pinned.id)

    def test_unknown_section_redirects_to_entry(self):
        """
        GIVEN a valid session for the survey
        WHEN the respondent opens a section name that does not exist in it
        THEN they are redirected to the survey entry point, not a 500
        """
        own = SurveySession.objects.create(survey=self.survey_b)
        self._set_cookie_session(own)

        response = self.client.get(f'/surveys/{self.survey_b.uuid}/no_such_section/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/surveys/{self.survey_b.uuid}/')

    def test_hard_deleted_session_row_starts_fresh(self):
        """
        GIVEN a cookie naming a session row that no longer exists
        WHEN the respondent opens a section
        THEN a fresh session is created and the section renders
        """
        ghost = SurveySession.objects.create(survey=self.survey_b)
        self._set_cookie_session(ghost)
        Answer.objects.filter(survey_session=ghost).delete()
        SurveySession.objects.filter(pk=ghost.id).delete()

        response = self.client.get(f'/surveys/{self.survey_b.uuid}/section_2/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            SurveySession.objects.filter(pk=self.client.session['survey_session_id']).exists()
        )
