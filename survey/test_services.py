"""The service layer (openspec change rest-api-v1, spec survey-service-layer, #380).

One module for the capability: the services are tested here directly, with an
`Actor` and plain values; the editor's behaviour over them is still covered by
the view tests in `survey/tests.py`, which did not change in the extraction.
"""
import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from survey.audit import record
from survey.models import (
    Answer, AuditLog, ContentReview, Membership, Organization, Question, SurveyHeader,
    SurveyMapLayer, SurveySection, SurveySession,
)
from survey.services import publishing, questions, sections
from survey.services.context import SURFACE_API, Actor
from survey.services.errors import Conflict, StructureLocked, TranslationGaps, ValidationFailed


def _org_user(name='svc'):
    org = Organization.objects.create(name=f'{name} org', slug=f'{name}-org')
    user = User.objects.create_user(username=f'{name}_user', password='x')
    Membership.objects.create(user=user, organization=org, role='owner')
    return org, user


class AuditRecordTest(TestCase):
    """`audit.record` -- the request-free audit writer the services use."""

    def setUp(self):
        self.org, self.user = _org_user('audit')
        self.survey = SurveyHeader.objects.create(name='a', organization=self.org)

    def test_record_from_actor(self):
        """
        GIVEN an Actor from the API surface with an IP
        WHEN record() is called for a survey
        THEN one AuditLog row carries the actor's user, IP, the survey and the metadata
        """
        actor = Actor(user=self.user, ip='203.0.113.9', surface=SURFACE_API)
        record(actor, 'status_transition', self.survey, old_status='draft', new_status='published')
        row = AuditLog.objects.get(action='status_transition')
        self.assertEqual(row.actor, self.user)
        self.assertEqual(row.ip, '203.0.113.9')
        self.assertEqual(row.survey_uuid, self.survey.uuid)
        self.assertEqual(row.metadata, {'old_status': 'draft', 'new_status': 'published'})

    def test_record_swallows_errors(self):
        """
        GIVEN the AuditLog table refuses the write
        WHEN record() is called
        THEN no exception escapes
        """
        with mock.patch('survey.models.AuditLog.objects.create', side_effect=RuntimeError('db')):
            record(self.user, 'survey_trash', self.survey)
        self.assertFalse(AuditLog.objects.exists())


def _survey_with_section(name='svc', status='draft', languages=None):
    org, user = _org_user(name)
    survey = SurveyHeader.objects.create(
        name=name, organization=org, status=status, created_by=user,
        available_languages=languages or ['en'], redirect_url='#')
    section = SurveySection.objects.create(
        survey_header=survey, name='section_1', title='S1', code='S1', is_head=True)
    return survey, section, Actor(user=user, ip='198.51.100.1')


def _question_data(**overrides):
    data = {'name': 'Favourite colour?', 'input_type': 'choice', 'color': '#000000',
            'choices_json': '[{"code": 1, "name": "Red"}, {"code": 2, "name": "Blue"}]'}
    data.update(overrides)
    return data


