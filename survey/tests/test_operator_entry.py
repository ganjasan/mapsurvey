"""Tests for the `operator-entry` capability (openspec/specs/operator-entry/spec.md).

Change operator-entry (#355, epic #350): a workspace member enters a survey's answers on
someone's behalf — a paper sheet, an assisted interview, a field observation.
"""
import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from billing.models import STATUS_REFUNDED
from billing.tests.helpers import make_sub, trial_used_elsewhere
from survey.models import (
    Answer, Membership, Organization, Question, SurveyCollaborator, SurveyEvent, SurveyHeader, SurveySection,
    SurveySession,
)


class _EntryFixture(TestCase):
    """A Pro workspace whose survey has two sections, an archived v1 and an editor."""

    def setUp(self):
        self.org = Organization.objects.create(name='Entry Org', slug='entry-org')
        self.owner = User.objects.create_user('entry_owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.sub = make_sub(self.org)
        self.survey = SurveyHeader.objects.create(
            name='entry_survey', organization=self.org, created_by=self.owner,
            status='published', redirect_url='#', available_languages=['en', 'pl'], version_number=2,
        )
        self.s1 = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True)
        self.s2 = SurveySection.objects.create(
            survey_header=self.survey, name='s2', title='S2', code='S2', prev_section=self.s1)
        self.s1.next_section = self.s2
        self.s1.save()
        self.q_like = Question.objects.create(
            survey_section=self.s1, code='LIKE', name='Like it?', input_type='choice', order_number=1,
            required=True, choices=[{'code': 1, 'name': 'Yes'}, {'code': 2, 'name': 'No'}])
        self.q_why = Question.objects.create(
            survey_section=self.s1, code='WHY', name='Why?', input_type='text', order_number=2,
            visibility_rule={'question_code': 'LIKE', 'choice_codes': [1]})
        self.q_sheet = Question.objects.create(
            survey_section=self.s1, code='SHEET', name='Sheet number', input_type='text_line',
            order_number=3, audience='operators', required=True)
        self.q_where = Question.objects.create(
            survey_section=self.s2, code='WHERE', name='Where?', input_type='point', order_number=1)
        # Archived v1: one section, the LIKE question only.
        self.v1 = SurveyHeader.objects.create(
            name='entry_survey_v1', organization=self.org, created_by=self.owner, status='archived',
            redirect_url='#', canonical_survey=self.survey, version_number=1)
        self.v1_s1 = SurveySection.objects.create(
            survey_header=self.v1, name='s1', title='S1', code='S1', is_head=True)
        self.v1_like = Question.objects.create(
            survey_section=self.v1_s1, code='LIKE', name='Like it?', input_type='choice', order_number=1,
            choices=[{'code': 1, 'name': 'Yes'}, {'code': 2, 'name': 'No'}])
        self.login(self.owner)
        self.header_url = reverse('operator_entry_header', args=[self.survey.uuid])

    def login(self, user):
        self.client.force_login(user)
        s = self.client.session
        s['active_org_id'] = self.org.id
        s.save()

    def start(self, source='paper', version=None, language='en'):
        response = self.client.post(self.header_url, {
            'source': source, 'version': version or self.survey.pk, 'language': language})
        session = SurveySession.objects.order_by('-pk').first()
        return response, session

    def section_url(self, session, section):
        return reverse('operator_entry_section', args=[self.survey.uuid, session.pk, section.name])


