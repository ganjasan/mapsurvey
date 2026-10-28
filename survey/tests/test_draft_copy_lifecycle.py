"""Tests for the `draft-copy-lifecycle` capability (openspec/specs/draft-copy-lifecycle/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
import json
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, SurveyCollaborator
from survey.models import SurveySectionTranslation, QuestionTranslation
from survey.versioning import clone_survey_for_draft, publish_draft
from survey.cloning import clone_question
from io import StringIO
from django.core.management import call_command
from survey.tests.helpers import _make_org


class EditorVersioningEndpointsTest(TestCase):
    """Tests for the editor versioning endpoints (create-draft, publish-draft, discard-draft)."""

    def setUp(self):
        self.org = _make_org('EditorVerOrg')
        self.owner = User.objects.create_user(username='ver_owner', password='pass')
        self.editor = User.objects.create_user(username='ver_editor', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')

        self.survey = SurveyHeader.objects.create(
            name='ver_test', organization=self.org, created_by=self.owner,
            status='published',
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')
        SurveyCollaborator.objects.create(user=self.editor, survey=self.survey, role='editor')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Test?', input_type='text',
        )

    # ─── create-draft ────────────────────────────────────────────────────────

    def test_create_draft_success_for_owner(self):
        """
        GIVEN a published survey and an owner user
        WHEN POST to create-draft
        THEN a 302 redirect to the draft editor page is returned
        """
        self.client.login(username='ver_owner', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/create-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.survey.has_draft_copy())

    def test_create_draft_409_if_draft_exists(self):
        """
        GIVEN a published survey that already has a draft copy
        WHEN POST to create-draft
        THEN a 409 response is returned
        """
        self.client.login(username='ver_owner', password='pass')
        clone_survey_for_draft(self.survey)
        url = f'/editor/surveys/{self.survey.uuid}/create-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 409)

    def test_create_draft_400_if_not_published(self):
        """
        GIVEN a draft-status survey
        WHEN POST to create-draft
        THEN a 400 response is returned
        """
        self.survey.status = 'draft'
        self.survey.save()
        self.client.login(username='ver_owner', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/create-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 400)

    def test_create_draft_allowed_for_editor(self):
        """
        GIVEN a published survey and an editor-role user
        WHEN POST to create-draft ("Start unpublished changes")
        THEN the draft is created — editors start changes, owners publish them
             (change edit-live-survey)
        """
        self.client.login(username='ver_editor', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/create-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.survey.has_draft_copy())

    def test_publish_draft_403_for_editor(self):
        """
        GIVEN unpublished changes and an editor-role user
        WHEN POST to publish-draft
        THEN a 403 response is returned — publishing stays with the owner
        """
        draft = clone_survey_for_draft(self.survey)
        self.client.login(username='ver_editor', password='pass')
        response = self.client.post(f'/editor/surveys/{draft.uuid}/publish-draft/')
        self.assertEqual(response.status_code, 403)

    # ─── publish-draft ───────────────────────────────────────────────────────

    def test_publish_draft_compatible_redirects(self):
        """
        GIVEN a compatible draft copy
        WHEN POST to publish-draft
        THEN a 302 redirect to the canonical editor page is returned
        """
        self.client.login(username='ver_owner', password='pass')
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        url = f'/editor/surveys/{draft.uuid}/publish-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.version_number, 2)

    def test_publish_draft_incompatible_returns_409(self):
        """
        GIVEN a draft with breaking compatibility issues
        WHEN POST to publish-draft without force
        THEN a 409 response with issues JSON is returned
        """
        self.client.login(username='ver_owner', password='pass')
        # Create answers so deletion becomes breaking
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session,
            question=Question.objects.get(survey_section=self.section, code='Q1'),
            text='answer',
        )
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        # Delete question in draft to make it incompatible
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()
        url = f'/editor/surveys/{draft.uuid}/publish-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 409)
        data = json.loads(response.content)
        self.assertIn('issues', data)

    def test_publish_draft_force_succeeds(self):
        """
        GIVEN a draft with breaking compatibility issues
        WHEN POST to publish-draft with force=true
        THEN a 302 redirect is returned and version incremented
        """
        self.client.login(username='ver_owner', password='pass')
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session,
            question=Question.objects.get(survey_section=self.section, code='Q1'),
            text='answer',
        )
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()
        url = f'/editor/surveys/{draft.uuid}/publish-draft/'
        response = self.client.post(url, {'force': 'true'})
        self.assertEqual(response.status_code, 302)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.version_number, 2)

    # ─── discard-draft ───────────────────────────────────────────────────────

    def test_discard_draft_redirects_and_deletes(self):
        """
        GIVEN a draft copy
        WHEN POST to discard-draft
        THEN the draft is deleted and a redirect to canonical is returned
        """
        self.client.login(username='ver_owner', password='pass')
        draft = clone_survey_for_draft(self.survey)
        draft_id = draft.id
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        url = f'/editor/surveys/{draft.uuid}/discard-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SurveyHeader.objects.filter(id=draft_id).exists())

    def test_discard_draft_canonical_unchanged(self):
        """
        GIVEN a draft copy
        WHEN POST to discard-draft
        THEN the canonical survey is unchanged
        """
        self.client.login(username='ver_owner', password='pass')
        original_version = self.survey.version_number
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        url = f'/editor/surveys/{draft.uuid}/discard-draft/'
        self.client.post(url)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.version_number, original_version)
        self.assertEqual(self.survey.status, 'published')

    def test_discard_draft_with_test_sessions_succeeds(self):
        """
        GIVEN a draft copy that has been previewed, so it owns test sessions
        WHEN POST to discard-draft
        THEN the draft and its test sessions are deleted, not a 500 from PROTECT
        """
        self.client.login(username='ver_owner', password='pass')
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        draft_question = Question.objects.get(
            survey_section__survey_header=draft, code='Q1',
        )
        test_session = SurveySession.objects.create(survey=draft)
        Answer.objects.create(survey_session=test_session, question=draft_question,
                              text='typed while previewing')

        url = f'/editor/surveys/{draft.uuid}/discard-draft/'
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SurveyHeader.objects.filter(id=draft.id).exists())
        self.assertFalse(SurveySession.objects.filter(id=test_session.id).exists())
        self.assertFalse(Answer.objects.filter(survey_session_id=test_session.id).exists())

    def test_discard_draft_with_test_sessions_leaves_canonical_sessions(self):
        """
        GIVEN a previewed draft copy and a real session on the canonical
        WHEN POST to discard-draft
        THEN only the draft's sessions are deleted
        """
        self.client.login(username='ver_owner', password='pass')
        real_session = SurveySession.objects.create(survey=self.survey)
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        SurveySession.objects.create(survey=draft)

        self.client.post(f'/editor/surveys/{draft.uuid}/discard-draft/')

        self.assertTrue(SurveySession.objects.filter(id=real_session.id).exists())
        self.assertEqual(SurveySession.objects.filter(survey=self.survey).count(), 1)

    # ─── check-compatibility ─────────────────────────────────────────────────

    def test_check_compatibility_returns_issues(self):
        """
        GIVEN a draft with breaking issues
        WHEN GET to check-compatibility
        THEN JSON response with issues list is returned
        """
        self.client.login(username='ver_editor', password='pass')
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session,
            question=Question.objects.get(survey_section=self.section, code='Q1'),
            text='answer',
        )
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.editor, survey=draft, defaults={'role': 'editor'},
        )
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()
        url = f'/editor/surveys/{draft.uuid}/check-compatibility/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('issues', data)
        self.assertTrue(len(data['issues']) > 0)

    # ─── publish-flow error wiring (guard) ───────────────────────────────────

    def test_publish_chains_carry_network_failure_handler(self):
        """
        GIVEN an owner viewing a draft copy's editor page
        WHEN the page renders the lifecycle scripts
        THEN every publish fetch chain is wired to publishFetchFailed, so a
             blocked or failed request can never leave the Publish button
             silently dead (backlog #190; template tests cannot execute the JS,
             so this pins the wiring's presence)
        """
        self.client.login(username='ver_owner', password='pass')
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        response = self.client.get(
            reverse('editor_survey_detail', kwargs={'survey_uuid': draft.uuid}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('function publishFetchFailed(', content)
        # postTransition, checkAndPublishDraft, doPublishDraft + its ack retry.
        self.assertEqual(content.count('.catch(publishFetchFailed)'), 4)
        # checkAndPublishDraft must not r.json() an error page.
        self.assertIn("throw new Error('compatibility check HTTP '", content)


class VersioningRegressionTest(TestCase):
    """Regression: validation_settings must persist through draft-copy clone."""

    def test_clone_survey_for_draft_preserves_validation_settings(self):
        """
        GIVEN a survey with a question carrying non-empty validation_settings
        WHEN clone_survey_for_draft creates a draft copy
        THEN the cloned question has identical validation_settings (was a bug pre-#16)
        """
        from survey.versioning import clone_survey_for_draft
        org = _make_org('VersioningRegOrg')
        user = User.objects.create_user(username='vreg', password='pass')
        survey = SurveyHeader.objects.create(
            name='vreg_src', visibility='private', organization=org,
            created_by=user, status='published', is_canonical=True,
        )
        section = SurveySection.objects.create(
            survey_header=survey, name='s', title='S', code='S', is_head=True,
        )
        Question.objects.create(
            survey_section=section, code='Q_vreg', order_number=1,
            name='Numeric', input_type='number',
            validation_settings={'min_value': 0, 'max_value': 100, 'outlier_sigma': 3},
        )
        draft = clone_survey_for_draft(survey)
        cloned_q = Question.objects.get(
            survey_section__survey_header=draft, name='Numeric'
        )
        self.assertEqual(
            cloned_q.validation_settings,
            {'min_value': 0, 'max_value': 100, 'outlier_sigma': 3},
        )


class DraftCopyKeepsFieldsTest(TestCase):
    """The draft copy and the publish keep every field of the questionnaire (#329,
    change draft-copy-keeps-fields): visibility rules, form layout, button labels,
    hidden layers, translated labels — and any column added later."""

    def setUp(self):
        from survey.models import SurveyMapLayer
        self.org = _make_org('DraftFieldsOrg')
        self.user = User.objects.create_user(username='draftfields', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='fields_live', organization=self.org, created_by=self.user,
            status='published', available_languages=['en', 'ru'],
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.layer = SurveyMapLayer.objects.create(
            survey=self.survey, name='Parks',
            geojson='{"type": "FeatureCollection", "features": []}',
        )
        self.welcome = SurveySection.objects.create(
            survey_header=self.survey, name='welcome', title='Welcome', code='S1',
            is_head=True, layout='form', next_label='Start the tour',
        )
        SurveySectionTranslation.objects.create(
            section=self.welcome, language='ru', title='Добро пожаловать',
            next_label='Начать тур',
        )
        self.controller = Question.objects.create(
            survey_section=self.welcome, code='Q1', order_number=1,
            name='Do you cycle?', input_type='choice',
            choices=[{'code': 1, 'name': 'Yes'}, {'code': 2, 'name': 'No'}],
        )
        self.dependent = Question.objects.create(
            survey_section=self.welcome, code='Q2', order_number=2,
            name='How often?', input_type='text',
            visibility_rule={'question_code': 'Q1', 'choice_codes': [1]},
        )
        self.map_section = SurveySection.objects.create(
            survey_header=self.survey, name='routes', title='Routes', code='S2',
            layout='map', hidden_layers=[self.layer.id],
            visibility_rule={'question_code': 'Q1', 'choice_codes': [1]},
            prev_section=self.welcome,
        )
        self.welcome.next_section = self.map_section
        self.welcome.save(update_fields=['next_section'])
        Question.objects.create(
            survey_section=self.map_section, code='Q3', order_number=1,
            name='Your route', input_type='line',
        )

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _plain_values(instance):
        """Every concrete, non-relational, non-pk field — the fields a copy must carry."""
        return {
            f.name: f.value_from_object(instance)
            for f in instance._meta.concrete_fields
            if not f.primary_key and not f.is_relation
        }

    @staticmethod
    def _poke(instance, skip=()):
        """Give every plain field a value that differs from the model default, so a
        field the copy forgets shows up as a difference rather than hiding behind
        its default. Choice fields take another choice; JSON fields a marker."""
        from django.db import models as dj
        from django.contrib.gis.db.models import GeometryField
        for f in instance._meta.concrete_fields:
            if f.primary_key or f.is_relation or f.name in skip:
                continue
            current = getattr(instance, f.attname)
            if isinstance(f, GeometryField):
                value = Point(7.0, 7.0)
            elif f.choices:
                value = next(c for c, _ in f.flatchoices if c != current)
            elif isinstance(f, dj.BooleanField):
                value = not current
            elif isinstance(f, dj.JSONField):
                value = {'poked': f.name} if not isinstance(current, list) else ['poked']
            elif isinstance(f, (dj.IntegerField, dj.PositiveIntegerField)):
                value = (current or 0) + 7
            elif isinstance(f, dj.FileField):
                value = f'images/{f.name}_poked.png'
            else:
                value = f'{f.name} poked'[: (f.max_length or 100)]
            setattr(instance, f.attname, value)
        instance.save()

    def _sections_by_code(self, survey):
        return {s.code: s for s in SurveySection.objects.filter(survey_header=survey)}

    def _questions_by_code(self, survey):
        return {q.code: q for q in Question.objects.filter(survey_section__survey_header=survey)}

    # -- tests -----------------------------------------------------------------

    def test_every_concrete_field_survives_the_draft_copy(self):
        """
        GIVEN a live survey whose every section, translation, question and question
              translation field holds a non-default value
        WHEN a draft copy is created
        THEN every concrete non-relational field of every row equals the live row's
             (a column added to one of the four models without reaching the copy fails here)
        """
        from survey.versioning import clone_survey_for_draft
        self.welcome.refresh_from_db()
        for section in SurveySection.objects.filter(survey_header=self.survey):
            self._poke(section, skip=('code', 'is_head', 'visibility_rule'))
            for trans in SurveySectionTranslation.objects.filter(section=section):
                self._poke(trans, skip=('language',))
        for question in Question.objects.filter(survey_section__survey_header=self.survey):
            self._poke(question, skip=('code', 'input_type', 'visibility_rule'))
            QuestionTranslation.objects.create(question=question, language='ru', name='x')
            for trans in QuestionTranslation.objects.filter(question=question):
                self._poke(trans, skip=('language',))

        draft = clone_survey_for_draft(self.survey)

        live_sections, draft_sections = self._sections_by_code(self.survey), self._sections_by_code(draft)
        self.assertEqual(set(live_sections), set(draft_sections))
        for code, live in live_sections.items():
            with self.subTest(section=code):
                self.assertEqual(self._plain_values(live), self._plain_values(draft_sections[code]))
                live_t = {t.language: self._plain_values(t) for t in live.translations.all()}
                draft_t = {t.language: self._plain_values(t) for t in draft_sections[code].translations.all()}
                self.assertEqual(live_t, draft_t)
        live_questions, draft_questions = self._questions_by_code(self.survey), self._questions_by_code(draft)
        self.assertEqual(set(live_questions), set(draft_questions))
        for code, live in live_questions.items():
            with self.subTest(question=code):
                self.assertEqual(self._plain_values(live), self._plain_values(draft_questions[code]))
                live_t = {t.language: self._plain_values(t) for t in live.translations.all()}
                draft_t = {t.language: self._plain_values(t) for t in draft_questions[code].translations.all()}
                self.assertEqual(live_t, draft_t)

    def test_untouched_draft_publishes_identically(self):
        """
        GIVEN a live survey with a conditional question, a conditional section, a form
              section with a custom (and translated) forward label and a hidden layer
        WHEN the creator starts unpublished changes and publishes them untouched
        THEN the live survey still has both rules, the form layout, both labels and the hidden layer
        """
        from survey.versioning import clone_survey_for_draft, publish_draft
        draft = clone_survey_for_draft(self.survey)
        canonical = publish_draft(draft)

        self.assertEqual(canonical.version_number, 2)
        sections = self._sections_by_code(canonical)
        self.assertEqual(sections['S1'].layout, 'form')
        self.assertEqual(sections['S1'].next_label, 'Start the tour')
        self.assertEqual(
            sections['S1'].translations.get(language='ru').next_label, 'Начать тур',
        )
        self.assertEqual(sections['S2'].hidden_layers, [self.layer.id])
        self.assertEqual(
            sections['S2'].visibility_rule, {'question_code': 'Q1', 'choice_codes': [1]},
        )
        questions = self._questions_by_code(canonical)
        self.assertEqual(
            questions['Q2'].visibility_rule, {'question_code': 'Q1', 'choice_codes': [1]},
        )
        self.assertIsNone(questions['Q1'].visibility_rule)

    def test_restored_version_keeps_rules_and_layout(self):
        """
        GIVEN a survey republished once, so v1 is an archived version
        WHEN v1 is restored as a new draft
        THEN the draft carries v1's rules, layout and labels
        """
        from survey.versioning import clone_survey_for_draft, publish_draft
        publish_draft(clone_survey_for_draft(self.survey))
        archived = SurveyHeader.objects.get(canonical_survey=self.survey, is_canonical=False)

        restored = clone_survey_for_draft(self.survey, structure_source=archived)

        sections = self._sections_by_code(restored)
        self.assertEqual(sections['S1'].layout, 'form')
        self.assertEqual(sections['S1'].next_label, 'Start the tour')
        self.assertEqual(sections['S2'].visibility_rule, {'question_code': 'Q1', 'choice_codes': [1]})
        self.assertEqual(
            self._questions_by_code(restored)['Q2'].visibility_rule,
            {'question_code': 'Q1', 'choice_codes': [1]},
        )

    def test_cross_survey_paste_still_drops_the_rule(self):
        """
        GIVEN a conditioned question in one survey
        WHEN it is pasted (codes regenerated) into a section of another survey
        THEN the pasted question has no visibility rule, the in-survey duplicate keeps it
        """
        from survey.cloning import clone_question
        other = SurveyHeader.objects.create(
            name='other', organization=self.org, created_by=self.user, status='draft',
        )
        other_section = SurveySection.objects.create(
            survey_header=other, name='s', title='S', code='SX', is_head=True,
        )
        pasted = clone_question(self.dependent, target_section=other_section)
        self.assertIsNone(pasted.visibility_rule)
        duplicate = clone_question(self.dependent, target_section=self.welcome)
        self.assertEqual(duplicate.visibility_rule, self.dependent.visibility_rule)

    def test_report_lists_what_a_pre_fix_publish_lost(self):
        """
        GIVEN a survey published from a draft the way the pre-fix copy did it
              (archived v1 has the rules, layout and labels; canonical v2 has none)
        WHEN find_draft_field_loss runs
        THEN it names the survey and every lost field, and a healthy survey is not listed
        """
        from io import StringIO
        from django.core.management import call_command
        from survey.versioning import clone_survey_for_draft, publish_draft, find_draft_field_loss
        publish_draft(clone_survey_for_draft(self.survey))
        # Strip the canonical the way the old draft copy did.
        SurveySection.objects.filter(survey_header=self.survey).update(
            layout='map', next_label=None, hidden_layers=[], visibility_rule=None,
        )
        SurveySectionTranslation.objects.filter(section__survey_header=self.survey).update(next_label=None)
        Question.objects.filter(survey_section__survey_header=self.survey).update(visibility_rule=None)

        reports = find_draft_field_loss()

        self.assertEqual([r['survey'] for r in reports], [self.survey])
        losses = '\n'.join(reports[0]['losses'])
        for expected in ("layout was 'form'", "next_label was 'Start the tour'",
                         "next_label[ru] was 'Начать тур'", f"hidden_layers was [{self.layer.id}]",
                         "section S2 (routes): visibility_rule was", "question Q2 ('How often?'): visibility_rule was"):
            self.assertIn(expected, losses)

        out = StringIO()
        call_command('report_draft_field_loss', stdout=out)
        self.assertIn(str(self.survey.uuid), out.getvalue())
        self.assertIn('1 survey(s) affected.', out.getvalue())

        # A healthy publish (post-fix) reports nothing.
        publish_draft(clone_survey_for_draft(self.survey))
        self.assertEqual(find_draft_field_loss(), [])