class SectionServiceTest(TestCase):
    """services.sections -- validate before write, atomic, reorder."""

    def setUp(self):
        self.survey, self.section, self.actor = _survey_with_section('sec')

    def test_invalid_rule_writes_nothing(self):
        """
        GIVEN a section update with a new title and a strict rule naming no question
        WHEN the service runs
        THEN ValidationFailed names visibility_rule and the title is unchanged
        """
        with self.assertRaises(ValidationFailed) as ctx:
            sections.update(self.actor, self.section, {'title': 'Changed'}, partial=True,
                            visibility_rule={'question_code': 'NOPE', 'choice_codes': [1]},
                            strict=True)
        self.assertIn('visibility_rule', ctx.exception.fields)
        self.section.refresh_from_db()
        self.assertEqual(self.section.title, 'S1')

    def test_partial_update_keeps_other_fields(self):
        """
        GIVEN a section with a name and code
        WHEN only its title is patched
        THEN the title changes and name and code stay
        """
        sections.update(self.actor, self.section, {'title': 'New title'}, partial=True)
        self.section.refresh_from_db()
        self.assertEqual((self.section.title, self.section.name, self.section.code),
                         ('New title', 'section_1', 'S1'))

    def test_delete_rolls_back_on_failure(self):
        """
        GIVEN three linked sections
        WHEN deleting the middle one fails after its neighbours were re-linked
        THEN the list is exactly as before
        """
        second = sections.create(self.actor, self.survey)
        third = sections.create(self.actor, self.survey)
        with mock.patch.object(SurveySection, 'delete', side_effect=RuntimeError('db')):
            with self.assertRaises(RuntimeError):
                sections.delete(self.actor, second)
        self.section.refresh_from_db()
        third.refresh_from_db()
        self.assertEqual(self.section.next_section_id, second.pk)
        self.assertEqual(third.prev_section_id, second.pk)

    def test_strict_reorder_requires_every_section(self):
        """
        GIVEN two sections
        WHEN a strict reorder lists only one, or a non-integer id
        THEN ValidationFailed, and the order is unchanged
        """
        second = sections.create(self.actor, self.survey)
        with self.assertRaises(ValidationFailed):
            sections.reorder(self.actor, self.survey, [second.pk], strict=True)
        with self.assertRaises(ValidationFailed):
            sections.reorder(self.actor, self.survey, ['abc'])
        self.assertEqual([s.pk for s in sections.ordered(self.survey)], [self.section.pk, second.pk])

    def test_editor_reorder_bad_id_is_400(self):
        """
        GIVEN the editor's section reorder endpoint
        WHEN it receives a non-integer id
        THEN it answers 400 (it used to raise a 500) and nothing changes
        """
        client = Client()
        client.force_login(self.actor.user)
        response = client.post(f'/editor/surveys/{self.survey.uuid}/sections/reorder/',
                               {'section_ids[]': ['abc']})
        self.assertEqual(response.status_code, 400)

    def test_structure_locked_on_published(self):
        """
        GIVEN a published survey
        WHEN a section is added through the service
        THEN StructureLocked is raised and no section is created
        """
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        with self.assertRaises(StructureLocked):
            sections.create(self.actor, self.survey)
        self.assertEqual(SurveySection.objects.filter(survey_header=self.survey).count(), 1)


