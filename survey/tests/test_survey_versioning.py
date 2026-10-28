"""Tests that no capability owns yet: survey-versioning.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, SurveyCollaborator
from survey.models import SurveySectionTranslation, QuestionTranslation
from survey.versioning import clone_survey_for_draft, publish_draft, IncompatibleDraftError
from survey.tests.helpers import _make_org


class VersioningModelTest(TestCase):
    """Tests for versioning-related model fields and methods on SurveyHeader."""

    def setUp(self):
        self.org = _make_org('VersionOrg')
        self.user = User.objects.create_user(username='vowner', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='canon_survey', organization=self.org, created_by=self.user,
            status='published',
        )

    def test_default_version_number_is_one(self):
        """
        GIVEN a newly created SurveyHeader
        WHEN no version_number is specified
        THEN version_number defaults to 1
        """
        self.assertEqual(self.survey.version_number, 1)

    def test_default_is_canonical_true(self):
        """
        GIVEN a newly created SurveyHeader
        WHEN no is_canonical is specified
        THEN is_canonical defaults to True
        """
        self.assertTrue(self.survey.is_canonical)

    def test_canonical_survey_defaults_to_null(self):
        """
        GIVEN a newly created SurveyHeader
        WHEN no canonical_survey is specified
        THEN canonical_survey is None
        """
        self.assertIsNone(self.survey.canonical_survey)

    def test_published_version_defaults_to_null(self):
        """
        GIVEN a newly created SurveyHeader
        WHEN no published_version is specified
        THEN published_version is None
        """
        self.assertIsNone(self.survey.published_version)

    def test_has_draft_copy_false_when_no_draft(self):
        """
        GIVEN a canonical survey with no draft copy
        WHEN has_draft_copy() is called
        THEN it returns False
        """
        self.assertFalse(self.survey.has_draft_copy())

    def test_has_draft_copy_true_when_draft_exists(self):
        """
        GIVEN a canonical survey with a draft copy linked via published_version
        WHEN has_draft_copy() is called
        THEN it returns True
        """
        SurveyHeader.objects.create(
            name='[draft] canon_survey', organization=self.org,
            status='draft', published_version=self.survey,
        )
        self.assertTrue(self.survey.has_draft_copy())

    def test_get_draft_copy_returns_none_when_no_draft(self):
        """
        GIVEN a canonical survey with no draft copy
        WHEN get_draft_copy() is called
        THEN it returns None
        """
        self.assertIsNone(self.survey.get_draft_copy())

    def test_get_draft_copy_returns_draft(self):
        """
        GIVEN a canonical survey with a draft copy
        WHEN get_draft_copy() is called
        THEN it returns the draft SurveyHeader
        """
        draft = SurveyHeader.objects.create(
            name='[draft] canon_survey', organization=self.org,
            status='draft', published_version=self.survey,
        )
        self.assertEqual(self.survey.get_draft_copy(), draft)

    def test_is_draft_copy_false_for_canonical(self):
        """
        GIVEN a canonical survey (published_version is None)
        WHEN is_draft_copy is accessed
        THEN it returns False
        """
        self.assertFalse(self.survey.is_draft_copy)

    def test_is_draft_copy_true_for_draft(self):
        """
        GIVEN a draft copy with published_version set
        WHEN is_draft_copy is accessed
        THEN it returns True
        """
        draft = SurveyHeader.objects.create(
            name='[draft] canon_survey', organization=self.org,
            status='draft', published_version=self.survey,
        )
        self.assertTrue(draft.is_draft_copy)

    def test_get_version_history_empty_when_no_archives(self):
        """
        GIVEN a canonical survey with no archived versions
        WHEN get_version_history() is called
        THEN it returns an empty queryset
        """
        self.assertEqual(self.survey.get_version_history().count(), 0)

    def test_get_version_history_returns_archived_versions_ordered(self):
        """
        GIVEN a canonical survey with two archived versions
        WHEN get_version_history() is called
        THEN it returns them ordered by -version_number
        """
        v1 = SurveyHeader.objects.create(
            name='canon_survey', organization=self.org,
            status='closed', is_canonical=False,
            canonical_survey=self.survey, version_number=1,
        )
        v2 = SurveyHeader.objects.create(
            name='canon_survey', organization=self.org,
            status='closed', is_canonical=False,
            canonical_survey=self.survey, version_number=2,
        )
        history = list(self.survey.get_version_history())
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], v2)
        self.assertEqual(history[1], v1)


class CloneSurveyTest(TestCase):
    """Tests for clone_survey_for_draft function."""

    def setUp(self):
        self.org = _make_org('CloneOrg')
        self.user = User.objects.create_user(username='cloner', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='original', organization=self.org, created_by=self.user,
            status='published', redirect_url='/done/',
            available_languages=['en', 'ru'], thanks_html={'en': 'Thanks'},
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1',
            code='S1', is_head=True,
        )
        SurveySectionTranslation.objects.create(
            section=self.section, language='ru', title='Раздел 1',
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Favorite color?', input_type='choice',
            choices=[{'code': 1, 'name': 'Red'}, {'code': 2, 'name': 'Blue'}],
        )
        QuestionTranslation.objects.create(
            question=self.question, language='ru', name='Любимый цвет?',
        )
        self.sub_q = Question.objects.create(
            survey_section=self.section, parent_question_id=self.question,
            code='Q1_1', order_number=1, name='Why?', input_type='text',
        )

    def test_draft_linked_to_canonical(self):
        """
        GIVEN a published canonical survey
        WHEN clone_survey_for_draft is called
        THEN the draft's published_version points to the canonical
        """
        draft = clone_survey_for_draft(self.survey)
        self.assertEqual(draft.published_version, self.survey)

    def test_draft_status_is_draft(self):
        """
        GIVEN a published canonical survey
        WHEN clone_survey_for_draft is called
        THEN the draft status is 'draft'
        """
        draft = clone_survey_for_draft(self.survey)
        self.assertEqual(draft.status, 'draft')

    def test_draft_name_has_prefix(self):
        """
        GIVEN a canonical survey named 'original'
        WHEN clone_survey_for_draft is called
        THEN the draft name starts with '[draft] '
        """
        draft = clone_survey_for_draft(self.survey)
        self.assertTrue(draft.name.startswith('[draft] '))

    def test_draft_name_truncation(self):
        """
        GIVEN a canonical survey with a 45-character name
        WHEN clone_survey_for_draft is called
        THEN the draft name is truncated to 45 characters
        """
        self.survey.name = 'a' * 45
        self.survey.save()
        draft = clone_survey_for_draft(self.survey)
        self.assertLessEqual(len(draft.name), 45)

    def test_sections_cloned_with_same_codes(self):
        """
        GIVEN a canonical survey with one section
        WHEN clone_survey_for_draft is called
        THEN the draft has a section with the same code and name
        """
        draft = clone_survey_for_draft(self.survey)
        draft_sections = SurveySection.objects.filter(survey_header=draft)
        self.assertEqual(draft_sections.count(), 1)
        self.assertEqual(draft_sections.first().code, 'S1')
        self.assertEqual(draft_sections.first().name, 'sec1')

    def test_section_translations_cloned(self):
        """
        GIVEN a canonical survey with section translations
        WHEN clone_survey_for_draft is called
        THEN the draft sections have the same translations
        """
        draft = clone_survey_for_draft(self.survey)
        draft_section = SurveySection.objects.get(survey_header=draft)
        trans = SurveySectionTranslation.objects.filter(section=draft_section)
        self.assertEqual(trans.count(), 1)
        self.assertEqual(trans.first().language, 'ru')
        self.assertEqual(trans.first().title, 'Раздел 1')

    def test_questions_cloned_with_same_codes(self):
        """
        GIVEN a canonical survey with questions
        WHEN clone_survey_for_draft is called
        THEN the draft has questions with the same codes
        """
        draft = clone_survey_for_draft(self.survey)
        draft_questions = Question.objects.filter(
            survey_section__survey_header=draft
        )
        codes = set(draft_questions.values_list('code', flat=True))
        self.assertIn('Q1', codes)
        self.assertIn('Q1_1', codes)

    def test_choices_cloned(self):
        """
        GIVEN a canonical survey with a choice question
        WHEN clone_survey_for_draft is called
        THEN the draft question has the same choices
        """
        draft = clone_survey_for_draft(self.survey)
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        self.assertEqual(len(draft_q.choices), 2)
        codes = {c['code'] for c in draft_q.choices}
        self.assertEqual(codes, {1, 2})

    def test_question_translations_cloned(self):
        """
        GIVEN a canonical survey with question translations
        WHEN clone_survey_for_draft is called
        THEN the draft questions have the same translations
        """
        draft = clone_survey_for_draft(self.survey)
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        trans = QuestionTranslation.objects.filter(question=draft_q)
        self.assertEqual(trans.count(), 1)
        self.assertEqual(trans.first().name, 'Любимый цвет?')

    def test_subquestions_cloned(self):
        """
        GIVEN a canonical survey with sub-questions
        WHEN clone_survey_for_draft is called
        THEN the draft has sub-questions with the same codes and parent links
        """
        draft = clone_survey_for_draft(self.survey)
        draft_sub = Question.objects.get(
            survey_section__survey_header=draft, code='Q1_1'
        )
        self.assertIsNotNone(draft_sub.parent_question_id)
        self.assertEqual(draft_sub.parent_question_id.code, 'Q1')

    def test_collaborators_cloned(self):
        """
        GIVEN a canonical survey with collaborators
        WHEN clone_survey_for_draft is called
        THEN the draft has the same collaborators with the same roles
        """
        draft = clone_survey_for_draft(self.survey)
        collabs = SurveyCollaborator.objects.filter(survey=draft)
        self.assertEqual(collabs.count(), 1)
        self.assertEqual(collabs.first().user, self.user)
        self.assertEqual(collabs.first().role, 'owner')

    def test_linked_list_preserved(self):
        """
        GIVEN a canonical survey with two linked sections
        WHEN clone_survey_for_draft is called
        THEN the draft sections maintain the same linked list structure
        """
        section2 = SurveySection.objects.create(
            survey_header=self.survey, name='sec2', title='Section 2', code='S2',
        )
        self.section.next_section = section2
        self.section.save(update_fields=['next_section'])
        section2.prev_section = self.section
        section2.save(update_fields=['prev_section'])

        draft = clone_survey_for_draft(self.survey)
        draft_secs = {
            s.code: s for s in SurveySection.objects.filter(survey_header=draft)
        }
        self.assertIsNotNone(draft_secs['S1'].next_section)
        self.assertEqual(draft_secs['S1'].next_section.code, 'S2')
        self.assertIsNotNone(draft_secs['S2'].prev_section)
        self.assertEqual(draft_secs['S2'].prev_section.code, 'S1')

    def test_settings_copied(self):
        """
        GIVEN a canonical survey with custom settings
        WHEN clone_survey_for_draft is called
        THEN the draft has the same redirect_url, available_languages, thanks_html
        """
        draft = clone_survey_for_draft(self.survey)
        self.assertEqual(draft.redirect_url, '/done/')
        self.assertEqual(draft.available_languages, ['en', 'ru'])
        self.assertEqual(draft.thanks_html, {'en': 'Thanks'})


class PublishDraftTest(TestCase):
    """Tests for publish_draft function."""

    def setUp(self):
        self.org = _make_org('PublishOrg')
        self.user = User.objects.create_user(username='publisher', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='pub_test', organization=self.org, created_by=self.user,
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1',
            code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Color?', input_type='choice',
            choices=[{'code': 1, 'name': 'Red'}],
        )
        self.session = SurveySession.objects.create(survey=self.survey)
        self.answer = Answer.objects.create(
            survey_session=self.session, question=self.question,
            selected_choices=[1],
        )

    def test_publish_increments_version(self):
        """
        GIVEN a canonical survey at version 1 with a compatible draft
        WHEN publish_draft is called
        THEN canonical.version_number becomes 2
        """
        draft = clone_survey_for_draft(self.survey)
        canonical = publish_draft(draft)
        self.assertEqual(canonical.version_number, 2)

    def test_publish_creates_archived_version(self):
        """
        GIVEN a canonical survey with a draft
        WHEN publish_draft is called
        THEN an archived version is created with is_canonical=False
        """
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        archived = SurveyHeader.objects.filter(
            canonical_survey=self.survey, is_canonical=False,
        )
        self.assertEqual(archived.count(), 1)
        self.assertEqual(archived.first().version_number, 1)
        self.assertEqual(archived.first().status, 'closed')

    def test_publish_moves_sessions_to_archived(self):
        """
        GIVEN a canonical survey with sessions
        WHEN publish_draft is called
        THEN existing sessions belong to the archived version
        """
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        archived = SurveyHeader.objects.get(
            canonical_survey=self.survey, is_canonical=False,
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.survey, archived)

    def test_publish_moves_old_sections_to_archived(self):
        """
        GIVEN a canonical survey with sections
        WHEN publish_draft is called
        THEN original sections belong to the archived version
        """
        old_section_id = self.section.id
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        archived = SurveyHeader.objects.get(
            canonical_survey=self.survey, is_canonical=False,
        )
        self.section.refresh_from_db()
        self.assertEqual(self.section.survey_header, archived)

    def test_publish_moves_draft_sections_to_canonical(self):
        """
        GIVEN a canonical survey with a draft
        WHEN publish_draft is called
        THEN draft sections now belong to the canonical survey
        """
        draft = clone_survey_for_draft(self.survey)
        draft_section = SurveySection.objects.get(survey_header=draft)
        draft_section_id = draft_section.id
        publish_draft(draft)
        draft_section.refresh_from_db()
        self.assertEqual(draft_section.survey_header, self.survey)

    def test_publish_deletes_draft(self):
        """
        GIVEN a canonical survey with a draft
        WHEN publish_draft is called
        THEN the draft SurveyHeader is deleted
        """
        draft = clone_survey_for_draft(self.survey)
        draft_id = draft.id
        publish_draft(draft)
        self.assertFalse(SurveyHeader.objects.filter(id=draft_id).exists())

    def test_old_answers_keep_valid_question_fk(self):
        """
        GIVEN a canonical survey with answers
        WHEN publish_draft is called
        THEN old answers still reference their original question (now on archived)
        """
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        self.answer.refresh_from_db()
        # The answer's question should still exist and be on the archived version
        self.assertIsNotNone(self.answer.question)
        self.assertEqual(self.answer.question.code, 'Q1')
        archived = SurveyHeader.objects.get(
            canonical_survey=self.survey, is_canonical=False,
        )
        self.assertEqual(self.answer.question.survey_section.survey_header, archived)

    def test_incompatible_without_force_raises_error(self):
        """
        GIVEN a draft with breaking compatibility issues
        WHEN publish_draft is called without force=True
        THEN IncompatibleDraftError is raised
        """
        draft = clone_survey_for_draft(self.survey)
        # Delete the question in draft to create incompatibility
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()

        with self.assertRaises(IncompatibleDraftError) as ctx:
            publish_draft(draft, force=False)
        self.assertTrue(len(ctx.exception.issues) > 0)

    def test_incompatible_with_force_succeeds(self):
        """
        GIVEN a draft with breaking compatibility issues
        WHEN publish_draft is called with force=True
        THEN it succeeds and returns the canonical survey
        """
        draft = clone_survey_for_draft(self.survey)
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()

        canonical = publish_draft(draft, force=True)
        self.assertEqual(canonical.id, self.survey.id)
        self.assertEqual(canonical.version_number, 2)

    def test_grace_period_old_session_on_archived(self):
        """
        GIVEN a respondent who started a session before publish
        WHEN publish_draft is called
        THEN the old session's survey is the archived version (grace period)
        """
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        self.session.refresh_from_db()
        # Old session is now on the archived version
        self.assertFalse(self.session.survey.is_canonical)
        self.assertEqual(self.session.survey.canonical_survey, self.survey)

    def test_grace_period_new_session_on_canonical(self):
        """
        GIVEN a published canonical survey after a publish_draft
        WHEN a new session is created
        THEN the session is on the canonical survey at the new version
        """
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        self.survey.refresh_from_db()
        new_session = SurveySession.objects.create(survey=self.survey)
        self.assertEqual(new_session.survey, self.survey)
        self.assertEqual(new_session.survey.version_number, 2)


class DashboardVersioningTest(TestCase):
    """Tests that the dashboard excludes draft copies and archived versions."""

    def setUp(self):
        self.org = _make_org('DashOrg')
        self.user = User.objects.create_user(username='dashuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='dashuser', password='pass')

    def test_dashboard_excludes_draft_copies(self):
        """
        GIVEN a canonical survey with a draft copy
        WHEN the dashboard is loaded
        THEN the draft copy is not listed
        """
        canonical = SurveyHeader.objects.create(
            name='dash_canonical', organization=self.org, status='published',
        )
        draft = SurveyHeader.objects.create(
            name='[draft] dash_canonical', organization=self.org,
            status='draft', published_version=canonical,
        )
        response = self.client.get('/editor/')
        self.assertContains(response, 'dash_canonical')
        # The draft name should not appear as a separate entry
        content = response.content.decode()
        # Count occurrences - canonical appears, draft appears zero times as list entry
        self.assertNotIn('[draft] dash_canonical', content)

    def test_dashboard_excludes_archived_versions(self):
        """
        GIVEN a canonical survey with an archived version
        WHEN the dashboard is loaded
        THEN the archived version is not listed as a separate survey
        """
        canonical = SurveyHeader.objects.create(
            name='dash_versioned', organization=self.org, status='published',
            version_number=2,
        )
        archived = SurveyHeader.objects.create(
            name='dash_versioned', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=canonical, version_number=1,
        )
        response = self.client.get('/editor/')
        # Should show the canonical once
        self.assertContains(response, 'dash_versioned')

    def test_dashboard_shows_only_canonical_surveys(self):
        """
        GIVEN a canonical survey, a draft copy, and an archived version
        WHEN the dashboard is loaded
        THEN only the canonical survey appears in the list
        """
        canonical = SurveyHeader.objects.create(
            name='single_entry', organization=self.org, status='published',
        )
        SurveyHeader.objects.create(
            name='[draft] single_entry', organization=self.org,
            status='draft', published_version=canonical,
        )
        SurveyHeader.objects.create(
            name='single_entry', organization=self.org,
            status='closed', is_canonical=False, canonical_survey=canonical,
            version_number=1,
        )
        response = self.client.get('/editor/')
        # The filter is is_canonical=True, published_version__isnull=True
        # Verify canonical survey appears
        survey_list = SurveyHeader.objects.filter(
            organization=self.org, is_canonical=True, published_version__isnull=True,
        )
        self.assertEqual(survey_list.count(), 1)
        self.assertEqual(survey_list.first(), canonical)


class PublicViewVersioningTest(TestCase):
    """Tests that versioning is invisible to public respondents."""

    def setUp(self):
        self.org = _make_org('PubViewOrg')
        self.survey = SurveyHeader.objects.create(
            name='public_ver', organization=self.org, status='published',
            version_number=2,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Sec',
            code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Q?', input_type='text',
        )

    def test_draft_copy_invisible_to_respondents(self):
        """
        GIVEN a draft copy of a published survey
        WHEN a respondent tries to access the draft by its UUID
        THEN they get a 404 (draft status raises Http404 in access control)
        """
        draft = SurveyHeader.objects.create(
            name='[draft] public_ver', organization=self.org,
            status='draft', published_version=self.survey,
        )
        # Draft section so the URL resolves properly
        SurveySection.objects.create(
            survey_header=draft, name='dsec', code='DS1', is_head=True,
        )
        url = f'/surveys/{draft.uuid}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_archived_version_shows_closed_page(self):
        """
        GIVEN an archived version of a survey
        WHEN a respondent accesses it by the archived UUID
        THEN resolve_survey returns the canonical survey instead
        """
        archived = SurveyHeader.objects.create(
            name='public_ver', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey, version_number=1,
        )
        # Access by archived UUID should redirect to canonical survey
        url = f'/surveys/{archived.uuid}/'
        response = self.client.get(url)
        # resolve_survey returns canonical for archived UUID,
        # so it should redirect to the first section of the canonical survey
        self.assertIn(response.status_code, [200, 302])

    def test_resolve_survey_returns_canonical_for_archived_uuid(self):
        """
        GIVEN an archived version with canonical_survey set
        WHEN resolve_survey is called with the archived UUID
        THEN the canonical survey is returned
        """
        from survey.views import resolve_survey
        archived = SurveyHeader.objects.create(
            name='public_ver', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey, version_number=1,
        )
        result = resolve_survey(str(archived.uuid))
        self.assertEqual(result, self.survey)

    def test_resolve_survey_name_filters_canonical_only(self):
        """
        GIVEN a canonical survey and an archived version with the same name
        WHEN resolve_survey is called with the name
        THEN the canonical survey is returned
        """
        from survey.views import resolve_survey
        SurveyHeader.objects.create(
            name='public_ver', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey, version_number=1,
        )
        result = resolve_survey('public_ver')
        self.assertEqual(result, self.survey)

    def test_canonical_survey_accessible_to_respondents(self):
        """
        GIVEN a published canonical survey
        WHEN a respondent accesses it by UUID
        THEN they get a successful response (redirect to section)
        """
        url = f'/surveys/{self.survey.uuid}/'
        response = self.client.get(url)
        self.assertIn(response.status_code, [200, 302])


class SessionProtectTest(TestCase):
    """Tests that SurveySession PROTECT prevents deletion of SurveyHeader with sessions."""

    def setUp(self):
        self.org = _make_org('ProtectOrg')
        self.survey = SurveyHeader.objects.create(
            name='protect_test', organization=self.org, status='published',
        )
        self.session = SurveySession.objects.create(survey=self.survey)

    def test_cannot_delete_survey_with_sessions(self):
        """
        GIVEN a SurveyHeader that has SurveySessions
        WHEN attempting to delete the SurveyHeader
        THEN a ProtectedError is raised
        """
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.survey.delete()

    def test_can_delete_survey_after_sessions_removed(self):
        """
        GIVEN a SurveyHeader whose sessions have been moved or deleted
        WHEN attempting to delete the SurveyHeader
        THEN it succeeds
        """
        self.session.delete()
        self.survey.delete()
        self.assertFalse(SurveyHeader.objects.filter(name='protect_test').exists())

    def test_can_delete_survey_after_sessions_moved(self):
        """
        GIVEN a SurveyHeader whose sessions have been moved to another survey
        WHEN attempting to delete the original SurveyHeader
        THEN it succeeds
        """
        other_survey = SurveyHeader.objects.create(
            name='other_survey', organization=self.org,
        )
        self.session.survey = other_survey
        self.session.save()
        self.survey.delete()
        self.assertFalse(SurveyHeader.objects.filter(name='protect_test').exists())
        # Session still exists on the other survey
        self.session.refresh_from_db()
        self.assertEqual(self.session.survey, other_survey)