class EntryGateTest(_EntryFixture):

    def test_editor_of_pro_workspace_opens_the_header(self):
        """
        GIVEN an owner of a Pro workspace
        WHEN they open the entry header
        THEN it renders with the source choices
        """
        response = self.client.get(self.header_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="source"')

    def test_viewer_cannot_enter(self):
        """
        GIVEN a workspace viewer
        WHEN they request the entry header
        THEN the response is 403
        """
        viewer = User.objects.create_user('entry_viewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.login(viewer)
        self.assertEqual(self.client.get(self.header_url).status_code, 403)

    def test_free_workspace_sees_the_lock(self):
        """
        GIVEN a workspace without Pro whose owner already used their Pro trial
        WHEN an owner opens Responses and then the entry header
        THEN Responses shows the locked button with the locked Pro mark and the header answers the feature refusal
        """
        self.sub.delete()
        trial_used_elsewhere(self.org)
        page = self.client.get(reverse('editor_survey_analytics', args=[self.survey.uuid]))
        self.assertContains(page, 'rv2-enter-response--locked')
        self.assertContains(page, 'data-pro-state="locked"')
        self.assertEqual(self.client.get(self.header_url).status_code, 403)

    def test_first_sheet_of_a_startable_workspace_starts_the_trial(self):
        """
        GIVEN a Free workspace that never had a trial, and an editor of it
        WHEN the editor opens Responses, then submits the entry header and walks the sheet
        THEN the button is live with "free to try"; the owner's trial exists started by the editor with
             operator_entry, the allowance reads 1 used with no limit, and the sections open
        """
        from billing.models import EntitlementGrant
        self.sub.delete()
        editor = User.objects.create_user('entry_editor2', password='pass')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        SurveyCollaborator.objects.create(user=editor, survey=self.survey, role='editor')
        self.login(editor)
        page = self.client.get(reverse('editor_survey_analytics', args=[self.survey.uuid]))
        self.assertNotContains(page, 'rv2-enter-response--locked')
        self.assertContains(page, 'data-pro-state="startable"')
        response, session = self.start()
        grant = EntitlementGrant.objects.get(organization=self.org)
        self.assertEqual((grant.claimed_by, grant.started_by, grant.trigger), (self.owner, editor, 'operator_entry'))
        allowance = grant.allowances.get(feature='operator_entry')
        self.assertEqual((allowance.used, allowance.limit), (1, None))
        self.assertEqual(self.client.get(self.section_url(session, self.s1)).status_code, 200)
        self.start()
        allowance.refresh_from_db()
        self.assertEqual(allowance.used, 2)

    def test_pro_workspace_sees_the_button(self):
        """
        GIVEN a Pro workspace
        WHEN an owner opens Responses
        THEN the live button links to the entry header
        """
        page = self.client.get(reverse('editor_survey_analytics', args=[self.survey.uuid]))
        self.assertContains(page, self.header_url)
        self.assertNotContains(page, 'rv2-enter-response--locked')

    def test_lapsed_subscription_keeps_entered_sessions(self):
        """
        GIVEN a session entered while the workspace was Pro
        WHEN the subscription is refunded
        THEN the session still exists and the entry URLs refuse new entries
        """
        _, session = self.start()
        self.sub.status = STATUS_REFUNDED
        self.sub.save()
        trial_used_elsewhere(self.org)
        self.assertTrue(SurveySession.objects.filter(pk=session.pk).exists())
        self.assertEqual(self.client.get(self.header_url).status_code, 403)
        self.assertEqual(self.client.get(self.section_url(session, self.s1)).status_code, 403)

    def test_closed_survey_accepts_entries(self):
        """
        GIVEN a closed survey
        WHEN an owner opens the entry header
        THEN it renders
        """
        self.survey.status = 'closed'
        self.survey.save()
        self.assertEqual(self.client.get(self.header_url).status_code, 200)


class EntryHeaderTest(_EntryFixture):

    def test_sheet_from_an_archived_version(self):
        """
        GIVEN versions v1 (archived) and v2 (live)
        WHEN the header is submitted with v1 and source `paper`
        THEN the session sits on v1, is `paper`, entered by the operator, and the flow opens v1's head
        """
        response, session = self.start(version=self.v1.pk)
        self.assertEqual(session.survey, self.v1)
        self.assertEqual(session.source, 'paper')
        self.assertEqual(session.entered_by, self.owner)
        self.assertEqual(session.opened_by_kind, 'owner')
        self.assertRedirects(response, self.section_url(session, self.v1_s1), fetch_redirect_response=False)

    def test_source_is_required(self):
        """
        GIVEN the header form
        WHEN it is submitted without a source
        THEN no session is created and the form re-renders
        """
        before = SurveySession.objects.count()
        response = self.client.post(self.header_url, {'version': self.survey.pk, 'language': 'en'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SurveySession.objects.count(), before)

    def test_language_is_stored(self):
        """
        GIVEN a survey offering en and pl
        WHEN the operator chooses pl
        THEN the session's language is pl
        """
        _, session = self.start(language='pl')
        self.assertEqual(session.language, 'pl')

    def test_next_sheet_prefills_the_header(self):
        """
        GIVEN a finished entry with source `assisted`, version v1, language pl
        WHEN the operator follows "Enter the next one"
        THEN the header renders with those values preselected
        """
        _, session = self.start(source='assisted', version=self.v1.pk, language='pl')
        saved = self.client.get(reverse('operator_entry_saved', args=[self.survey.uuid, session.pk]))
        next_url = saved.context['next_url']
        page = self.client.get(next_url)
        form = page.context['form']
        self.assertEqual(form['source'].value(), 'assisted')
        self.assertEqual(str(form['version'].value()), str(self.v1.pk))
        self.assertEqual(form['language'].value(), 'pl')


class EntryFlowTest(_EntryFixture):

    def test_foreign_and_online_sessions_are_404(self):
        """
        GIVEN a session of another survey and an online session of this one
        WHEN an editor requests entry URLs with their ids
        THEN both answer 404
        """
        other = SurveyHeader.objects.create(name='other_entry', organization=self.org, redirect_url='#')
        foreign = SurveySession.objects.create(survey=other, source='paper')
        online = SurveySession.objects.create(survey=self.survey)
        self.assertEqual(self.client.get(self.section_url(foreign, self.s1)).status_code, 404)
        self.assertEqual(self.client.get(self.section_url(online, self.s1)).status_code, 404)

    def test_respondent_cookie_is_untouched(self):
        """
        GIVEN the operator's browser holds a respondent session for the same survey
        WHEN they enter a sheet
        THEN the cookie still names the respondent session and the answers sit on the entered one
        """
        respondent = SurveySession.objects.create(survey=self.survey)
        s = self.client.session
        s['survey_session_id'] = respondent.pk
        s.save()
        _, session = self.start()
        self.client.post(self.section_url(session, self.s1), {'LIKE': '2', 'SHEET': '17'})
        self.assertEqual(self.client.session['survey_session_id'], respondent.pk)
        self.assertEqual(Answer.objects.filter(survey_session=session).count(), 2)
        self.assertFalse(Answer.objects.filter(survey_session=respondent).exists())

    def test_section_renders_operator_only_questions_softly(self):
        """
        GIVEN a required respondent question and a required operator-only question
        WHEN the operator opens the first section
        THEN both render, only the operator's own is marked required, and the page is entry mode
        """
        _, session = self.start()
        page = self.client.get(self.section_url(session, self.s1))
        self.assertContains(page, 'name="SHEET"')
        self.assertContains(page, 'data-entry-session="%d"' % session.pk)
        html = page.content.decode()
        self.assertRegex(html, r'data-field-name="SHEET"\s+data-required="true"')
        self.assertNotRegex(html, r'data-field-name="LIKE"\s+data-required="true"')
        self.assertNotContains(page, 'Made with')

    def test_answers_are_stored_like_a_respondents(self):
        """
        GIVEN an entry session
        WHEN the operator submits a choice, a text, the sheet number and a point
        THEN one Answer per question is stored and Finish lands on the Saved page
        """
        _, session = self.start()
        r1 = self.client.post(self.section_url(session, self.s1),
                              {'LIKE': '1', 'WHY': 'Shade', 'SHEET': '17'})
        self.assertRedirects(r1, self.section_url(session, self.s2), fetch_redirect_response=False)
        feature = json.dumps({'type': 'Feature', 'properties': {'question_id': 'WHERE'},
                              'geometry': {'type': 'Point', 'coordinates': [13.4, 52.5]}})
        r2 = self.client.post(self.section_url(session, self.s2), {'WHERE': feature + '|'})
        saved_url = reverse('operator_entry_saved', args=[self.survey.uuid, session.pk])
        self.assertRedirects(r2, saved_url, fetch_redirect_response=False)
        codes = sorted(Answer.objects.filter(survey_session=session).values_list('question__code', flat=True))
        self.assertEqual(codes, ['LIKE', 'SHEET', 'WHERE', 'WHY'])
        self.assertEqual(Answer.objects.get(survey_session=session, question=self.q_where).point.coords, (13.4, 52.5))

    def test_visibility_applies(self):
        """
        GIVEN WHY is shown only when LIKE = Yes
        WHEN the operator answers No but the POST still carries WHY
        THEN no Answer is stored for WHY
        """
        _, session = self.start()
        self.client.post(self.section_url(session, self.s1), {'LIKE': '2', 'WHY': 'ghost'})
        self.assertFalse(Answer.objects.filter(survey_session=session, question=self.q_why).exists())

    def test_blank_on_paper_stays_blank(self):
        """
        GIVEN LIKE is required for respondents
        WHEN the operator submits the section without it
        THEN the section is accepted and no Answer exists for LIKE
        """
        _, session = self.start()
        response = self.client.post(self.section_url(session, self.s1), {'SHEET': '3'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Answer.objects.filter(survey_session=session, question=self.q_like).exists())

    def test_finish_completes_the_session(self):
        """
        GIVEN an entry session
        WHEN the Saved page is reached
        THEN end_datetime is set
        """
        _, session = self.start()
        self.client.get(reverse('operator_entry_saved', args=[self.survey.uuid, session.pk]))
        session.refresh_from_db()
        self.assertIsNotNone(session.end_datetime)

    def test_abandoned_entry_is_an_empty_session(self):
        """
        GIVEN the operator submitted the header and left
        WHEN Responses is computed with empty sessions hidden
        THEN the session counts as empty
        """
        from survey.analytics import empty_sessions
        _, session = self.start()
        self.assertIn(session, empty_sessions(SurveySession.objects.filter(survey=self.survey)))


class EntrySideEffectsTest(_EntryFixture):

    def test_no_survey_events(self):
        """
        GIVEN an operator enters a complete sheet
        WHEN the event log is read
        THEN there is no SurveyEvent for that session
        """
        _, session = self.start()
        self.client.get(self.section_url(session, self.s1))
        self.client.post(self.section_url(session, self.s1), {'LIKE': '1', 'SHEET': '9'})
        self.client.get(self.section_url(session, self.s2))
        self.client.post(self.section_url(session, self.s2), {})
        self.assertFalse(SurveyEvent.objects.filter(session=session).exists())

    def test_client_events_for_an_entered_session_are_dropped(self):
        """
        GIVEN an entered session
        WHEN a page_load beacon names it
        THEN no SurveyEvent row is written
        """
        _, session = self.start()
        self.client.post('/surveys/track/event/', json.dumps({
            'event_type': 'page_load', 'session_id': session.pk, 'load_ms': 500,
        }), content_type='application/json')
        self.assertFalse(SurveyEvent.objects.filter(session=session).exists())


class EntryOnReadSurfacesTest(_EntryFixture):

    def _entered(self, source='paper'):
        _, session = self.start(source=source)
        self.client.post(self.section_url(session, self.s1), {'LIKE': '1', 'SHEET': '1'})
        return session

    def test_table_has_a_source_column_and_filter(self):
        """
        GIVEN one online session and one paper session with answers
        WHEN the Responses table is filtered to paper
        THEN only the paper session is listed, and the column reads its source
        """
        online = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=online, question=self.q_like, selected_choices=[2])
        paper = self._entered()
        table = reverse('analytics_table', args=[self.survey.uuid])
        page = self.client.get(table, {'cf_source': 'v:paper'})
        ids = [row['id'] for row in page.context['rows']]
        self.assertEqual(ids, [paper.pk])
        self.assertIn('source', [c['key'] for c in page.context['columns']])

    def test_drawer_names_the_operator(self):
        """
        GIVEN a paper session entered by entry_owner
        WHEN its detail drawer opens
        THEN it shows the source and the operator's username
        """
        paper = self._entered()
        page = self.client.get(reverse('analytics_session_detail', args=[self.survey.uuid, paper.pk]))
        self.assertContains(page, 'Paper form')
        self.assertContains(page, 'entry_owner')

    def test_overview_counts_entered_sessions(self):
        """
        GIVEN one online and two paper sessions with answers
        WHEN the analytics service computes the overview
        THEN the response count is 3
        """
        from survey.analytics import SurveyAnalyticsService
        online = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=online, question=self.q_like, selected_choices=[2])
        self._entered()
        self._entered(source='assisted')
        overview = SurveyAnalyticsService(self.survey, include_empty=False).get_overview()
        self.assertEqual(overview['total_sessions'], 3)


@override_settings(FILE_UPLOAD_QUESTIONS=True)
class EntryUploadTest(_EntryFixture):
    """A file question on an entered sheet: the upload belongs to the entered session."""

    JPEG = b'\xff\xd8\xff\xe0' + b'0' * 16

    def setUp(self):
        super().setUp()
        self.photo = Question.objects.create(
            survey_section=self.s1, code='PHOTO', name='Scan', input_type='photo', order_number=4)
        self.survey.status = 'closed'
        self.survey.save()

    def _upload(self, entry_session):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post(f'/surveys/{self.survey.uuid}/upload/', {
            'question': 'PHOTO', 'entry_session': entry_session,
            'file': SimpleUploadedFile('sheet.jpg', self.JPEG, content_type='image/jpeg'),
        })

    def test_upload_on_a_closed_survey_attaches_to_the_entered_sheet(self):
        """
        GIVEN a closed survey and an entered sheet
        WHEN the operator uploads a scan for it and submits the section
        THEN the upload sits on the entered session and becomes its answer
        """
        from survey.models import Upload
        _, session = self.start()
        response = self._upload(session.pk)
        self.assertEqual(response.status_code, 200, response.content)
        token = response.json()['token']
        self.assertEqual(Upload.objects.get(token=token).session, session)
        self.client.post(self.section_url(session, self.s1), {'SHEET': '1', 'PHOTO': token})
        self.assertTrue(Answer.objects.filter(survey_session=session, question=self.photo,
                                              upload__isnull=False).exists())

    def test_viewer_cannot_upload_into_an_entered_sheet(self):
        """
        GIVEN an entered sheet and a workspace viewer
        WHEN the viewer posts an upload naming that sheet
        THEN the upload is refused (the closed survey is not open to them either)
        """
        _, session = self.start()
        viewer = User.objects.create_user('entry_up_viewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.login(viewer)
        self.assertNotEqual(self._upload(session.pk).status_code, 200)