class QuestionServiceTest(TestCase):
    """services.questions -- one parser, same bytes, live-survey split."""

    def setUp(self):
        self.survey, self.section, self.actor = _survey_with_section('qst')

    def test_same_bytes_as_the_editor_form(self):
        """
        GIVEN subtext carrying a script and markup
        WHEN it is saved once through the editor's question form and once through the service
        THEN both rows hold identical sanitised subtext
        """
        dirty = '<script>alert(1)</script><b>ok</b>'
        via_service = questions.create(self.actor, self.section, _question_data(subtext=dirty))
        client = Client()
        client.force_login(self.actor.user)
        client.post(f'/editor/surveys/{self.survey.uuid}/sections/{self.section.pk}/questions/new/',
                    _question_data(subtext=dirty, name='Editor'))
        via_editor = Question.objects.get(name='Editor')
        self.assertEqual(via_service.subtext, via_editor.subtext)
        self.assertNotIn('<script', via_service.subtext)

    def test_number_bounds_kept_on_create(self):
        """
        GIVEN a number question created with min and max
        WHEN the service saves it
        THEN validation_settings holds both
        """
        q = questions.create(self.actor, self.section, _question_data(
            input_type='number', choices_json='', vs_min_value='1', vs_max_value='10'))
        self.assertEqual(q.validation_settings, {'min_value': 1.0, 'max_value': 10.0})

    def test_inverted_feature_bounds_refused(self):
        """
        GIVEN a point question saved with min_features 5 and max_features 2
        WHEN the settings are parsed
        THEN ValidationFailed names max_features
        """
        with self.assertRaises(ValidationFailed) as ctx:
            questions.parse_validation_settings('point', {'vs_min_features': '5', 'vs_max_features': '2'})
        self.assertIn('max_features', ctx.exception.fields)

    @override_settings(MAP_REFERENCE_LAYERS=True)
    def test_refused_create_leaves_no_layer(self):
        """
        GIVEN a point question to source a layer from
        WHEN an Objects question naming layer=answers:<code> is created with an invalid colour
        THEN the create is refused and no SurveyMapLayer exists
        """
        Question.objects.create(survey_section=self.section, code='PT', name='Places',
                                input_type='point', order_number=1)
        with self.assertRaises(ValidationFailed):
            questions.create(self.actor, self.section, _question_data(
                input_type='layer_objects', choices_json='', layer='answers:PT', color='not-a-colour'))
        self.assertFalse(SurveyMapLayer.objects.exists())

    def test_bad_choices_json(self):
        """
        GIVEN malformed choices JSON
        WHEN a choice question is created
        THEN ValidationFailed at the choices stage, nothing stored
        """
        with self.assertRaises(ValidationFailed) as ctx:
            questions.create(self.actor, self.section, _question_data(choices_json='[{'))
        self.assertEqual(ctx.exception.stage, questions.Stage.CHOICES)
        self.assertFalse(Question.objects.exists())

    def _published_question(self):
        q = questions.create(self.actor, self.section, _question_data())
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        return q

    def test_live_wording_applied_and_rescreened(self):
        """
        GIVEN a published survey with a choice question
        WHEN only its name changes through the service
        THEN it is stored and the content screen runs with the live_edit trigger
        """
        q = self._published_question()
        with mock.patch('survey.services.locks.screen_survey') as screen:
            questions.update(self.actor, q, {'name': 'Renamed'}, partial=True)
        q.refresh_from_db()
        self.assertEqual(q.name, 'Renamed')
        screen.assert_called_once_with(self.survey, trigger='live_edit')

    def test_live_type_change_is_structural(self):
        """
        GIVEN a published survey with a choice question
        WHEN its type changes through the service
        THEN StructureLocked is raised and the type is unchanged
        """
        q = self._published_question()
        with self.assertRaises(StructureLocked) as ctx:
            questions.update(self.actor, q, {'input_type': 'text_line'}, partial=True, strict=True)
        self.assertIn('the question type', ctx.exception.reasons)
        q.refresh_from_db()
        self.assertEqual(q.input_type, 'choice')

    def test_partial_update_keeps_choices(self):
        """
        GIVEN a choice question with two options
        WHEN only its name is patched
        THEN the options are unchanged
        """
        q = questions.create(self.actor, self.section, _question_data())
        questions.update(self.actor, q, {'name': 'Renamed'}, partial=True)
        q.refresh_from_db()
        self.assertEqual([c['code'] for c in q.choices], [1, 2])

    def test_repeated_choice_codes_refused_on_save(self):
        """
        GIVEN a star rating with five options 1-5
        WHEN an editor save posts the list the old modal produced: five default
             stars followed by the saved five, codes 1-5 twice (#452)
        THEN ValidationFailed at the choices stage naming the codes, and the
             stored options are unchanged
        """
        five = [{'code': i, 'name': n} for i, n in enumerate(
            ['Unsafe', 'Slightly Safe', 'Somewhat Safe', 'Rather Safe', 'Very Safe'], start=1)]
        q = questions.create(self.actor, self.section, _question_data(
            input_type='rating', display_style='stars', choices_json=json.dumps(five)))
        doubled = [{'code': i, 'name': str(i)} for i in range(1, 6)] + five
        with self.assertRaises(ValidationFailed) as ctx:
            questions.update(self.actor, q, _question_data(
                input_type='rating', display_style='stars', choices_json=json.dumps(doubled)))
        self.assertEqual(ctx.exception.stage, questions.Stage.CHOICES)
        self.assertIn('1, 2, 3, 4, 5', str(ctx.exception.fields['choices']))
        q.refresh_from_db()
        self.assertEqual(q.choices, five)

    def test_set_choices_refuses_a_repeated_code(self):
        """
        GIVEN a choice question with two options
        WHEN set_choices (REST/MCP) is given two options that share code 1
        THEN ValidationFailed at the choices stage, and the options are unchanged
        """
        q = questions.create(self.actor, self.section, _question_data())
        with self.assertRaises(ValidationFailed) as ctx:
            questions.set_choices(self.actor, q, [{'code': 1, 'name': 'Red'}, {'code': 1, 'name': 'Green'}])
        self.assertEqual(ctx.exception.stage, questions.Stage.CHOICES)
        self.assertIn('code 1', str(ctx.exception.fields['choices']))
        q.refresh_from_db()
        self.assertEqual([c['code'] for c in q.choices], [1, 2])

    def test_removing_answered_choice_on_live_survey(self):
        """
        GIVEN a published survey whose option 1 was answered
        WHEN set_choices drops option 1
        THEN StructureLocked, and the options are unchanged
        """
        q = self._published_question()
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=q, selected_choices=[1])
        with self.assertRaises(StructureLocked):
            questions.set_choices(self.actor, q, [{'code': 2, 'name': 'Blue'}])
        q.refresh_from_db()
        self.assertEqual(len(q.choices), 2)


