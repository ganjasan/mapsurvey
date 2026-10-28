"""Tests for the `live-survey-editing` capability (openspec/specs/live-survey-editing/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from unittest import mock
import json
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, SurveyCollaborator
from survey.versioning import clone_survey_for_draft, check_draft_compatibility
from survey.versioning import removed_answered_choices, structural_question_changes, question_snapshot
from survey.tests.helpers import _make_org


class CompatibilityCheckTest(TestCase):
    """Tests for check_draft_compatibility function."""

    def setUp(self):
        self.org = _make_org('CompatOrg')
        self.survey = SurveyHeader.objects.create(
            name='compat_survey', organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Color?', input_type='choice',
            choices=[
                {'code': 1, 'name': 'Red'},
                {'code': 2, 'name': 'Blue'},
                {'code': 3, 'name': 'Green'},
            ],
        )
        # Create a session and an answer to make compatibility checks meaningful
        self.session = SurveySession.objects.create(survey=self.survey)
        self.answer = Answer.objects.create(
            survey_session=self.session, question=self.question,
            selected_choices=[1],
        )

    def _make_draft(self):
        """Create a draft copy via clone."""
        return clone_survey_for_draft(self.survey)

    def test_deleted_question_with_answers_is_breaking(self):
        """
        GIVEN a draft where a question with answers is deleted
        WHEN check_draft_compatibility is called
        THEN it returns a breaking issue of type 'deleted_question'
        """
        draft = self._make_draft()
        # Delete the cloned question from draft
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()

        issues = check_draft_compatibility(draft, self.survey)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]['type'], 'deleted_question')
        self.assertEqual(issues[0]['question_code'], 'Q1')

    def test_changed_input_type_with_answers_is_breaking(self):
        """
        GIVEN a draft where a question's input_type changed and has answers
        WHEN check_draft_compatibility is called
        THEN it returns a breaking issue of type 'changed_input_type'
        """
        draft = self._make_draft()
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        draft_q.input_type = 'text'
        draft_q.save()

        issues = check_draft_compatibility(draft, self.survey)
        types = [i['type'] for i in issues]
        self.assertIn('changed_input_type', types)

    def test_removed_choice_code_with_answers_is_breaking(self):
        """
        GIVEN a draft where a choice code used in answers is removed
        WHEN check_draft_compatibility is called
        THEN it returns a breaking issue of type 'removed_choice_codes'
        """
        draft = self._make_draft()
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        # Remove choice code 1 which is used in the answer
        draft_q.choices = [
            {'code': 2, 'name': 'Blue'},
            {'code': 3, 'name': 'Green'},
        ]
        draft_q.save()

        issues = check_draft_compatibility(draft, self.survey)
        types = [i['type'] for i in issues]
        self.assertIn('removed_choice_codes', types)

    def test_safe_changes_pass(self):
        """
        GIVEN a draft with only safe changes (added questions, added choices)
        WHEN check_draft_compatibility is called
        THEN it returns an empty list
        """
        draft = self._make_draft()
        # Add a new choice (safe)
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        draft_q.choices.append({'code': 4, 'name': 'Yellow'})
        draft_q.save()
        # Add a new question (safe)
        draft_sec = SurveySection.objects.get(survey_header=draft)
        Question.objects.create(
            survey_section=draft_sec, code='Q_NEW', order_number=2,
            name='New question', input_type='text',
        )

        issues = check_draft_compatibility(draft, self.survey)
        self.assertEqual(len(issues), 0)

    def test_no_answers_means_no_breaking_issues(self):
        """
        GIVEN a canonical survey with no answers
        WHEN a draft deletes a question and check_draft_compatibility is called
        THEN it returns an empty list (no breaking issues)
        """
        # Remove all answers
        Answer.objects.all().delete()
        SurveySession.objects.all().delete()

        draft = self._make_draft()
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()

        issues = check_draft_compatibility(draft, self.survey)
        self.assertEqual(len(issues), 0)

    def test_removed_unused_choice_is_not_breaking(self):
        """
        GIVEN a draft that removes a choice code not used in any answer
        WHEN check_draft_compatibility is called
        THEN it returns an empty list
        """
        draft = self._make_draft()
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        # Remove code 3 which is NOT used in any answer (answer uses code 1)
        draft_q.choices = [
            {'code': 1, 'name': 'Red'},
            {'code': 2, 'name': 'Blue'},
        ]
        draft_q.save()

        issues = check_draft_compatibility(draft, self.survey)
        self.assertEqual(len(issues), 0)


class ReadOnlyLockTest(TestCase):
    """Tests that structural editor endpoints return 403 for published/closed surveys."""

    def setUp(self):
        self.org = _make_org('LockOrg')
        self.user = User.objects.create_user(username='lockuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='lockuser', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='locked_survey', organization=self.org, created_by=self.user,
            status='published',
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1',
            code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Test?', input_type='text',
        )

    def test_section_create_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to section create is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/sections/new/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_section_delete_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to section delete is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/delete/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_question_create_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to question create is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/'
        response = self.client.post(url, {
            'name': 'New Q', 'input_type': 'text',
        })
        self.assertEqual(response.status_code, 403)

    @override_settings(LIVE_SURVEY_EDITING=False)
    def test_question_edit_blocked_on_published(self):
        """
        GIVEN a published survey and live editing switched off
        WHEN a POST to question edit is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/edit/'
        response = self.client.post(url, {
            'name': 'Updated', 'input_type': 'text',
        })
        self.assertEqual(response.status_code, 403)

    def test_question_delete_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to question delete is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/delete/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_sections_reorder_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to sections reorder is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/sections/reorder/'
        response = self.client.post(url, json.dumps({'order': []}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_questions_reorder_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to questions reorder is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/questions/reorder/'
        response = self.client.post(url, json.dumps({'order': []}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_subquestion_create_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to subquestion create is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/subquestions/new/'
        response = self.client.post(url, {
            'name': 'Sub Q', 'input_type': 'text',
        })
        self.assertEqual(response.status_code, 403)

    def test_settings_edit_allowed_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to survey settings is made
        THEN it succeeds (settings are not structural edits)
        """
        url = f'/editor/surveys/{self.survey.uuid}/settings/'
        response = self.client.post(url, {
            'name': 'locked_survey',
            'redirect_url': 'https://example.org/new-done/',
            'visibility': 'private',
        })
        # Should succeed (200 for rendered form or 302 for redirect)
        self.assertIn(response.status_code, [200, 204, 302])

    def test_structural_edits_blocked_on_closed_survey(self):
        """
        GIVEN a closed survey
        WHEN a POST to section create is made
        THEN a 403 response is returned
        """
        self.survey.status = 'closed'
        self.survey.save()
        url = f'/editor/surveys/{self.survey.uuid}/sections/new/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)


@override_settings(LIVE_SURVEY_EDITING=True, MOBILE_EDITOR_NAV=False)
class LiveSurveyEditingTest(TestCase):
    """Safe edits save to a published survey in place; structural ones become
    unpublished changes (the draft copy) — spec live-survey-editing."""

    def setUp(self):
        self.org = _make_org('LiveOrg')
        self.user = User.objects.create_user(username='liveowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='liveowner', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='Live survey', organization=self.org, created_by=self.user,
            status='published',
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Favourite colour?', input_type='choice',
            choices=[{'code': 1, 'name': 'Red'}, {'code': 2, 'name': 'Blue'}],
        )
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=self.question, selected_choices=[1])

    def _edit_url(self):
        return f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/edit/'

    def _post_question(self, **overrides):
        data = {
            'name': 'Favourite colour?', 'input_type': 'choice', 'color': '#000000',
            'choices_json': json.dumps([{'code': 1, 'name': 'Red'}, {'code': 2, 'name': 'Blue'}]),
            'autosave': '1',
        }
        data.update(overrides)
        return self.client.post(self._edit_url(), data)

    # ── classifier ──

    def test_removing_an_answered_choice_is_structural(self):
        """
        GIVEN a choice that one answer selected
        WHEN an edit drops it
        THEN it is reported with its answer count, and an unanswered one is not
        """
        old = self.question.choices
        self.assertEqual(
            removed_answered_choices(self.question, old, [{'code': 2, 'name': 'Blue'}]),
            [(1, 'Red', 1)])
        self.assertEqual(
            removed_answered_choices(self.question, old, [{'code': 1, 'name': 'Red'}]), [])

    def test_wording_is_safe_and_type_is_structural(self):
        """
        GIVEN a snapshot of a question
        WHEN only the name changes, and then the type
        THEN only the type change yields a reason
        """
        before = question_snapshot(self.question)
        self.question.name = 'Colour you like most?'
        self.assertEqual(structural_question_changes(before, self.question), [])
        self.question.input_type = 'multichoice'
        self.assertEqual(structural_question_changes(before, self.question), ['the question type'])

    # ── safe edits in place ──

    def test_rewording_saves_to_the_live_survey(self):
        """
        GIVEN a published survey with answers
        WHEN the question is reworded
        THEN the live row changes, no draft exists and the version is unchanged
        """
        response = self._post_question(name='Which colour do you like most?')
        self.assertEqual(response.status_code, 200)
        self.question.refresh_from_db()
        self.assertEqual(self.question.name, 'Which colour do you like most?')
        self.survey.refresh_from_db()
        self.assertFalse(self.survey.has_draft_copy())
        self.assertEqual(self.survey.version_number, 1)

    def test_live_question_edit_is_rescreened(self):
        """
        GIVEN a published survey
        WHEN a question's text is saved in place
        THEN the content screen runs with the live_edit trigger, as it does for
             the thanks page and redirect URL — the other live text paths
        """
        with mock.patch('survey.services.locks.screen_survey') as screen:
            self._post_question(name='Verify your PDF document here')
        screen.assert_called_once_with(self.survey, trigger='live_edit')

    def test_adding_and_removing_unanswered_choices_is_safe(self):
        """
        GIVEN an answered choice question
        WHEN an option is added and the unanswered one removed
        THEN the edit saves
        """
        response = self._post_question(choices_json=json.dumps(
            [{'code': 1, 'name': 'Red'}, {'code': 3, 'name': 'Green'}]))
        self.assertEqual(response.status_code, 200)
        self.question.refresh_from_db()
        self.assertEqual({c['code'] for c in self.question.choices}, {1, 3})

    def test_removing_an_answered_choice_is_refused(self):
        """
        GIVEN an answered choice question on a live survey
        WHEN the answered option is removed
        THEN the edit is refused with a pointer to unpublished changes
        """
        response = self._post_question(choices_json=json.dumps([{'code': 2, 'name': 'Blue'}]))
        self.assertEqual(response.status_code, 422)
        self.assertTrue(response.json()['needs_unpublished_changes'])
        self.question.refresh_from_db()
        self.assertEqual({c['code'] for c in self.question.choices}, {1, 2})

    def test_posted_type_is_ignored_on_a_live_survey(self):
        """
        GIVEN a live choice question
        WHEN a POST carries another input type
        THEN the stored type stays
        """
        self._post_question(input_type='text')
        self.question.refresh_from_db()
        self.assertEqual(self.question.input_type, 'choice')

    def test_section_title_saves_live_but_code_does_not(self):
        """
        GIVEN a live section
        WHEN its title and code are posted
        THEN the title changes and the code does not
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/',
            {'title': 'Your colours', 'subheading': '', 'code': 'ZZ', 'layout': 'map'})
        self.assertIn(response.status_code, (204, 302))
        self.section.refresh_from_db()
        self.assertEqual(self.section.title, 'Your colours')
        self.assertEqual(self.section.code, 'S1')

    def test_structural_endpoints_stay_refused(self):
        """
        GIVEN a live survey
        WHEN a question is created directly
        THEN the server refuses it
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'New', 'input_type': 'text'})
        self.assertEqual(response.status_code, 403)

    # ── the Build page ──

    def test_build_page_is_editable_with_a_structure_gate(self):
        """
        GIVEN a live survey without unpublished changes
        WHEN the owner opens Build
        THEN structural controls open the gate and the draft vocabulary is gone
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="structureGateModal"')
        self.assertContains(response, 'data-gate="add_section"')
        self.assertContains(response, 'Change structure')
        self.assertNotContains(response, 'Draft new version')
        self.assertNotContains(response, 'read-only')

    def test_confirmations_can_be_switched_off(self):
        """
        GIVEN a live survey and its unpublished changes
        WHEN the structure prompt and the publish dialog render
        THEN each carries a "Don't ask again" box, and the account menu the
             item that turns the confirmations back on (browser-side preference)
        """
        live = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertContains(live, 'id="structureGateDontAsk"')
        self.assertContains(live, 'class="dropdown-item editor-confirm-toggle"')
        draft = clone_survey_for_draft(self.survey)
        changes = self.client.get(f'/editor/surveys/{draft.uuid}/')
        self.assertContains(changes, 'id="publishDraftDontAsk"')
        self.assertContains(changes, 'EditorConfirm.asks()')

    def test_section_panel_gates_new_question(self):
        """
        GIVEN a live survey
        WHEN the section panel renders
        THEN "New Question" opens the gate and the form is not disabled
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/')
        self.assertContains(response, 'data-gate="add_question"')
        self.assertNotContains(response, 'el.disabled = true')

    def test_question_modal_explains_the_live_wording(self):
        """
        GIVEN an answered question on a live survey
        WHEN its edit modal opens
        THEN it says edits go live and offers the type change through the gate
        """
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'live-wording-hint')
        self.assertContains(response, 'data-gate="type"')

    # ── unpublished changes ──

    def test_gate_creates_draft_and_lands_on_the_same_section(self):
        """
        GIVEN the gate opened from "New Question" in section S1
        WHEN the owner starts unpublished changes
        THEN the draft opens on its S1 with the action to replay
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/create-draft/',
            {'then': 'add_question', 'section_code': 'S1'})
        draft = self.survey.get_draft_copy()
        self.assertIsNotNone(draft)
        draft_section = SurveySection.objects.get(survey_header=draft, code='S1')
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(draft.uuid), response['Location'])
        self.assertIn(f'section={draft_section.id}', response['Location'])
        self.assertIn('then=add_question', response['Location'])

    def test_build_opens_the_unpublished_changes(self):
        """
        GIVEN a live survey with unpublished changes
        WHEN the owner opens its Build page
        THEN they are sent to the draft, and ?live=1 still shows the live one read-only
        """
        draft = clone_survey_for_draft(self.survey)
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/?section={self.section.id}')
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(draft.uuid), response['Location'])
        live = self.client.get(f'/editor/surveys/{self.survey.uuid}/?live=1')
        self.assertEqual(live.status_code, 200)
        self.assertContains(live, 'Continue editing')

    def test_live_edits_refused_while_unpublished_changes_exist(self):
        """
        GIVEN a live survey with unpublished changes
        WHEN a safe edit is posted to the live survey
        THEN it is refused, so publishing cannot silently drop it
        """
        clone_survey_for_draft(self.survey)
        response = self._post_question(name='Sneaky')
        self.assertEqual(response.status_code, 403)

    def test_survey_settings_refused_while_unpublished_changes_exist(self):
        """
        GIVEN a live survey with unpublished changes
        WHEN its settings, thanks page or map start are posted on the live survey
        THEN each is refused, because publish_draft would copy the draft's values over them
        AND the settings panel says so and links to the changes
        """
        draft = clone_survey_for_draft(self.survey)
        base = f'/editor/surveys/{self.survey.uuid}'
        self.assertEqual(self.client.post(f'{base}/settings-panel/', {'name': 'Renamed'}).status_code, 403)
        self.assertEqual(self.client.post(f'{base}/settings/', {'name': 'Renamed'}).status_code, 403)
        self.assertEqual(self.client.post(f'{base}/thanks-panel/', {'thanks_en': '<p>Ty</p>'}).status_code, 403)
        self.assertEqual(self.client.post(f'{base}/settings/map-position/', {'lat': '1', 'lng': '2', 'zoom': '5'}).status_code, 403)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.name, 'Live survey')
        self.assertIsNone(self.survey.start_map_postion)
        panel = self.client.get(f'{base}/settings-panel/')
        self.assertContains(panel, 'data-testid="settings-shadowed"')
        self.assertContains(panel, f'/editor/surveys/{draft.uuid}/?panel=settings')

    def test_survey_settings_stay_editable_on_a_plain_live_survey(self):
        """
        GIVEN a live survey without unpublished changes
        WHEN its map start is posted
        THEN it saves, as settings always did on a published survey
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/settings/map-position/',
            {'lat': '52.5', 'lng': '13.4', 'zoom': '11'})
        self.assertEqual(response.status_code, 204)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.start_map_zoom, 11)

    def test_draft_page_speaks_unpublished_changes(self):
        """
        GIVEN unpublished changes
        WHEN the owner opens them
        THEN they read as the same survey with unpublished changes
        """
        draft = clone_survey_for_draft(self.survey)
        response = self.client.get(f'/editor/surveys/{draft.uuid}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unpublished changes')
        self.assertContains(response, 'Publish changes')
        self.assertContains(response, 'View live version')
        self.assertNotContains(response, 'Draft of')
        self.assertNotContains(response, 'Publish Version')

    def test_dashboard_marks_unpublished_changes(self):
        """
        GIVEN a survey with unpublished changes
        WHEN the dashboard renders
        THEN its card carries the badge
        """
        clone_survey_for_draft(self.survey)
        response = self.client.get('/editor/?dashboard=1')
        self.assertContains(response, 'Unpublished changes')

    def test_viewer_still_sees_read_only(self):
        """
        GIVEN an org viewer
        WHEN they open a live survey
        THEN nothing is editable for them
        """
        viewer = User.objects.create_user(username='liveviewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username='liveviewer', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertContains(response, 'read-only')
        self.assertNotContains(response, 'id="structureGateModal"')

    def _login_editor(self):
        editor = User.objects.create_user(username='liveeditor', password='pass')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        SurveyCollaborator.objects.create(user=editor, survey=self.survey, role='editor')
        self.client.login(username='liveeditor', password='pass')
        return editor

    def test_editor_can_start_unpublished_changes(self):
        """
        GIVEN an editor collaborator on a live survey
        WHEN they open Build and confirm the structure prompt
        THEN the prompt offers the action and the draft is created
        """
        self._login_editor()
        page = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertContains(page, 'id="structureGateForm"')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/create-draft/',
            {'then': 'add_question', 'section_code': 'S1'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.survey.has_draft_copy())

    def test_editor_on_the_changes_sees_who_publishes(self):
        """
        GIVEN unpublished changes opened by an editor
        WHEN the page renders
        THEN there is no Publish changes button, and the page says the owner publishes
        """
        draft = clone_survey_for_draft(self.survey)
        self._login_editor()
        response = self.client.get(f'/editor/surveys/{draft.uuid}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The survey owner publishes these changes')
        self.assertNotContains(response, 'checkAndPublishDraft()"')

    def test_collaborator_added_after_the_changes_can_open_them(self):
        """
        GIVEN unpublished changes created before an editor was added to the survey
        WHEN that editor opens Build
        THEN they are redirected to the changes and can open them (the draft
             answers with the live survey's collaborators, not its snapshot)
        """
        draft = clone_survey_for_draft(self.survey)
        outsider = User.objects.create_user(username='lateeditor', password='pass')
        Membership.objects.create(user=outsider, organization=self.org, role='viewer')
        SurveyCollaborator.objects.create(user=outsider, survey=self.survey, role='editor')
        self.client.login(username='lateeditor', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], f'/editor/surveys/{draft.uuid}/')

    def test_viewer_cannot_start_unpublished_changes(self):
        """
        GIVEN an org viewer
        WHEN they post to create the changes
        THEN they are refused
        """
        viewer = User.objects.create_user(username='liveviewer2', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username='liveviewer2', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/create-draft/')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.survey.has_draft_copy())

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_mobile_status_line_offers_structure_and_share(self):
        """
        GIVEN a live survey and the mobile status line
        WHEN Build renders
        THEN it offers "Structure" (the gate) and Share, and no read-only intercept
        """
        html = self.client.get(f'/editor/surveys/{self.survey.uuid}/').content.decode()
        self.assertIn('data-gate="edit"', html)
        self.assertIn(f'/editor/surveys/{self.survey.uuid}/share/', html)
        self.assertNotIn('id="editIntercept"', html)

    def test_section_title_saves_despite_a_half_filled_visibility_rule(self):
        """
        GIVEN an ordinary draft survey (not live)
        WHEN a section autosave carries a title and an incomplete visibility rule
        THEN the title is still saved and the rule error is reported
        """
        self.survey.status = 'draft'
        self.survey.save(update_fields=['status'])
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/',
            {'title': 'Renamed', 'subheading': '', 'code': 'S1', 'layout': 'map',
             'visibility_mode': 'conditional'})
        self.assertEqual(response.status_code, 422)
        self.section.refresh_from_db()
        self.assertEqual(self.section.title, 'Renamed')

    @override_settings(LIVE_SURVEY_EDITING=False)
    def test_kill_switch_restores_read_only(self):
        """
        GIVEN live editing switched off
        WHEN the owner opens Build and posts a rewording
        THEN the old read-only page renders and the edit is refused
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertContains(response, 'Draft new version')
        self.assertNotContains(response, 'id="structureGateModal"')
        self.assertEqual(self._post_question(name='x').status_code, 403)