class ValidateRuleTest(TestCase):
    """visibility.validate_rule -- the strict check the API uses."""

    def setUp(self):
        self.survey, self.section, self.actor = _survey_with_section('rule')
        Question.objects.create(
            survey_section=self.section, code='C', name='C', input_type='choice', order_number=1,
            choices=[{'code': 1, 'name': 'Yes'}])
        Question.objects.create(
            survey_section=self.section, code='T', name='T', input_type='text_line', order_number=2)

    def _check(self, rule, order=None):
        from survey.visibility import validate_rule
        return validate_rule(rule, 'question', survey=self.survey, section=self.section, order=order)

    def test_valid_rule(self):
        """
        GIVEN a choice controller earlier in the section
        WHEN a new question's rule names it and an existing option
        THEN it passes
        """
        self.assertIsNone(self._check({'question_code': 'C', 'choice_codes': [1]}))

    def test_refusals(self):
        """
        GIVEN the same section
        WHEN a rule names a later controller, a text controller, or an unknown option
        THEN each is refused with a reason
        """
        self.assertIsNotNone(self._check({'question_code': 'C', 'choice_codes': [1]}, order=0))
        self.assertIsNotNone(self._check({'question_code': 'T', 'answered': True}))
        self.assertIn('unknown option', self._check({'question_code': 'C', 'choice_codes': [1, 9]}))


class PublishingServiceTest(TestCase):
    """services.publishing -- gaps, review state, audit actor."""

    def setUp(self):
        self.survey, self.section, self.actor = _survey_with_section('pub')
        questions.create(self.actor, self.section, _question_data())

    def test_publish_audited_with_actor(self):
        """
        GIVEN a draft survey with a question
        WHEN the service publishes it
        THEN the status is published and the audit row carries the actor and IP
        """
        result = publishing.transition(self.actor, self.survey, 'published')
        self.assertEqual(result.survey.status, 'published')
        row = AuditLog.objects.get(action='status_transition')
        self.assertEqual((row.actor, row.ip), (self.actor.user, '198.51.100.1'))

    def test_translation_gaps_refused(self):
        """
        GIVEN a survey offered in a second language without translations
        WHEN it is published without acknowledgement
        THEN TranslationGaps is raised and the status is unchanged
        """
        self.survey.available_languages = ['en', 'de']
        self.survey.save(update_fields=['available_languages'])
        with self.assertRaises(TranslationGaps):
            publishing.transition(self.actor, self.survey, 'published')
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status, 'draft')

    def test_held_publish_reports_review(self):
        """
        GIVEN content screening that holds the survey
        WHEN it is published
        THEN the result reports review='pending'
        """
        def hold(survey, trigger):
            ContentReview.objects.create(survey=survey, status='pending')
        with mock.patch('survey.services.publishing.screen_survey', side_effect=hold):
            result = publishing.transition(self.actor, self.survey, 'published')
        self.assertEqual(result.review, 'pending')

    def test_draft_copy_refused_when_asked(self):
        """
        GIVEN unpublished changes of a published survey
        WHEN the API-style transition is asked to publish the draft copy itself
        THEN Conflict is raised
        """
        publishing.transition(self.actor, self.survey, 'published')
        draft = publishing.create_draft(self.actor, self.survey)
        with self.assertRaises(Conflict):
            publishing.transition(self.actor, draft, 'published', refuse_draft_copy=True)
