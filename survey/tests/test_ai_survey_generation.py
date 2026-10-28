"""Tests for the `ai-survey-generation` capability (openspec/specs/ai-survey-generation/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from unittest import mock
from unittest.mock import patch
import json
import re
from survey.models import Organization, SurveyHeader, SurveySection, Question, Membership, SurveyCollaborator
from survey.serialization import ImportError
from survey.models import SurveySectionTranslation, QuestionTranslation, AIGenerationEvent
from survey.tests.helpers import _AIGenerationFixture, _FakeProvider, _FlakyProvider, _ProgressingProvider, _ai_blob, _ai_choice, _ai_question, _make_org


class AIValidatorTest(TestCase):
    """The gate that stops a hallucinated draft before it reaches the database."""

    def test_well_formed_draft_passes(self):
        """
        GIVEN a draft with two sections, choices and one geo question
        WHEN it is validated against the requested languages
        THEN no errors are reported
        """
        from survey.ai.validator import validate_blob

        self.assertEqual(validate_blob(_ai_blob(('en',)), ['en']), [])

    def test_missing_translation_is_rejected(self):
        """
        GIVEN a two-language survey whose first question lacks the German name
        WHEN the draft is validated
        THEN the missing translation is reported rather than silently falling back
        """
        from survey.ai.validator import validate_blob

        blob = _ai_blob(('en', 'de'))
        del blob['sections'][0]['questions'][0]['name']['de']

        errors = validate_blob(blob, ['en', 'de'])

        self.assertTrue(any('missing translations for de' in e for e in errors), errors)

    def test_second_top_level_geo_question_is_rejected(self):
        """
        GIVEN a draft with two top-level geo questions
        WHEN it is validated
        THEN the extra geo question is reported (geo is the most-skipped type)
        """
        from survey.ai.validator import validate_blob

        blob = _ai_blob(('en',))
        blob['sections'][0]['questions'].append(
            _ai_question('Draw your route', 'line', ('en',))
        )

        errors = validate_blob(blob, ['en'])

        self.assertTrue(any('at most one top-level geo question' in e for e in errors), errors)

    def test_draft_without_answerable_questions_is_rejected(self):
        """
        GIVEN a draft made only of html decoration blocks
        WHEN it is validated
        THEN it is rejected — it would import cleanly and collect nothing
        """
        from survey.ai.validator import validate_blob

        blob = {
            'sections': [
                {
                    'title': {'en': 'One'}, 'subheading': {'en': ''},
                    'questions': [_ai_question('Intro', 'html', ('en',))],
                },
                {
                    'title': {'en': 'Two'}, 'subheading': {'en': ''},
                    'questions': [_ai_question('Outro', 'html', ('en',))],
                },
            ],
        }

        errors = validate_blob(blob, ['en'])

        self.assertIn('the draft has no answerable questions', errors)

    def test_choice_question_without_choices_is_rejected(self):
        """
        GIVEN a choice question with an empty choices list
        WHEN the draft is validated
        THEN the missing choices are reported
        """
        from survey.ai.validator import validate_blob

        blob = _ai_blob(('en',))
        blob['sections'][0]['questions'][0]['choices'] = []

        errors = validate_blob(blob, ['en'])

        self.assertTrue(any('requires choices' in e for e in errors), errors)

    def test_non_integer_and_duplicate_choice_codes_are_rejected(self):
        """
        GIVEN choices with a string code and a duplicated code
        WHEN the draft is validated
        THEN both problems are reported — codes drive scales and answer merging
        """
        from survey.ai.validator import validate_blob

        blob = _ai_blob(('en',))
        blob['sections'][0]['questions'][0]['choices'] = [
            _ai_choice('one', 'On foot'), _ai_choice(2, 'By bike'), _ai_choice(2, 'By car'),
        ]

        errors = validate_blob(blob, ['en'])

        self.assertTrue(any('non-integer code' in e for e in errors), errors)
        self.assertTrue(any('must be unique' in e for e in errors), errors)

    def test_descending_rating_codes_are_rejected(self):
        """
        GIVEN a rating question whose codes descend
        WHEN the draft is validated
        THEN it is rejected because min/max are derived from code order
        """
        from survey.ai.validator import validate_blob

        blob = _ai_blob(('en',))
        blob['sections'][1]['questions'][1]['choices'] = [
            _ai_choice(5, 'Severe'), _ai_choice(1, 'Minor'),
        ]

        errors = validate_blob(blob, ['en'])

        self.assertTrue(any('must ascend' in e for e in errors), errors)

    def test_section_count_outside_bounds_is_rejected(self):
        """
        GIVEN a draft with a single section
        WHEN it is validated
        THEN the section count is reported
        """
        from survey.ai.validator import validate_blob

        blob = _ai_blob(('en',))
        blob['sections'] = blob['sections'][:1]

        errors = validate_blob(blob, ['en'])

        self.assertTrue(any('between 2 and 4 sections' in e for e in errors), errors)

    def test_geo_question_without_style_is_rejected(self):
        """
        GIVEN a point question with no color and no icon
        WHEN the draft is validated
        THEN both are reported — a default black marker reads as unfinished
        """
        from survey.ai.validator import validate_blob

        blob = _ai_blob(('en',))
        blob['sections'][1]['questions'][0]['color'] = ''
        blob['sections'][1]['questions'][0]['icon'] = 'none'

        errors = validate_blob(blob, ['en'])

        self.assertTrue(any('hex color' in e for e in errors), errors)
        self.assertTrue(any('marker icon' in e for e in errors), errors)

    def test_unknown_icon_is_rejected(self):
        """
        GIVEN an icon outside the curated list
        WHEN the draft is validated
        THEN it is rejected — a hallucinated FA class silently draws nothing
        """
        from survey.ai.validator import validate_blob

        blob = _ai_blob(('en',))
        blob['sections'][1]['questions'][0]['icon'] = 'sparkling-unicorn'

        errors = validate_blob(blob, ['en'])

        self.assertTrue(any('unknown icon' in e for e in errors), errors)

    def test_geo_sub_question_is_rejected(self):
        """
        GIVEN a geo question whose sub-question is itself a geo question
        WHEN the draft is validated
        THEN it is rejected — the editor forbids geo sub-questions
        """
        from survey.ai.validator import validate_blob

        blob = _ai_blob(('en',))
        blob['sections'][1]['questions'][0]['sub_questions'] = [
            _ai_question('Draw it', 'polygon', ('en',))
        ]

        errors = validate_blob(blob, ['en'])

        self.assertTrue(any('invalid input_type' in e for e in errors), errors)


class AIMaterializeTest(TestCase):
    """Turning a validated draft into rows, with structure computed not generated."""

    def setUp(self):
        self.org = _make_org('AIMaterializeOrg')
        self.user = User.objects.create_user('aimatuser', password='pass')

    def _materialize(self, blob, languages=('en',)):
        from survey.ai.materialize import header_overrides_from_form, materialize_draft

        overrides = header_overrides_from_form(
            name='ai_draft', languages=list(languages),
            map_lat='52.52', map_lng='13.405', map_zoom='12', default_basemap='streets',
        )
        return materialize_draft(
            blob, overrides, list(languages),
            organization=self.org, created_by=self.user,
        )

    def test_structure_is_computed_from_list_order(self):
        """
        GIVEN a model draft that contains no codes, is_head or section links
        WHEN it is materialized
        THEN exactly one head section exists and the sections form one chain
        """
        survey, _warnings = self._materialize(_ai_blob(('en',)))

        sections = list(SurveySection.objects.filter(survey_header=survey).order_by('code'))
        self.assertEqual([s.code for s in sections], ['S1', 'S2'])
        self.assertEqual([s.is_head for s in sections], [True, False])
        self.assertEqual(sections[0].next_section_id, sections[1].id)
        self.assertEqual(sections[1].prev_section_id, sections[0].id)
        self.assertIsNone(sections[1].next_section_id)

    def test_questions_get_unique_codes_and_sequential_order(self):
        """
        GIVEN a draft whose questions carry no codes
        WHEN it is materialized
        THEN every question has a distinct code and order_number runs 1..N per section
        """
        survey, _warnings = self._materialize(_ai_blob(('en',)))

        questions = list(Question.objects.filter(survey_section__survey_header=survey))
        codes = [q.code for q in questions]
        self.assertEqual(len(codes), len(set(codes)))
        second_section = SurveySection.objects.get(survey_header=survey, code='S2')
        top_level = list(
            Question.objects.filter(survey_section=second_section, parent_question_id__isnull=True)
            .order_by('order_number')
        )
        self.assertEqual([q.order_number for q in top_level], [1, 2])

    def test_sub_question_is_attached_to_its_geo_parent(self):
        """
        GIVEN a point question with one sub-question
        WHEN the draft is materialized
        THEN the sub-question hangs off the point question, not off the section
        """
        survey, _warnings = self._materialize(_ai_blob(('en',)))

        point = Question.objects.get(
            survey_section__survey_header=survey, input_type='point',
        )
        subs = list(Question.objects.filter(parent_question_id=point))
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0].input_type, 'text')

    def test_non_primary_languages_get_translation_rows_primary_stays_in_base(self):
        """
        GIVEN a two-language draft
        WHEN it is materialized
        THEN sections and questions carry translation rows for the non-primary
             language only, and the primary text lives in base fields — a
             primary row would shadow later base-field edits via the fallback
        """
        survey, _warnings = self._materialize(_ai_blob(('en', 'de')), ('en', 'de'))

        section = SurveySection.objects.filter(survey_header=survey, code='S1').first()
        languages = set(
            SurveySectionTranslation.objects.filter(section=section)
            .values_list('language', flat=True)
        )
        self.assertEqual(languages, {'de'})
        self.assertEqual(section.title, 'About you [en]')
        question = Question.objects.filter(survey_section=section).first()
        q_languages = set(
            QuestionTranslation.objects.filter(question=question)
            .values_list('language', flat=True)
        )
        self.assertEqual(q_languages, {'de'})

    def test_single_language_draft_creates_no_translation_rows_and_flat_choices(self):
        """
        GIVEN a single-language draft whose choice names are locale dicts
        WHEN it is materialized
        THEN no translation rows exist and choice names collapse to flat
             strings — the shapes the choices editor itself saves
        """
        survey, _warnings = self._materialize(_ai_blob(('en',)), ('en',))

        self.assertFalse(
            SurveySectionTranslation.objects.filter(section__survey_header=survey).exists()
        )
        self.assertFalse(
            QuestionTranslation.objects.filter(
                question__survey_section__survey_header=survey,
            ).exists()
        )
        choice_q = Question.objects.get(
            survey_section__survey_header=survey, input_type='choice',
        )
        self.assertEqual(
            [c['name'] for c in choice_q.choices],
            ['On foot [en]', 'By bike [en]'],
        )

    def test_multilingual_choice_dicts_keep_the_primary_key(self):
        """
        GIVEN a two-language draft
        WHEN it is materialized
        THEN choice name dicts keep both languages — the primary key is the
             base slot for choices, there is no separate base field in the JSON
        """
        survey, _warnings = self._materialize(_ai_blob(('en', 'de')), ('en', 'de'))

        choice_q = Question.objects.get(
            survey_section__survey_header=survey, input_type='choice',
        )
        for choice in choice_q.choices:
            self.assertEqual(set(choice['name'].keys()), {'en', 'de'})

    def test_header_comes_from_the_form_not_the_model(self):
        """
        GIVEN map position and languages picked by the creator
        WHEN the draft is materialized
        THEN the survey header carries those values and starts as a draft
        """
        survey, _warnings = self._materialize(_ai_blob(('en',)))

        self.assertEqual(survey.name, 'ai_draft')
        self.assertEqual(survey.status, 'draft')
        self.assertEqual(survey.available_languages, ['en'])
        self.assertEqual(survey.start_map_zoom, 12)
        self.assertIsNotNone(survey.start_map_postion)

    def test_marker_style_reaches_the_question_row(self):
        """
        GIVEN a point question styled by the model
        WHEN the draft is materialized
        THEN the row carries the hex color and the fas-prefixed icon class
        """
        survey, _warnings = self._materialize(_ai_blob(('en',)))

        point = Question.objects.get(
            survey_section__survey_header=survey, input_type='point',
        )
        self.assertEqual(point.color, '#E8590C')
        self.assertEqual(point.icon_class, 'fas fa-map-marker-alt')

    def test_import_failure_leaves_nothing_behind(self):
        """
        GIVEN a draft that the import path rejects (unknown input_type)
        WHEN materialization runs inside a transaction
        THEN it raises and no survey survives
        """
        from django.db import transaction
        from survey.serialization import ImportError as ImportError

        blob = _ai_blob(('en',))
        blob['sections'][0]['questions'][0]['input_type'] = 'telepathy'
        before = SurveyHeader.objects.count()

        with self.assertRaises(ImportError):
            with transaction.atomic():
                self._materialize(blob)

        self.assertEqual(SurveyHeader.objects.count(), before)


class AIProviderErrorClassificationTest(TestCase):
    """Which failures are worth another try, decided where the status is seen."""

    def test_server_side_statuses_are_transient(self):
        """
        GIVEN a 429 or any 5xx
        WHEN it is classified
        THEN it is transient, because it describes the provider's moment
        """
        from survey.ai.client import _transient_status

        for status in (429, 500, 502, 503, 504):
            self.assertTrue(_transient_status(status), status)

    def test_client_side_statuses_are_verdicts(self):
        """
        GIVEN a 4xx other than rate limiting
        WHEN it is classified
        THEN it is not transient, because it describes our request
        """
        from survey.ai.client import _transient_status

        for status in (400, 401, 403, 404):
            self.assertFalse(_transient_status(status), status)

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='')
    def test_gemini_overload_is_raised_as_transient(self):
        """
        GIVEN the provider answering 503
        WHEN the call is made
        THEN the raised error is marked transient, which is what earns the retry
        """
        from survey.ai.client import GeminiProvider, ProviderError

        response = mock.MagicMock()
        response.status_code = 503
        response.json.return_value = {'error': {'message': 'high demand'}}

        with patch('requests.post', return_value=response):
            with self.assertRaises(ProviderError) as raised:
                GeminiProvider().complete_structured(
                    system='s', user='u', schema={'type': 'object'},
                )

        self.assertTrue(raised.exception.transient)

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='')
    def test_gemini_unparseable_output_is_transient(self):
        """
        GIVEN a 200 whose body is not the JSON the schema demanded
        WHEN the call is made
        THEN the error is transient: this is the failure that hit production on
             2026-08-17 and it is the provider stumbling, not a bad brief
        """
        from survey.ai.client import GeminiProvider, ProviderError

        response = mock.MagicMock()
        response.status_code = 200
        response.json.return_value = {
            'usageMetadata': {'promptTokenCount': 1},
            'candidates': [{'finishReason': 'STOP',
                            'content': {'parts': [{'text': '{"sections": [{"tit'}]}}],
        }

        with patch('requests.post', return_value=response):
            with self.assertRaises(ProviderError) as raised:
                GeminiProvider().complete_structured(
                    system='s', user='u', schema={'type': 'object'},
                )

        self.assertTrue(raised.exception.transient)

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='')
    def test_retired_model_is_not_transient(self):
        """
        GIVEN a 404 for a model this key cannot use
        WHEN the call is made
        THEN the error is final, because retrying cannot make the model exist
        """
        from survey.ai.client import GeminiProvider, ProviderError

        response = mock.MagicMock()
        response.status_code = 404
        response.json.return_value = {'error': {'message': 'model not found'}}

        with patch('requests.post', return_value=response):
            with self.assertRaises(ProviderError) as raised:
                GeminiProvider().complete_structured(
                    system='s', user='u', schema={'type': 'object'},
                )

        self.assertFalse(raised.exception.transient)


class AIClientConfigTest(TestCase):
    """Credentials absent is a state, not an error."""

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='')
    def test_missing_key_reports_not_configured(self):
        """
        GIVEN no provider credentials
        WHEN a provider is requested
        THEN NotConfigured is raised before any network call is attempted
        """
        from survey.ai import client

        self.assertFalse(client.provider_configured())
        with self.assertRaises(client.NotConfigured):
            client.get_provider()

    @override_settings(AI_PROVIDER='nonexistent', ANTHROPIC_API_KEY='sk-test')
    def test_unknown_provider_reports_not_configured(self):
        """
        GIVEN AI_PROVIDER naming a provider that has no implementation
        WHEN a provider is requested
        THEN NotConfigured is raised rather than an opaque KeyError
        """
        from survey.ai import client

        self.assertFalse(client.provider_configured())
        with self.assertRaises(client.NotConfigured):
            client.get_provider()


class AIGenerationFlowTest(_AIGenerationFixture, TestCase):
    """The orchestrator: provider → validator → materializer → event."""

    def test_successful_generation_creates_survey_and_owner(self):
        """
        GIVEN a provider returning a valid draft
        WHEN generation runs
        THEN a survey exists, the creator owns it, and the event records usage
        """
        provider = _FakeProvider([_ai_blob(('en',))])

        event = self._run(provider)

        self.assertEqual(event.outcome, 'success')
        self.assertIsNotNone(event.created_survey_id)
        self.assertEqual(event.input_tokens, 100)
        self.assertEqual(event.latency_ms, 1234)
        self.assertTrue(SurveyCollaborator.objects.filter(
            survey=event.created_survey, user=self.user, role='owner',
        ).exists())
        self.assertEqual(len(provider.calls), 1)

    def test_invalid_draft_is_retried_once_then_rejected(self):
        """
        GIVEN a provider that returns an invalid draft twice
        WHEN generation runs
        THEN exactly two calls are made, nothing is written, and the outcome says why
        """
        bad = _ai_blob(('en',))
        bad['sections'] = bad['sections'][:1]
        provider = _FakeProvider([bad, dict(bad)])
        before = SurveyHeader.objects.count()

        event = self._run(provider)

        self.assertEqual(event.outcome, 'invalid_draft')
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(SurveyHeader.objects.count(), before)
        self.assertIn('sections', event.error_detail)

    def test_retry_prompt_carries_the_validation_errors(self):
        """
        GIVEN a first draft that fails validation and a valid second one
        WHEN generation runs
        THEN the second prompt tells the model what was wrong, and the draft is saved
        """
        bad = _ai_blob(('en',))
        bad['sections'] = bad['sections'][:1]
        provider = _FakeProvider([bad, _ai_blob(('en',))])

        event = self._run(provider)

        self.assertEqual(event.outcome, 'success')
        self.assertEqual(len(provider.calls), 2)
        self.assertIn('rejected for these reasons', provider.calls[1])

    def test_provider_error_writes_nothing(self):
        """
        GIVEN a provider that fails to answer
        WHEN generation runs
        THEN the failure is recorded and no partial survey is left behind
        """
        from survey.ai.client import ProviderError

        provider = _FakeProvider([], error=ProviderError('connection error'))
        before = SurveyHeader.objects.count()

        event = self._run(provider)

        self.assertEqual(event.outcome, 'provider_error')
        self.assertEqual(SurveyHeader.objects.count(), before)

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='')
    def test_unconfigured_provider_is_recorded_not_raised(self):
        """
        GIVEN no provider credentials
        WHEN generation runs
        THEN the event records not_configured instead of the task crashing
        """
        from survey.ai.generation import generate_survey_draft, start_generation

        brief = self._brief()
        event = start_generation(self.user, self.org, brief, ['en'])

        generate_survey_draft(event, brief, ['en'], {'name': 'x', 'available_languages': ['en']})

        event.refresh_from_db()
        self.assertEqual(event.outcome, 'not_configured')


class AIBriefLocationTest(_AIGenerationFixture, TestCase):
    """The place the model reads from the brief becomes the start position
    (openspec: create-map-location-from-brief) — unless the creator framed
    the map, and never at the cost of the draft."""

    TALLINN = (59.4370, 24.7536, 12)

    def _blob_with_location(self, location):
        blob = _ai_blob(('en',))
        blob['location'] = location
        return blob

    def _run_with(self, blob, map_locked, resolved):
        from survey.ai.generation import generate_survey_draft, start_generation
        from survey.ai.materialize import header_overrides_from_form

        brief = self._brief()
        event = start_generation(self.user, self.org, brief, ['en'])
        overrides = header_overrides_from_form(
            name=brief.name, languages=['en'],
            map_lat='52.52', map_lng='13.405', map_zoom='12', default_basemap='streets',
        )
        provider = _FakeProvider([blob])
        with patch('survey.ai.generation.client.get_provider', return_value=provider), \
                patch('survey.ai.generation.geocode_place', return_value=resolved) as geocode:
            generate_survey_draft(event, brief, ['en'], overrides, map_locked=map_locked)
        event.refresh_from_db()
        return event, geocode

    def test_untouched_map_takes_the_briefs_place(self):
        """
        GIVEN the creator left the create-page map alone and the model named a place
        WHEN the place geocodes
        THEN the survey opens on the geocoded point at the place-type zoom
        """
        event, geocode = self._run_with(
            self._blob_with_location('Tallinn, Estonia'), map_locked=False, resolved=self.TALLINN,
        )

        self.assertEqual(event.outcome, 'success')
        geocode.assert_called_once_with('Tallinn, Estonia')
        survey = event.created_survey
        self.assertAlmostEqual(survey.start_map_postion.y, 59.4370, places=4)
        self.assertAlmostEqual(survey.start_map_postion.x, 24.7536, places=4)
        self.assertEqual(survey.start_map_zoom, 12)

    def test_creator_framed_map_wins_and_skips_the_lookup(self):
        """
        GIVEN the creator dragged the map (map_touched posted)
        WHEN the model also names a resolvable place
        THEN the form position is kept and no geocode request is made
        """
        event, geocode = self._run_with(
            self._blob_with_location('Tallinn, Estonia'), map_locked=True, resolved=self.TALLINN,
        )

        self.assertEqual(event.outcome, 'success')
        geocode.assert_not_called()
        survey = event.created_survey
        self.assertAlmostEqual(survey.start_map_postion.y, 52.52, places=4)
        self.assertAlmostEqual(survey.start_map_postion.x, 13.405, places=4)
        self.assertEqual(survey.start_map_zoom, 12)

    def test_unresolvable_place_falls_back_to_the_form(self):
        """
        GIVEN an untouched map and a place the geocoder cannot resolve
        WHEN generation runs
        THEN the draft still succeeds on the form position
        """
        event, geocode = self._run_with(
            self._blob_with_location('Nowhere Particular'), map_locked=False, resolved=None,
        )

        self.assertEqual(event.outcome, 'success')
        geocode.assert_called_once()
        self.assertAlmostEqual(event.created_survey.start_map_postion.y, 52.52, places=4)

    def test_empty_location_makes_no_lookup(self):
        """
        GIVEN a brief that names no place, so the model returned ""
        WHEN generation runs
        THEN no geocode request is made and the form position is used
        """
        event, geocode = self._run_with(self._blob_with_location(''), map_locked=False, resolved=self.TALLINN)

        self.assertEqual(event.outcome, 'success')
        geocode.assert_not_called()
        self.assertAlmostEqual(event.created_survey.start_map_postion.x, 13.405, places=4)

    def test_returned_location_is_kept_on_the_event(self):
        """
        GIVEN a successful generation
        WHEN the blob is stored on the event
        THEN the location the model returned is readable from generated_blob
        """
        event, _ = self._run_with(
            self._blob_with_location('Tallinn, Estonia'), map_locked=False, resolved=self.TALLINN,
        )

        self.assertEqual(event.generated_blob['location'], 'Tallinn, Estonia')

    def test_bad_location_is_normalized_not_rejected(self):
        """
        GIVEN drafts whose location is missing, not a string, or over-long
        WHEN they are validated
        THEN validation passes and the location reads as empty
        """
        from survey.ai.validator import MAX_LOCATION_CHARS, validate_blob

        for bad in ({}, {'location': 42}, {'location': 'x' * (MAX_LOCATION_CHARS + 1)}):
            blob = _ai_blob(('en',))
            blob.pop('location', None)
            blob.update(bad)
            self.assertEqual(validate_blob(blob, ['en']), [], bad)
            self.assertEqual(blob['location'], '', bad)

        blob = self._blob_with_location('  Tallinn, Estonia  ')
        self.assertEqual(validate_blob(blob, ['en']), [])
        self.assertEqual(blob['location'], 'Tallinn, Estonia')

    def test_schema_requires_location(self):
        """
        GIVEN the strict response schema
        WHEN it is built
        THEN location is a required top-level string, so the model always answers it
        """
        from survey.ai.schema import survey_draft_schema

        schema = survey_draft_schema(['en'])
        self.assertEqual(schema['properties']['location'], {'type': 'string'})
        self.assertIn('location', schema['required'])


class AIGeocodePlaceTest(TestCase):
    """One bounded Photon lookup that can only ever return a position or None."""

    def _response(self, status=200, payload=None):
        response = mock.Mock()
        response.status_code = status
        response.json.return_value = payload if payload is not None else {}
        return response

    def _feature(self, lng, lat, place_type):
        return {'features': [{
            'geometry': {'coordinates': [lng, lat]},
            'properties': {'type': place_type, 'name': 'x'},
        }]}

    def test_hit_returns_position_and_type_zoom(self):
        """
        GIVEN Photon answers with a country
        WHEN the place is geocoded
        THEN lat/lng come back in that order with the country zoom
        """
        from survey.ai import geocode

        with patch('survey.ai.geocode.requests.get', return_value=self._response(
                payload=self._feature(25.0, 58.6, 'country'))) as get:
            self.assertEqual(geocode.geocode_place('Estonia'), (58.6, 25.0, 6))
        kwargs = get.call_args.kwargs
        self.assertEqual(kwargs['params'], {'q': 'Estonia', 'limit': 1})
        self.assertLessEqual(kwargs['timeout'], 4)

    def test_city_gets_default_zoom(self):
        """
        GIVEN Photon answers with a city
        WHEN the place is geocoded
        THEN the default (city) zoom is used
        """
        from survey.ai import geocode

        with patch('survey.ai.geocode.requests.get', return_value=self._response(
                payload=self._feature(24.75, 59.44, 'city'))):
            self.assertEqual(geocode.geocode_place('Tallinn')[2], geocode.ZOOM_DEFAULT)

    def test_every_failure_is_none(self):
        """
        GIVEN an empty result, a non-200, a timeout, a malformed feature, or a blank name
        WHEN the place is geocoded
        THEN the result is None and nothing raises
        """
        import requests as requests_lib
        from survey.ai import geocode

        cases = [
            self._response(payload={'features': []}),
            self._response(status=503),
            self._response(payload={'features': [{'geometry': {}}]}),
        ]
        for response in cases:
            with patch('survey.ai.geocode.requests.get', return_value=response):
                self.assertIsNone(geocode.geocode_place('Tallinn'))
        with patch('survey.ai.geocode.requests.get', side_effect=requests_lib.Timeout()):
            self.assertIsNone(geocode.geocode_place('Tallinn'))
        with patch('survey.ai.geocode.requests.get') as get:
            self.assertIsNone(geocode.geocode_place('   '))
            get.assert_not_called()


class AIThinkingLevelRequestTest(TestCase):
    """Reasoning effort is a value we send, not a provider default we inherit."""

    def _post_and_capture(self):
        """Run one Gemini call against a stubbed transport, return the request body."""
        from survey.ai.client import GeminiProvider

        response = mock.MagicMock()
        response.status_code = 200
        response.json.return_value = {
            'usageMetadata': {'promptTokenCount': 10, 'candidatesTokenCount': 20,
                              'totalTokenCount': 30},
            'candidates': [{'finishReason': 'STOP',
                            'content': {'parts': [{'text': '{"ok": true}'}]}}],
        }
        with patch('requests.post', return_value=response) as post:
            GeminiProvider().complete_structured(
                system='sys', user='usr', schema={'type': 'object'},
            )
        return post.call_args.kwargs['json']

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='low')
    def test_configured_level_is_sent(self):
        """
        GIVEN AI_THINKING_LEVEL set to a non-empty value
        WHEN a Gemini generation is requested
        THEN the request body carries it at generationConfig.thinkingConfig.thinkingLevel
        """
        payload = self._post_and_capture()

        self.assertEqual(
            payload['generationConfig']['thinkingConfig']['thinkingLevel'], 'low',
        )

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='')
    def test_empty_level_omits_the_key_entirely(self):
        """
        GIVEN AI_THINKING_LEVEL set to an empty string
        WHEN a Gemini generation is requested
        THEN no thinkingConfig key is present, so a model that rejects the field
             can be worked around by configuration rather than by a deploy
        """
        payload = self._post_and_capture()

        self.assertNotIn('thinkingConfig', payload['generationConfig'])


class AIThinkingTokensTest(TestCase):
    """Reasoning usage: read it where reported, derive it where implied, else absent."""

    def test_reported_field_wins(self):
        """
        GIVEN usage metadata carrying a reasoning-token count
        WHEN reasoning usage is read
        THEN that value is used without consulting the derived fallback
        """
        from survey.ai.client import _thinking_tokens

        meta = {'thoughtsTokenCount': 512, 'promptTokenCount': 10,
                'candidatesTokenCount': 20, 'totalTokenCount': 30}

        self.assertEqual(_thinking_tokens(meta), 512)

    def test_derived_from_the_total_when_no_field(self):
        """
        GIVEN metadata with no reasoning field but a total exceeding prompt plus candidates
        WHEN reasoning usage is read
        THEN the difference is returned
        """
        from survey.ai.client import _thinking_tokens

        meta = {'promptTokenCount': 100, 'candidatesTokenCount': 200,
                'totalTokenCount': 900}

        self.assertEqual(_thinking_tokens(meta), 600)

    def test_absent_is_none_not_zero(self):
        """
        GIVEN metadata whose total is fully accounted for by prompt and candidates
        WHEN reasoning usage is read
        THEN it is None, because "not reported" and "reasoned for nothing" are
             different facts and a zero would average the first into the second
        """
        from survey.ai.client import _thinking_tokens

        meta = {'promptTokenCount': 100, 'candidatesTokenCount': 200,
                'totalTokenCount': 300}

        self.assertIsNone(_thinking_tokens(meta))

    def test_missing_total_is_none(self):
        """
        GIVEN metadata with neither a reasoning field nor a total
        WHEN reasoning usage is read
        THEN it is None rather than a value derived from absent numbers
        """
        from survey.ai.client import _thinking_tokens

        self.assertIsNone(_thinking_tokens({'promptTokenCount': 100}))


class AIGenerationLatencyAccountingTest(_AIGenerationFixture, TestCase):
    """A retried generation must not read as one fast call."""

    def test_single_attempt_totals_equal_the_one_call(self):
        """
        GIVEN a provider whose first draft passes validation
        WHEN generation runs
        THEN one attempt is recorded and the summed elapsed equals latency_ms
        """
        provider = _FakeProvider([_ai_blob(('en',))])

        event = self._run(provider)

        self.assertEqual(event.attempts, 1)
        self.assertEqual(event.total_latency_ms, event.latency_ms)
        self.assertEqual(event.total_latency_ms, 1234)

    def test_retry_sums_elapsed_and_tokens_but_not_latency_ms(self):
        """
        GIVEN a first draft rejected by validation and a valid second one
        WHEN generation runs
        THEN both calls are accounted, while latency_ms stays the terminal call's
        """
        bad = _ai_blob(('en',))
        bad['sections'] = bad['sections'][:1]
        provider = _FakeProvider(
            [bad, _ai_blob(('en',))],
            usages=[{'latency_ms': 40000, 'input_tokens': 1000, 'output_tokens': 500},
                    {'latency_ms': 9000, 'input_tokens': 1100, 'output_tokens': 700}],
        )

        event = self._run(provider)

        self.assertEqual(event.outcome, 'success')
        self.assertEqual(event.attempts, 2)
        self.assertEqual(event.total_latency_ms, 49000)
        self.assertEqual(event.latency_ms, 9000)
        self.assertEqual(event.input_tokens, 2100)
        self.assertEqual(event.output_tokens, 1200)

    def test_failed_set_is_accounted_too(self):
        """
        GIVEN every attempt in the set rejected by validation
        WHEN generation runs
        THEN the attempt count and summed elapsed are still recorded
        """
        bad = _ai_blob(('en',))
        bad['sections'] = bad['sections'][:1]
        provider = _FakeProvider(
            [bad, dict(bad)],
            usages=[{'latency_ms': 5000}, {'latency_ms': 6000}],
        )

        event = self._run(provider)

        self.assertEqual(event.outcome, 'invalid_draft')
        self.assertEqual(event.attempts, 2)
        self.assertEqual(event.total_latency_ms, 11000)

    def test_provider_error_counts_the_call_it_could_not_measure(self):
        """
        GIVEN a provider whose first call raises before reporting any usage
        WHEN generation runs
        THEN the attempt is counted, and elapsed stays absent rather than invented
        """
        from survey.ai.client import ProviderError

        provider = _FakeProvider([], error=ProviderError('API error 503: high demand'))

        event = self._run(provider)

        self.assertEqual(event.outcome, 'provider_error')
        self.assertEqual(event.attempts, 1)
        self.assertIsNone(event.total_latency_ms)

    def test_thinking_tokens_sum_only_over_calls_that_reported(self):
        """
        GIVEN one attempt reporting reasoning usage and one not
        WHEN generation runs
        THEN the reported one is summed and the silent one contributes nothing
        """
        bad = _ai_blob(('en',))
        bad['sections'] = bad['sections'][:1]
        provider = _FakeProvider(
            [bad, _ai_blob(('en',))],
            usages=[{'thinking_tokens': 800}, {'thinking_tokens': None}],
        )

        event = self._run(provider)

        self.assertEqual(event.thinking_tokens, 800)

    def test_thinking_tokens_stay_absent_when_nothing_reports(self):
        """
        GIVEN a provider that never reports reasoning usage
        WHEN generation runs
        THEN the row records None, not 0
        """
        provider = _FakeProvider([_ai_blob(('en',))])

        event = self._run(provider)

        self.assertIsNone(event.thinking_tokens)

    def test_analytics_carries_the_accounting_and_omits_what_is_absent(self):
        """
        GIVEN a successful generation with no reasoning usage reported
        WHEN ai_draft_finished is emitted
        THEN attempts and elapsed are present and thinking_tokens is omitted
             rather than sent as a zero that a breakdown would average in
        """
        provider = _FakeProvider([_ai_blob(('en',))])

        with patch('survey.product_events.emit') as emit:
            self._run(provider)

        finished = [c for c in emit.call_args_list
                    if c.args[0] == 'ai_draft_finished']
        self.assertEqual(len(finished), 1)
        props = finished[0].args[2]
        self.assertEqual(props['attempts'], 1)
        self.assertEqual(props['total_latency_ms'], 1234)
        self.assertNotIn('thinking_tokens', props)


class DraftProgressScannerTest(TestCase):
    """Progress counted from structure, so it cannot drift into fiction."""

    def _draft(self, sections):
        """A draft blob's JSON text with `sections` sections of two questions each."""
        section = ('{"title": {"en": "T"}, "subheading": {"en": "S"}, "questions": ['
                   '{"name": "q1"}, {"name": "q2"}]}')
        return '{"sections": [' + ', '.join([section] * sections) + ']}'

    def test_counts_sections_and_questions(self):
        """
        GIVEN a complete draft fed in one piece
        WHEN the scanner consumes it
        THEN it reports every closed section and question
        """
        from survey.ai.progress import DraftProgress

        tracker = DraftProgress()
        tracker.feed(self._draft(3))

        self.assertEqual(tracker.sections, 3)
        self.assertEqual(tracker.questions, 6)

    def test_chunk_boundaries_do_not_change_the_count(self):
        """
        GIVEN the same draft split at every possible character boundary
        WHEN the scanner consumes it chunk by chunk
        THEN the totals match the unsplit reading, because a stream's chunking
             is the provider's business and must not be visible in the count
        """
        from survey.ai.progress import DraftProgress

        text = self._draft(2)
        for size in (1, 3, 7, 50):
            tracker = DraftProgress()
            for start in range(0, len(text), size):
                tracker.feed(text[start:start + size])
            self.assertEqual((tracker.sections, tracker.questions), (2, 4),
                             'chunk size %d' % size)

    def test_braces_and_quotes_in_label_text_are_not_structure(self):
        """
        GIVEN question text containing braces, brackets, quotes and backslashes
        WHEN the scanner consumes it
        THEN the counts are unaffected, because a creator's wording is not JSON
        """
        from survey.ai.progress import DraftProgress

        text = (
            '{"sections": [{"title": {"en": "Where {is} it [worst]?"}, '
            '"subheading": {"en": "say \\"why\\" \\\\ how"}, '
            '"questions": [{"name": "a {b} [c]"}]}]}'
        )

        tracker = DraftProgress()
        tracker.feed(text)

        self.assertEqual((tracker.sections, tracker.questions), (1, 1))

    def test_open_section_is_not_counted_until_it_closes(self):
        """
        GIVEN a stream cut off midway through the second section
        WHEN the scanner consumes what arrived
        THEN only the completed section counts, so the number never has to go
             backwards if the stream then fails
        """
        from survey.ai.progress import DraftProgress

        text = self._draft(2)
        tracker = DraftProgress()
        tracker.feed(text[:text.rindex('{"title"')])

        self.assertEqual(tracker.sections, 1)

    def test_feed_reports_whether_anything_advanced(self):
        """
        GIVEN a chunk that closes nothing
        WHEN it is fed
        THEN feed() reports no advance, which is what suppresses a needless write
        """
        from survey.ai.progress import DraftProgress

        tracker = DraftProgress()

        self.assertFalse(tracker.feed('{"sections": [{"title": '))
        self.assertTrue(tracker.feed('{"en": "T"}, "questions": []}'))

    def test_unbalanced_close_is_ignored_not_raised(self):
        """
        GIVEN corrupt text with more closing braces than opening ones
        WHEN the scanner consumes it
        THEN it does not raise, because a counter must never be the reason a
             draft fails
        """
        from survey.ai.progress import DraftProgress

        tracker = DraftProgress()
        tracker.feed('}}]}')

        self.assertEqual(tracker.sections, 0)


class GeminiStreamingTest(TestCase):
    """Streaming changes how the blob arrives, not what happens to it."""

    def _sse(self, events):
        """Encode dicts as the SSE byte lines the provider will read back.

        Bytes, not str, because that is what `requests.iter_lines()` actually
        yields — and the distinction is not pedantry: a fake that spoke str is
        exactly why the mojibake bug (UTF-8 stream decoded as the ISO-8859-1
        default) shipped with green tests. `ensure_ascii=False` so Cyrillic
        content crosses the wire as real UTF-8 bytes, the way Gemini sends it.
        """
        lines = []
        for event in events:
            lines.append(('data: %s' % json.dumps(event, ensure_ascii=False)).encode('utf-8'))
            lines.append(b'')
        return lines

    def _chunk(self, text, finish_reason=None, usage=None):
        event = {'candidates': [{'content': {'parts': [{'text': text}]}}]}
        if finish_reason:
            event['candidates'][0]['finishReason'] = finish_reason
        if usage:
            event['usageMetadata'] = usage
        return event

    def _stream(self, events):
        response = mock.MagicMock()
        response.status_code = 200
        response.iter_lines.return_value = iter(self._sse(events))
        return response

    def _blob_text(self):
        return ('{"sections": [{"title": {"en": "T"}, "subheading": {"en": "S"}, '
                '"questions": [{"name": "q1"}]}]}')

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='low')
    def test_progress_is_reported_and_the_result_is_unchanged(self):
        """
        GIVEN a callback and a response streamed in several chunks
        WHEN generation runs
        THEN progress is reported as sections close, and the parsed blob and
             usage are what the same response would have produced unstreamed
        """
        from survey.ai.client import GeminiProvider

        text = self._blob_text()
        events = [
            self._chunk(text[:40]),
            self._chunk(text[40:]),
            self._chunk('', finish_reason='STOP',
                        usage={'promptTokenCount': 11, 'candidatesTokenCount': 22,
                               'totalTokenCount': 60}),
        ]
        seen = []

        with patch('requests.post', return_value=self._stream(events)):
            blob, usage = GeminiProvider().complete_structured(
                system='s', user='u', schema={'type': 'object'},
                on_progress=lambda sections, questions: seen.append((sections, questions)),
            )

        self.assertEqual(blob, json.loads(text))
        self.assertEqual(usage.input_tokens, 11)
        self.assertEqual(usage.output_tokens, 22)
        self.assertEqual(usage.thinking_tokens, 27)
        self.assertEqual(seen, [(1, 1)])

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='low')
    def test_streaming_endpoint_is_used_only_with_a_callback(self):
        """
        GIVEN a call with no progress callback
        WHEN generation runs
        THEN the blocking endpoint is used, so a caller that wants no progress
             pays nothing for the streaming path
        """
        from survey.ai.client import GeminiProvider

        response = mock.MagicMock()
        response.status_code = 200
        response.json.return_value = {
            'usageMetadata': {'promptTokenCount': 1, 'candidatesTokenCount': 2,
                              'totalTokenCount': 3},
            'candidates': [{'finishReason': 'STOP',
                            'content': {'parts': [{'text': self._blob_text()}]}}],
        }

        with patch('requests.post', return_value=response) as post:
            GeminiProvider().complete_structured(
                system='s', user='u', schema={'type': 'object'},
            )

        self.assertIn(':generateContent', post.call_args.args[0])
        self.assertNotIn('streamGenerateContent', post.call_args.args[0])

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='low')
    def test_a_raising_callback_does_not_fail_the_draft(self):
        """
        GIVEN a progress callback that raises every time it is called
        WHEN generation runs
        THEN the draft still comes back, because progress reporting is strictly
             less important than the draft it describes
        """
        from survey.ai.client import GeminiProvider

        text = self._blob_text()
        events = [self._chunk(text),
                  self._chunk('', finish_reason='STOP', usage={'promptTokenCount': 1})]

        def explode(sections, questions):
            raise RuntimeError('progress store is down')

        with patch('requests.post', return_value=self._stream(events)):
            blob, _ = GeminiProvider().complete_structured(
                system='s', user='u', schema={'type': 'object'}, on_progress=explode,
            )

        self.assertEqual(blob, json.loads(text))

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='low')
    def test_truncation_still_raises_with_its_usage(self):
        """
        GIVEN a stream whose final chunk reports the token ceiling
        WHEN generation runs
        THEN TruncatedOutput is raised carrying the usage, exactly as unstreamed
        """
        from survey.ai.client import GeminiProvider, TruncatedOutput

        events = [self._chunk('{"sections": ['),
                  self._chunk('', finish_reason='MAX_TOKENS',
                              usage={'candidatesTokenCount': 64000})]

        with patch('requests.post', return_value=self._stream(events)):
            with self.assertRaises(TruncatedOutput) as raised:
                GeminiProvider().complete_structured(
                    system='s', user='u', schema={'type': 'object'},
                    on_progress=lambda s, q: None,
                )

        self.assertEqual(raised.exception.usage.output_tokens, 64000)

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='low')
    def test_cyrillic_content_survives_the_stream(self):
        """
        GIVEN a streamed draft whose text is Russian, arriving as UTF-8 bytes
        WHEN the provider assembles it
        THEN the parsed blob carries the exact Cyrillic text — the regression
             that killed every Russian draft on 2026-08-17, when the stream was
             decoded with requests' ISO-8859-1 fallback instead of the UTF-8
             that SSE specifies
        """
        from survey.ai.client import GeminiProvider

        text = ('{"sections": [{"title": {"ru": "Ваш опыт вечерних прогулок"}, '
                '"subheading": {"ru": "Тёмное время — расскажите"}, '
                '"questions": [{"name": "q1"}]}]}')
        events = [
            self._chunk(text[:60]),
            self._chunk(text[60:]),
            self._chunk('', finish_reason='STOP',
                        usage={'promptTokenCount': 1, 'candidatesTokenCount': 2,
                               'totalTokenCount': 3}),
        ]
        seen = []

        with patch('requests.post', return_value=self._stream(events)):
            blob, _ = GeminiProvider().complete_structured(
                system='s', user='u', schema={'type': 'object'},
                on_progress=lambda s, q: seen.append((s, q)),
            )

        self.assertEqual(blob['sections'][0]['title']['ru'], 'Ваш опыт вечерних прогулок')
        self.assertEqual(seen, [(1, 1)])

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='low',
                       AI_REQUEST_TIMEOUT_SECONDS=120)
    def test_stream_cannot_outlive_the_total_budget(self):
        """
        GIVEN a stream still trickling data past the total time budget
        WHEN the next line arrives
        THEN the call is abandoned as a transient error — a trickle resets the
             read timeout forever, which is how 2026-08-17's stall ran until
             Celery's soft limit killed the task
        """
        from survey.ai.client import GeminiProvider, ProviderError

        events = [self._chunk('{"sections": [')]

        with patch('requests.post', return_value=self._stream(events)):
            with patch('survey.ai.client.time.monotonic',
                       side_effect=[0, 0] + [999] * 10):
                with self.assertRaises(ProviderError) as raised:
                    GeminiProvider().complete_structured(
                        system='s', user='u', schema={'type': 'object'},
                        on_progress=lambda s, q: None,
                    )

        self.assertTrue(raised.exception.transient)
        self.assertIn('exceeded', str(raised.exception))

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='low',
                       AI_REQUEST_TIMEOUT_SECONDS=120, AI_STREAM_STALL_SECONDS=30)
    def test_streamed_read_timeout_is_the_stall_limit(self):
        """
        GIVEN a streamed call and a blocking call
        WHEN each posts to the provider
        THEN the streamed one uses the stall limit as its read timeout and the
             blocking one keeps the full budget — requests restarts the read
             timer per chunk, so the full budget cannot bound silence there
        """
        from survey.ai.client import GeminiProvider

        text = self._blob_text()
        events = [self._chunk(text),
                  self._chunk('', finish_reason='STOP', usage={'promptTokenCount': 1})]

        with patch('requests.post', return_value=self._stream(events)) as post:
            GeminiProvider().complete_structured(
                system='s', user='u', schema={'type': 'object'},
                on_progress=lambda s, q: None,
            )
        self.assertEqual(post.call_args.kwargs['timeout'], 30)

        blocking = mock.MagicMock()
        blocking.status_code = 200
        blocking.json.return_value = {
            'usageMetadata': {'promptTokenCount': 1},
            'candidates': [{'finishReason': 'STOP',
                            'content': {'parts': [{'text': text}]}}],
        }
        with patch('requests.post', return_value=blocking) as post:
            GeminiProvider().complete_structured(
                system='s', user='u', schema={'type': 'object'},
            )
        self.assertEqual(post.call_args.kwargs['timeout'], 120)

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='low')
    def test_stream_cut_short_is_not_mistaken_for_a_complete_answer(self):
        """
        GIVEN a stream that stops mid-JSON without ever reporting a finish reason
        WHEN the call is made
        THEN it raises a transient ProviderError rather than handing the partial
             text to the parser — the regression that reached production on
             2026-08-17 and surfaced to creators as an unreachable AI service
        """
        from survey.ai.client import GeminiProvider, ProviderError

        events = [self._chunk('{"sections": [{"title": {"en": "Half a dr')]

        with patch('requests.post', return_value=self._stream(events)):
            with self.assertRaises(ProviderError) as raised:
                GeminiProvider().complete_structured(
                    system='s', user='u', schema={'type': 'object'},
                    on_progress=lambda s, q: None,
                )

        self.assertTrue(raised.exception.transient)
        self.assertNotIn('unparseable', str(raised.exception))

    @override_settings(GEMINI_API_KEY='k', AI_THINKING_LEVEL='low')
    def test_mid_stream_failure_is_a_provider_error(self):
        """
        GIVEN a stream that dies after headers were already accepted
        WHEN generation runs
        THEN it surfaces as ProviderError, landing on the same outcome any other
             provider failure does
        """
        import requests

        from survey.ai.client import GeminiProvider, ProviderError

        response = mock.MagicMock()
        response.status_code = 200
        response.iter_lines.side_effect = requests.RequestException('connection reset')

        with patch('requests.post', return_value=response):
            with self.assertRaises(ProviderError):
                GeminiProvider().complete_structured(
                    system='s', user='u', schema={'type': 'object'},
                    on_progress=lambda s, q: None,
                )


class AITransientRetryTest(_AIGenerationFixture, TestCase):
    """A provider having a bad second must not become the creator's dead end."""

    def setUp(self):
        super().setUp()
        # The waits are real seconds in production and pure delay in a test.
        sleep = patch('survey.ai.generation.time.sleep')
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def test_overload_is_ridden_out(self):
        """
        GIVEN a provider that returns 503 twice and then succeeds
        WHEN generation runs
        THEN the creator gets their survey, never seeing the failures
        """
        from survey.ai.client import ProviderError

        provider = _FlakyProvider(
            [_ai_blob(('en',))],
            ProviderError('API error 503: high demand', transient=True),
            failures=2,
        )

        event = self._run(provider)

        self.assertEqual(event.outcome, 'success')
        self.assertIsNotNone(event.created_survey_id)
        self.assertEqual(provider.attempts_made, 3)

    def test_malformed_reply_is_ridden_out(self):
        """
        GIVEN a provider whose first reply does not parse and whose second does
        WHEN generation runs
        THEN the draft still lands, because a garbled payload is the provider
             stumbling rather than an answer to the creator's brief
        """
        from survey.ai.client import ProviderError

        provider = _FlakyProvider(
            [_ai_blob(('en',))],
            ProviderError('unparseable model output: Expecting value', transient=True),
            failures=1,
        )

        event = self._run(provider)

        self.assertEqual(event.outcome, 'success')

    def test_every_retry_is_counted_as_waiting(self):
        """
        GIVEN a provider that is transiently broken for the whole budget
        WHEN generation gives up
        THEN the event records every call made, so the wait the creator sat
             through is visible rather than reported as a single failure
        """
        from survey.ai.client import ProviderError
        from survey.ai.generation import TRANSIENT_BACKOFF_SECONDS

        provider = _FlakyProvider(
            [], ProviderError('API error 503: high demand', transient=True), failures=99,
        )

        event = self._run(provider)

        self.assertEqual(event.outcome, 'provider_error')
        self.assertEqual(provider.attempts_made, len(TRANSIENT_BACKOFF_SECONDS) + 1)
        self.assertEqual(event.attempts, len(TRANSIENT_BACKOFF_SECONDS) + 1)
        self.assertEqual(self.sleep.call_count, len(TRANSIENT_BACKOFF_SECONDS))

    def test_backoff_grows_between_retries(self):
        """
        GIVEN a provider that stays overloaded
        WHEN the retries run
        THEN each wait is longer than the last, so a struggling provider is not
             hammered at a fixed rate
        """
        from survey.ai.client import ProviderError
        from survey.ai.generation import TRANSIENT_BACKOFF_SECONDS

        provider = _FlakyProvider(
            [], ProviderError('API error 503', transient=True), failures=99,
        )

        self._run(provider)

        waited = [call.args[0] for call in self.sleep.call_args_list]
        self.assertEqual(waited, list(TRANSIENT_BACKOFF_SECONDS))
        self.assertEqual(waited, sorted(waited))

    @override_settings(AI_STREAMING_ENABLED=False)
    def test_streaming_can_be_switched_off_without_a_deploy(self):
        """
        GIVEN the streaming kill switch turned off
        WHEN generation runs
        THEN no progress callback is passed, so the provider takes the blocking
             path and the draft still lands
        """
        provider = _ProgressingProvider([_ai_blob(('en',))], [(1, 2)])

        event = self._run(provider)

        self.assertEqual(event.outcome, 'success')
        self.assertIsNone(event.sections_drafted)

    def test_a_verdict_is_not_retried(self):
        """
        GIVEN a failure the provider will repeat — a rejected key, say
        WHEN generation runs
        THEN it is reported once, because spending the creator's wait twice
             arrives at the same message
        """
        from survey.ai.client import ProviderError

        provider = _FlakyProvider(
            [], ProviderError('API error 401: invalid key'), failures=99,
        )

        event = self._run(provider)

        self.assertEqual(event.outcome, 'provider_error')
        self.assertEqual(provider.attempts_made, 1)
        self.assertFalse(self.sleep.called)

    def test_transient_retries_do_not_spend_the_validation_budget(self):
        """
        GIVEN a provider that is overloaded once and then returns an invalid draft
        WHEN generation runs
        THEN the invalid draft still gets its own retry, because riding out a
             503 must not consume the attempt a bad draft needed
        """
        from survey.ai.client import ProviderError

        bad = _ai_blob(('en',))
        bad['sections'] = bad['sections'][:1]
        provider = _FlakyProvider(
            [bad, _ai_blob(('en',))],
            ProviderError('API error 503', transient=True),
            failures=1,
        )

        event = self._run(provider)

        self.assertEqual(event.outcome, 'success')
        self.assertEqual(provider.attempts_made, 3)


# Explicit rather than relying on the default, because the default is now OFF:
# these tests exercise what the streamed path records when it is switched on.
@override_settings(AI_STREAMING_ENABLED=True)
class AIGenerationProgressRecordingTest(_AIGenerationFixture, TestCase):
    """Progress reaches the row the poller reads, and a retry restarts it."""

    def test_counts_are_recorded_as_the_draft_grows(self):
        """
        GIVEN a provider that reports progress while generating
        WHEN generation runs
        THEN the event row carries the counts a poll would have read
        """
        blob = _ai_blob(('en',))
        provider = _ProgressingProvider([blob], [(1, 2), (2, 5)])

        event = self._run(provider)

        self.assertEqual(event.outcome, 'success')
        recorded = AIGenerationEvent.objects.get(pk=event.pk)
        self.assertEqual(recorded.sections_drafted, 2)
        self.assertEqual(recorded.questions_drafted, 5)

    def test_retry_restarts_the_counts(self):
        """
        GIVEN a first attempt that drafted sections and was then rejected
        WHEN the second attempt begins
        THEN the stored counts are cleared, so the counter does not jump
             backwards when the replacement draft's first section closes
        """
        bad = _ai_blob(('en',))
        bad['sections'] = bad['sections'][:1]
        provider = _ProgressingProvider([bad, _ai_blob(('en',))], [(4, 9)], progress_on_first_only=True)

        event = self._run(provider)

        self.assertEqual(event.outcome, 'success')
        recorded = AIGenerationEvent.objects.get(pk=event.pk)
        self.assertIsNone(recorded.sections_drafted)

    def test_progress_cannot_resurrect_a_finished_generation(self):
        """
        GIVEN a progress callback invoked after the outcome was already written
        WHEN it fires
        THEN the row is not touched, because the update is filtered on pending
        """
        from survey.ai.generation import _progress_recorder

        event = AIGenerationEvent.objects.create(
            kind='survey_draft', user=self.user, organization=self.org, outcome='success',
        )

        _progress_recorder(event)(3, 7)

        event.refresh_from_db()
        self.assertIsNone(event.sections_drafted)


class AIGenerationProgressPollingTest(TestCase):
    """The status endpoint reports news, and stays silent otherwise."""

    def setUp(self):
        self.org = _make_org('AIPollOrg')
        self.user = User.objects.create_user('aipolluser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.force_login(self.user)
        self.event = AIGenerationEvent.objects.create(
            kind='survey_draft', user=self.user, organization=self.org, outcome='pending',
        )
        self.url = reverse('editor_generation_status', kwargs={'event_id': self.event.pk})

    def test_nothing_drafted_yet_leaves_the_page_alone(self):
        """
        GIVEN a pending event with no counts recorded
        WHEN the status endpoint is polled
        THEN it answers 204, so the waiting card is never re-rendered and no
             zero is shown that would read as a stall
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 204)

    def test_advanced_counts_return_a_fragment(self):
        """
        GIVEN stored counts ahead of what the poller reports having
        WHEN the status endpoint is polled
        THEN the fragment carries the current counts
        """
        AIGenerationEvent.objects.filter(pk=self.event.pk).update(
            sections_drafted=3, questions_drafted=8)

        response = self.client.get(self.url, {'sections': 1, 'questions': 4})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '8 questions')
        self.assertContains(response, '3 sections')

    def test_fragment_has_no_percentage_label(self):
        """
        GIVEN any progress fragment
        WHEN it is rendered
        THEN no percentage text reaches the creator — the width is styling, and
             a printed "45%" would claim precision the denominator does not have
        """
        AIGenerationEvent.objects.filter(pk=self.event.pk).update(
            sections_drafted=1, questions_drafted=4)

        response = self.client.get(self.url, {'sections': 0, 'questions': 0})

        visible = re.sub(r'<[^>]*>', '', response.content.decode())
        self.assertNotIn('%', visible)

    def test_first_question_shows_before_any_section_closes(self):
        """
        GIVEN one question drafted and no section closed yet
        WHEN the status endpoint is polled
        THEN the fragment appears — gating on sections kept the counter blank
             for most of the wait, observed live on 2026-08-17
        """
        AIGenerationEvent.objects.filter(pk=self.event.pk).update(
            sections_drafted=0, questions_drafted=1)

        response = self.client.get(self.url, {'sections': 0, 'questions': 0})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1 question drafted')
        # The data-sections attribute may carry a 0, but no visible "0 sections"
        # line should reach the creator's eyes.
        self.assertNotContains(response, '0 sections')

    def test_unchanged_counts_return_no_content(self):
        """
        GIVEN stored counts the poller already has
        WHEN the status endpoint is polled
        THEN it answers 204 rather than re-sending what is already on screen
        """
        AIGenerationEvent.objects.filter(pk=self.event.pk).update(
            sections_drafted=3, questions_drafted=8)

        response = self.client.get(self.url, {'sections': 3, 'questions': 8})

        self.assertEqual(response.status_code, 204)

    def test_malformed_client_count_is_tolerated(self):
        """
        GIVEN a junk `sections` parameter
        WHEN the status endpoint is polled
        THEN it answers with the fragment rather than a 400: the value is a hint
             about what the browser rendered, not a permission
        """
        AIGenerationEvent.objects.filter(pk=self.event.pk).update(sections_drafted=2)

        response = self.client.get(self.url, {'sections': 'banana'})

        self.assertEqual(response.status_code, 200)

    def test_another_users_event_is_not_disclosed(self):
        """
        GIVEN an event belonging to a different user
        WHEN it is polled
        THEN the request is rejected and no progress is disclosed
        """
        other = User.objects.create_user('aipollother', password='pass')
        other_org = _make_org('AIPollOther')
        Membership.objects.create(user=other, organization=other_org, role='owner')
        self.client.force_login(other)

        response = self.client.get(self.url, {'sections': 0})

        self.assertIn(response.status_code, (403, 404))


class AILLMAnalyticsEmissionTest(_AIGenerationFixture, TestCase):
    """The generator on PostHog's LLM dashboards — numbers, never content."""

    def _captured(self, emit_mock, name):
        return [c for c in emit_mock.call_args_list if c.args and c.args[0] == name]

    def test_success_emits_billing_accurate_generation_event(self):
        """
        GIVEN a successful generation with output and reasoning tokens
        WHEN the terminal events are emitted
        THEN one $ai_generation carries output+reasoning as the output count
             (Gemini bills thinking at the output rate, and the computed cost
             must equal the invoice), latency in seconds, and the row's trace id
        """
        provider = _FakeProvider(
            [_ai_blob(('en',))],
            usages=[{'latency_ms': 8000, 'input_tokens': 1300,
                     'output_tokens': 1000, 'thinking_tokens': 500}],
        )

        with patch('posthog.capture') as capture, patch('posthog.disabled', False):
            event = self._run(provider)

        calls = self._captured(capture, '$ai_generation')
        self.assertEqual(len(calls), 1)
        props = calls[0].kwargs['properties']
        self.assertEqual(props['$ai_trace_id'], 'survey-draft-%s' % event.pk)
        self.assertEqual(props['$ai_input_tokens'], 1300)
        self.assertEqual(props['$ai_output_tokens'], 1500)
        self.assertEqual(props['thinking_tokens'], 500)
        self.assertEqual(props['$ai_latency'], 8.0)
        self.assertEqual(props['$ai_provider'], 'fake')
        self.assertNotIn('$ai_is_error', props)

    def test_no_content_ever_reaches_the_event(self):
        """
        GIVEN any emitted $ai_generation
        WHEN its properties are inspected
        THEN neither the brief nor the draft is among them — the creator's
             project description is not ours to ship to an analytics vendor
        """
        provider = _FakeProvider([_ai_blob(('en',))])

        with patch('posthog.capture') as capture, patch('posthog.disabled', False):
            self._run(provider)

        props = self._captured(capture, '$ai_generation')[0].kwargs['properties']
        dumped = str(props)
        self.assertNotIn('$ai_input', props)
        self.assertNotIn('$ai_output_choices', props)
        self.assertNotIn('Where is traffic worst', dumped)

    def test_failure_emits_flagged_without_the_error_message(self):
        """
        GIVEN a generation that ends in provider_error
        WHEN the terminal events are emitted
        THEN $ai_generation is flagged with the outcome slug only — provider
             messages have quoted model output, and model output can quote the
             brief
        """
        from survey.ai.client import ProviderError

        provider = _FakeProvider([], error=ProviderError('API error 503: brief-ish detail'))

        with patch('posthog.capture') as capture, patch('posthog.disabled', False):
            self._run(provider)

        props = self._captured(capture, '$ai_generation')[0].kwargs['properties']
        self.assertTrue(props['$ai_is_error'])
        self.assertEqual(props['$ai_error'], 'provider_error')
        self.assertNotIn('brief-ish', str(props))


class AIDraftFeedbackStripTest(_AIGenerationFixture, TestCase):
    """The one-shot verdict prompt: only for the right person, right draft."""

    def _open_editor(self, survey, draft_param):
        self.client.force_login(self.user)
        url = reverse('editor_survey_detail', kwargs={'survey_uuid': survey.uuid})
        return self.client.get(url, {'draft': draft_param})

    @override_settings(POSTHOG_PROJECT_KEY='phc_test')
    def test_redirect_carries_the_draft_parameter(self):
        """
        GIVEN a successful generation being polled
        WHEN the success redirect is issued
        THEN it carries ?draft=<event id>, the only source of the prompt
        """
        provider = _FakeProvider([_ai_blob(('en',))])
        event = self._run(provider)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('editor_generation_status', kwargs={'event_id': event.pk}))

        self.assertEqual(
            response['HX-Redirect'],
            '%s?draft=%d' % (
                reverse('editor_survey_detail',
                        kwargs={'survey_uuid': event.created_survey.uuid}),
                event.pk,
            ))

    @override_settings(POSTHOG_PROJECT_KEY='phc_test')
    def test_legitimate_arrival_gets_the_strip(self):
        """
        GIVEN the creator arriving via their own generation's redirect
        WHEN the editor renders
        THEN the strip is present and carries the generation's trace id
        """
        provider = _FakeProvider([_ai_blob(('en',))])
        event = self._run(provider)

        response = self._open_editor(event.created_survey, event.pk)

        self.assertContains(response, 'ai-feedback-strip')
        self.assertContains(response, 'survey-draft-%s' % event.pk)

    @override_settings(POSTHOG_PROJECT_KEY='phc_test')
    def test_foreign_or_mismatched_draft_conjures_nothing(self):
        """
        GIVEN a draft parameter naming another user's event, or one that did
              not produce this survey
        WHEN the editor renders
        THEN no strip appears — an unvalidated id must not conjure UI
        """
        provider = _FakeProvider([_ai_blob(('en',))])
        event = self._run(provider)
        other = AIGenerationEvent.objects.create(
            kind='survey_draft',
            user=User.objects.create_user('someone-else', password='x'),
            organization=self.org, outcome='success',
        )

        self.assertNotContains(
            self._open_editor(event.created_survey, other.pk), 'ai-feedback-strip')
        self.assertNotContains(
            self._open_editor(event.created_survey, 999999), 'ai-feedback-strip')

    @override_settings(POSTHOG_PROJECT_KEY='phc_test')
    def test_manual_arrival_never_asks(self):
        """
        GIVEN the editor opened without the generation redirect's parameter
        WHEN it renders
        THEN no strip appears — manual surveys have no draft to judge
        """
        provider = _FakeProvider([_ai_blob(('en',))])
        event = self._run(provider)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('editor_survey_detail',
                    kwargs={'survey_uuid': event.created_survey.uuid}))

        self.assertNotContains(response, 'ai-feedback-strip')

    @override_settings(POSTHOG_PROJECT_KEY='')
    def test_no_posthog_means_no_strip(self):
        """
        GIVEN PostHog unconfigured
        WHEN the creator arrives via the generation redirect
        THEN no strip appears — the vote would have nowhere to go
        """
        provider = _FakeProvider([_ai_blob(('en',))])
        event = self._run(provider)

        response = self._open_editor(event.created_survey, event.pk)

        self.assertNotContains(response, 'ai-feedback-strip')


class AISurveyCreateViewTest(TestCase):
    """The create page: manual path untouched, AI path gated and asynchronous."""

    def setUp(self):
        self.org = _make_org('AIViewOrg')
        self.user = User.objects.create_user('aiviewuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='aiviewuser', password='pass')

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='', GEMINI_API_KEY='')
    def test_panel_is_absent_when_provider_unconfigured(self):
        """
        GIVEN no provider credentials
        WHEN the create page is opened
        THEN no AI panel is rendered and only manual creation is offered
        """
        response = self.client.get(reverse('editor_survey_create'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Generate draft')

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    @override_settings(MOBILE_EDITOR_NAV=False)
    def test_panel_is_present_when_provider_configured(self):
        """
        GIVEN configured provider credentials
        WHEN the create page is opened
        THEN the brief panel and the privacy notice are rendered
        """
        response = self.client.get(reverse('editor_survey_create'))

        self.assertContains(response, 'Generate draft')
        self.assertContains(response, 'never sent to AI providers')

    def test_manual_creation_is_unchanged(self):
        """
        GIVEN the manual action
        WHEN the create form is submitted
        THEN a survey with one head section is created and the user is redirected
        """
        response = self.client.post(reverse('editor_survey_create'), {
            'name': 'manual_survey', 'available_languages': '["en"]', 'action': 'empty',
        })

        survey = SurveyHeader.objects.get(name='manual_survey')
        self.assertRedirects(
            response, reverse('editor_survey_detail', kwargs={'survey_uuid': survey.uuid}),
        )
        self.assertEqual(
            SurveySection.objects.filter(survey_header=survey, is_head=True).count(), 1,
        )

    def test_legacy_post_without_action_still_creates_manually(self):
        """
        GIVEN a POST that predates the action parameter
        WHEN it reaches the create view
        THEN the manual path runs exactly as before
        """
        response = self.client.post(reverse('editor_survey_create'), {
            'name': 'legacy_survey', 'available_languages': '["en"]',
        })

        self.assertTrue(SurveyHeader.objects.filter(name='legacy_survey').exists())
        self.assertEqual(response.status_code, 302)

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_generate_enqueues_a_task_and_returns_the_poller(self):
        """
        GIVEN a filled brief and a configured provider
        WHEN the generate action is submitted
        THEN a pending event is created, a task is enqueued, and the poller is returned
        """
        with patch('survey.editor_views.generate_survey_draft_task.delay') as delay:
            response = self.client.post(reverse('editor_survey_create'), {
                'name': 'ai_survey', 'available_languages': '["en"]',
                'action': 'generate', 'goal': 'Where is traffic worst',
                'use_case': 'urban_planning',
            })

        event = AIGenerationEvent.objects.get(user=self.user)
        self.assertEqual(event.outcome, 'pending')
        self.assertEqual(event.brief['goal'], 'Where is traffic worst')
        delay.assert_called_once()
        # The POST is what puts the overlay and its poller on the page.
        self.assertContains(response, 'Building your survey')
        self.assertContains(response, 'hx-trigger')

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_map_touched_locks_the_position_for_the_task(self):
        """
        GIVEN the create page posted map_touched=1 (the creator framed the map)
        WHEN the generate action is submitted
        THEN the task is told the map is locked; without the flag it is not
        """
        base = {
            'name': 'ai_survey', 'available_languages': '["en"]',
            'action': 'generate', 'goal': 'Where is traffic worst',
            'use_case': 'urban_planning',
        }
        with patch('survey.editor_views.generate_survey_draft_task.delay') as delay:
            self.client.post(reverse('editor_survey_create'), dict(base, map_touched='1'))
            self.assertTrue(delay.call_args.kwargs['map_locked'])
        with patch('survey.editor_views.generate_survey_draft_task.delay') as delay:
            self.client.post(reverse('editor_survey_create'), base)
            self.assertFalse(delay.call_args.kwargs['map_locked'])

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_create_page_ships_the_map_touched_field(self):
        """
        GIVEN the create page
        WHEN it renders
        THEN the hidden map_touched field is present and empty, so an untouched
             map is reported as untouched
        """
        response = self.client.get(reverse('editor_survey_create'))
        self.assertContains(response, 'name="map_touched" id="create-map-touched" value=""')

    # The decorator is load-bearing: without it the test only passes on a
    # machine whose .env happens to hold a real provider key (run_tests.sh
    # exports .env), because an unconfigured provider returns the
    # not-configured fragment instead of the waiting card. It shipped without
    # one and failed on the first checkout that lacked a key.
    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_waiting_card_opens_with_quips_and_elapsed(self):
        """
        GIVEN a generate submission that succeeds in enqueueing
        WHEN the waiting card is returned
        THEN it carries the rotating quips and the ticking elapsed counter, and
             no trace of the removed progress bar
        """
        with patch('survey.editor_views.generate_survey_draft_task.delay'):
            response = self.client.post(reverse('editor_survey_create'), {
                'name': 'ai_survey', 'available_languages': '["en"]',
                'action': 'generate', 'goal': 'Where is traffic worst',
                'use_case': 'urban_planning',
            })

        self.assertContains(response, 'gen-quip')
        self.assertContains(response, 'gen-elapsed')
        self.assertNotContains(response, 'gen-bar')

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_generate_without_a_goal_redisplays_the_form(self):
        """
        GIVEN a generate submission with an empty goal
        WHEN it is posted
        THEN the form is re-rendered and no event or task is created
        """
        with patch('survey.editor_views.generate_survey_draft_task.delay') as delay:
            response = self.client.post(reverse('editor_survey_create'), {
                'name': 'ai_survey', 'available_languages': '["en"]',
                'action': 'generate', 'goal': '',
            })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(AIGenerationEvent.objects.exists())
        delay.assert_not_called()
        # A fragment, not the page: this is swapped into a div inside the form
        # the creator is still looking at, so a full page would duplicate every
        # id and re-run the Leaflet setup against an initialised map.
        self.assertNotContains(response, '<html')
        self.assertNotContains(response, 'create-map-picker')
        self.assertContains(response, 'Check the form before generating')

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_invalid_generate_carries_field_error_payload(self):
        """
        GIVEN a generate submission with an empty goal
        WHEN the invalid fragment is returned
        THEN it embeds a JSON payload anchoring the error to the goal field's
             rendered id, and reports zero unanchored errors, so the page
             script can mark the field in place and hide the detached card
        """
        with patch('survey.editor_views.generate_survey_draft_task.delay'):
            response = self.client.post(reverse('editor_survey_create'), {
                'name': 'ai_survey', 'available_languages': '["en"]',
                'action': 'generate', 'goal': '',
            })

        self.assertContains(response, 'id="gen-field-errors"')
        payload = re.search(
            r'<script id="gen-field-errors" type="application/json">(.*?)</script>',
            response.content.decode(), re.S)
        self.assertIsNotNone(payload)
        field_errors = json.loads(payload.group(1))
        self.assertEqual([fe['field_id'] for fe in field_errors], ['id_goal'])
        self.assertTrue(field_errors[0]['messages'])
        self.assertContains(response, 'data-unanchored="0"')
        # The anchor must match an input the create page actually renders.
        page = self.client.get(reverse('editor_survey_create')).content.decode()
        self.assertIn('id="id_goal"', page)

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='')
    def test_not_configured_card_has_no_field_payload(self):
        """
        GIVEN a generate submission while the provider key is empty
        WHEN the not-configured fragment is returned
        THEN the plain card renders without a field-error payload
        """
        response = self.client.post(reverse('editor_survey_create'), {
            'name': 'ai_survey', 'available_languages': '["en"]',
            'action': 'generate', 'goal': 'Where is traffic worst',
        })

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'gen-field-errors')

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_wizard_draft_button_signals_a_next_step(self):
        """
        GIVEN the create page renders the mobile wizard's step-1 draft button
        WHEN the markup is inspected
        THEN the button says a next step follows instead of implying the
             survey is created immediately
        """
        response = self.client.get(reverse('editor_survey_create'))
        html = response.content.decode()

        # The wizard step-1 button advances to the map step; only the desktop
        # #generate-btn (which really does submit) may keep "Draft my survey".
        wizard_btn = re.search(r'<button[^>]*wizard-draft-next[^>]*>(.*?)</button>', html, re.S)
        self.assertIsNotNone(wizard_btn)
        self.assertIn('Next — choose the place', wizard_btn.group(1))
        self.assertNotIn('Draft my survey', wizard_btn.group(1))

    # The two tests below guard the same defect from both sides. It is worth
    # saying why the obvious one is not enough: `test_manual_creation_is_unchanged`
    # above passed throughout the whole time "Create empty" was dead in
    # production, because the test client posts straight to the view and never
    # runs browser validation. The bug lived entirely in the rendered HTML, so
    # only an assertion about the markup can catch it coming back.
    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_brief_fields_carry_no_html5_required(self):
        """
        GIVEN the AI panel is rendered
        WHEN the create page markup is inspected
        THEN no brief field carries `required`, because the panel shares one
             form with the "Create empty" submit and the browser validates the
             whole form -- while the survey name keeps its own `required`
        """
        response = self.client.get(reverse('editor_survey_create'))
        html = response.content.decode()

        for field_id in ('id_goal', 'id_audience', 'id_map_target'):
            tag = re.search(r'<[^>]*id="%s"[^>]*>' % field_id, html)
            self.assertIsNotNone(tag, 'brief field %s is not rendered' % field_id)
            self.assertNotIn('required', tag.group(0))

        name_tag = re.search(r'<[^>]*id="id_name"[^>]*>', html)
        self.assertIn('required', name_tag.group(0))

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_create_empty_works_with_an_untouched_brief(self):
        """
        GIVEN the AI panel is present and every brief field is left blank
        WHEN "Create empty" is submitted
        THEN the survey is created with its head section, exactly as when the
             panel is absent -- declining AI costs the creator nothing
        """
        response = self.client.post(reverse('editor_survey_create'), {
            'name': 'declined_ai', 'available_languages': '["en"]', 'action': 'empty',
            'goal': '', 'audience': '', 'map_target': '',
        })

        survey = SurveyHeader.objects.get(name='declined_ai')
        self.assertRedirects(
            response, reverse('editor_survey_detail', kwargs={'survey_uuid': survey.uuid}),
        )
        self.assertEqual(
            SurveySection.objects.filter(survey_header=survey, is_head=True).count(), 1,
        )
        self.assertFalse(AIGenerationEvent.objects.exists())


class AIGenerationStatusViewTest(TestCase):
    """The polled status endpoint."""

    def setUp(self):
        self.org = _make_org('AIStatusOrg')
        self.user = User.objects.create_user('aistatususer', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='aistatususer', password='pass')

    def _event(self, outcome='pending', survey=None):
        return AIGenerationEvent.objects.create(
            kind='survey_draft', user=self.user, organization=self.org,
            outcome=outcome, created_survey=survey, languages=['en'],
        )

    def test_pending_event_changes_nothing_on_the_page(self):
        """
        GIVEN a generation still running
        WHEN the status endpoint is polled
        THEN it answers 204 so the overlay is left untouched and does not flicker
        """
        event = self._event()

        response = self.client.get(
            reverse('editor_generation_status', kwargs={'event_id': event.id})
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(response.content)

    def test_success_redirects_to_the_populated_editor(self):
        """
        GIVEN a finished generation
        WHEN the status endpoint is polled
        THEN it answers with HX-Redirect to the new survey's editor
        """
        survey = SurveyHeader.objects.create(
            name='generated', organization=self.org, created_by=self.user,
        )
        event = self._event(outcome='success', survey=survey)

        response = self.client.get(
            reverse('editor_generation_status', kwargs={'event_id': event.id})
        )

        self.assertEqual(response.status_code, 204)
        # ?draft= is what entitles the arrival to the one-shot feedback prompt;
        # only this redirect ever carries it.
        self.assertEqual(
            response['HX-Redirect'],
            '%s?draft=%d' % (
                reverse('editor_survey_detail', kwargs={'survey_uuid': survey.uuid}),
                event.pk,
            ),
        )

    def test_failure_stops_polling_and_explains(self):
        """
        GIVEN a generation that failed
        WHEN the status endpoint is polled
        THEN a message is shown and the fragment no longer polls
        """
        event = self._event(outcome='provider_error')

        response = self.client.get(
            reverse('editor_generation_status', kwargs={'event_id': event.id})
        )

        # No poller in the failure fragment, so polling stops; it arrives as an
        # out-of-band swap because the poll itself no longer swaps anything.
        self.assertNotContains(response, 'hx-trigger')
        self.assertContains(response, 'hx-swap-oob')
        # The copy contains an apostrophe, which the template escapes.
        self.assertContains(response, 'The Wizard couldn')

    def test_another_users_event_is_not_visible(self):
        """
        GIVEN an event belonging to a different user
        WHEN it is polled
        THEN the request 404s — the brief is the creator's project description
        """
        other = User.objects.create_user('aiotheruser', password='pass')
        Membership.objects.create(user=other, organization=self.org, role='owner')
        event = AIGenerationEvent.objects.create(
            kind='survey_draft', user=other, organization=self.org, outcome='pending',
        )

        response = self.client.get(
            reverse('editor_generation_status', kwargs={'event_id': event.id})
        )

        self.assertEqual(response.status_code, 404)


class AIGenerationTaskTest(TestCase):
    """The Celery entry point: never leaves the poller waiting forever."""

    def setUp(self):
        self.org = _make_org('AITaskOrg')
        self.user = User.objects.create_user('aitaskuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

    def _event(self):
        return AIGenerationEvent.objects.create(
            kind='survey_draft', user=self.user, organization=self.org,
            outcome='pending', languages=['en'],
        )

    def _brief_data(self):
        return {
            'name': 'task_survey', 'goal': 'Where is traffic worst',
            'audience': '', 'map_target': '', 'use_case': 'urban_planning',
        }

    def test_task_runs_generation_end_to_end(self):
        """
        GIVEN a queued generation and a provider returning a valid draft
        WHEN the task executes
        THEN the survey is created and the event reaches a terminal outcome
        """
        from survey.ai.materialize import header_overrides_from_form
        from survey.ai.tasks import generate_survey_draft_task

        event = self._event()
        overrides = header_overrides_from_form(
            name='task_survey', languages=['en'],
            map_lat=None, map_lng=None, map_zoom=None, default_basemap=None,
        )
        provider = _FakeProvider([_ai_blob(('en',))])

        with patch('survey.ai.generation.client.get_provider', return_value=provider):
            generate_survey_draft_task(event.id, self._brief_data(), ['en'], overrides)

        event.refresh_from_db()
        self.assertEqual(event.outcome, 'success')
        self.assertTrue(SurveyHeader.objects.filter(name='task_survey').exists())

    def test_unexpected_crash_still_terminates_the_event(self):
        """
        GIVEN generation that raises something unforeseen
        WHEN the task executes
        THEN the event leaves 'pending' so the page stops polling and explains
        """
        from survey.ai.tasks import generate_survey_draft_task

        event = self._event()

        # Patched at its definition site: tasks.py imports it inside the
        # function body, so there is no module attribute to replace.
        with patch('survey.ai.generation.generate_survey_draft', side_effect=RuntimeError('boom')):
            generate_survey_draft_task(event.id, self._brief_data(), ['en'], {})

        event.refresh_from_db()
        self.assertEqual(event.outcome, 'error')
        self.assertIn('boom', event.error_detail)

    def test_missing_event_is_survivable(self):
        """
        GIVEN a task whose event row no longer exists
        WHEN it executes
        THEN it returns quietly instead of crashing the worker
        """
        from survey.ai.tasks import generate_survey_draft_task

        generate_survey_draft_task(999999, self._brief_data(), ['en'], {})


class AITruncatedOutputUsageTest(TestCase):
    """A truncated call still spent tokens — the event must say how many."""

    def setUp(self):
        self.org = _make_org('AITruncOrg')
        self.user = User.objects.create_user('aitruncuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

    def test_truncated_generation_records_every_failed_calls_usage(self):
        """
        GIVEN a provider whose every answer is cut off at the token ceiling
        WHEN generation gives up after both attempts
        THEN the event carries what the whole set spent, not one call's share:
             two truncated attempts really did burn the ceiling twice
        """
        from survey.ai.client import LLMUsage, TruncatedOutput
        from survey.ai.generation import SurveyBrief, generate_survey_draft, start_generation

        spent = LLMUsage(
            provider='fake', model='fake-model',
            input_tokens=900, output_tokens=64000, latency_ms=55000,
        )

        class _TruncatingProvider:
            def complete_structured(self, **kwargs):
                raise TruncatedOutput('output truncated at 64000 tokens', usage=spent)

        brief = SurveyBrief(
            name='truncated', goal='Everything about everything',
            audience='', map_target='', use_case='other',
        )
        event = start_generation(self.user, self.org, brief, ['en'])

        with patch('survey.ai.generation.client.get_provider', return_value=_TruncatingProvider()):
            generate_survey_draft(event, brief, ['en'], {'name': 'truncated'})

        event.refresh_from_db()
        self.assertEqual(event.outcome, 'provider_error')
        self.assertEqual(event.attempts, 2)
        self.assertEqual(event.output_tokens, 128000)
        self.assertEqual(event.input_tokens, 1800)
        self.assertEqual(event.total_latency_ms, 110000)
        # The terminal call alone, so the pre-existing column keeps meaning what
        # the rows written before the accounting existed were measured as.
        self.assertEqual(event.latency_ms, 55000)
        self.assertEqual(event.model, 'fake-model')


class GeminiProviderTest(TestCase):
    """The free-tier provider used for end-to-end testing."""

    @override_settings(AI_PROVIDER='gemini', GEMINI_API_KEY='')
    def test_missing_key_reports_not_configured(self):
        """
        GIVEN AI_PROVIDER=gemini with no key
        WHEN a provider is requested
        THEN NotConfigured is raised and the UI gate stays closed
        """
        from survey.ai import client

        self.assertFalse(client.provider_configured())
        with self.assertRaises(client.NotConfigured):
            client.get_provider()

    @override_settings(AI_PROVIDER='gemini', GEMINI_API_KEY='test-key')
    def test_configured_key_opens_the_gate(self):
        """
        GIVEN a Gemini key
        WHEN the UI asks whether AI is available
        THEN it is, without importing any vendor SDK
        """
        from survey.ai import client

        self.assertTrue(client.provider_configured())

    def test_schema_is_adapted_to_geminis_dialect(self):
        """
        GIVEN our JSON schema, which uses additionalProperties and lowercase types
        WHEN it is adapted for Gemini
        THEN additionalProperties is dropped and types are uppercased
        """
        from survey.ai.client import _to_gemini_schema
        from survey.ai.schema import survey_draft_schema

        adapted = _to_gemini_schema(survey_draft_schema(['en']))

        self.assertEqual(adapted['type'], 'OBJECT')
        self.assertNotIn('additionalProperties', adapted)
        sections = adapted['properties']['sections']
        self.assertEqual(sections['type'], 'ARRAY')
        self.assertNotIn('additionalProperties', sections['items'])
        title = sections['items']['properties']['title']
        self.assertEqual(title['type'], 'OBJECT')
        self.assertEqual(title['properties']['en']['type'], 'STRING')
        self.assertEqual(sections['items']['required'], ['title', 'subheading', 'questions'])

    @override_settings(AI_PROVIDER='gemini', GEMINI_API_KEY='test-key', GEMINI_MODEL='ghost-model')
    def test_unknown_model_says_which_setting_to_change(self):
        """
        GIVEN a model name the key cannot use
        WHEN generation is attempted
        THEN the error names GEMINI_MODEL rather than reading like an outage
        """
        from survey.ai import client

        provider = client.get_provider()
        response = mock.Mock(status_code=404, text='not found')

        with patch('requests.post', return_value=response):
            with self.assertRaises(client.ProviderError) as ctx:
                provider.complete_structured(system='s', user='u', schema={})

        self.assertIn('GEMINI_MODEL', str(ctx.exception))

    @override_settings(AI_PROVIDER='gemini', GEMINI_API_KEY='test-key')
    def test_truncated_response_carries_its_usage(self):
        """
        GIVEN a response cut off at the token ceiling
        WHEN it is parsed
        THEN TruncatedOutput carries the spent tokens so the event can record them
        """
        from survey.ai import client

        provider = client.get_provider()
        response = mock.Mock(status_code=200)
        response.json.return_value = {
            'candidates': [{'finishReason': 'MAX_TOKENS', 'content': {'parts': [{'text': '{'}]}}],
            'usageMetadata': {'promptTokenCount': 10, 'candidatesTokenCount': 4096},
        }

        with patch('requests.post', return_value=response):
            with self.assertRaises(client.TruncatedOutput) as ctx:
                provider.complete_structured(system='s', user='u', schema={})

        self.assertEqual(ctx.exception.usage.output_tokens, 4096)
        self.assertEqual(ctx.exception.usage.provider, 'gemini')

    @override_settings(AI_PROVIDER='gemini', GEMINI_API_KEY='test-key')
    def test_successful_response_is_parsed_with_usage(self):
        """
        GIVEN a well-formed Gemini response
        WHEN it is parsed
        THEN the JSON blob and the token usage both come back
        """
        from survey.ai import client

        provider = client.get_provider()
        response = mock.Mock(status_code=200)
        response.json.return_value = {
            'candidates': [{
                'finishReason': 'STOP',
                'content': {'parts': [{'text': '{"sections": []}'}]},
            }],
            'usageMetadata': {'promptTokenCount': 11, 'candidatesTokenCount': 22},
        }

        with patch('requests.post', return_value=response):
            blob, usage = provider.complete_structured(system='s', user='u', schema={})

        self.assertEqual(blob, {'sections': []})
        self.assertEqual(usage.input_tokens, 11)
        self.assertEqual(usage.output_tokens, 22)


class AIGenerationTelemetryTest(TestCase):
    """Server-side hypothesis telemetry: waited-or-left, and the draft snapshot."""

    def setUp(self):
        self.org = _make_org('AITelemetryOrg')
        self.user = User.objects.create_user('aitelemuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='aitelemuser', password='pass')

    def _event(self, outcome='pending', survey=None):
        return AIGenerationEvent.objects.create(
            kind='survey_draft', user=self.user, organization=self.org,
            outcome=outcome, created_survey=survey, languages=['en'],
        )

    def test_each_poll_stamps_last_polled_at(self):
        """
        GIVEN a pending generation
        WHEN the page polls the status endpoint
        THEN last_polled_at is stamped — its freeze marks when the creator left
        """
        event = self._event()
        self.assertIsNone(event.last_polled_at)

        self.client.get(reverse('editor_generation_status', kwargs={'event_id': event.id}))

        event.refresh_from_db()
        self.assertIsNotNone(event.last_polled_at)

    def test_redirect_stamps_redirected_at_once(self):
        """
        GIVEN a finished generation polled twice
        WHEN both polls receive the redirect
        THEN redirected_at keeps the FIRST stamp — the moment the creator waited to
        """
        survey = SurveyHeader.objects.create(
            name='telemetry_ok', organization=self.org, created_by=self.user,
        )
        event = self._event(outcome='success', survey=survey)
        url = reverse('editor_generation_status', kwargs={'event_id': event.id})

        self.client.get(url)
        event.refresh_from_db()
        first = event.redirected_at
        self.assertIsNotNone(first)

        self.client.get(url)
        event.refresh_from_db()
        self.assertEqual(event.redirected_at, first)

    def test_generated_blob_is_snapshotted_on_success(self):
        """
        GIVEN a provider returning a valid draft
        WHEN generation succeeds
        THEN the event keeps the model's blob as produced, for the edit-diff metric
        """
        from survey.ai.generation import SurveyBrief, generate_survey_draft, start_generation

        brief = SurveyBrief(
            name='telemetry_snap', goal='goal', audience='', map_target='',
            use_case='other',
        )
        event = start_generation(self.user, self.org, brief, ['en'])
        blob = _ai_blob(('en',))
        provider = _FakeProvider([blob])

        with patch('survey.ai.generation.client.get_provider', return_value=provider):
            generate_survey_draft(event, brief, ['en'], {'name': 'telemetry_snap'})

        event.refresh_from_db()
        self.assertEqual(event.outcome, 'success')
        self.assertEqual(event.generated_blob, blob)

    def test_rejected_blob_is_kept_for_prompt_iteration(self):
        """
        GIVEN a draft that fails validation twice
        WHEN generation gives up
        THEN the last rejected blob is stored next to the reasons it was rejected
        """
        from survey.ai.generation import SurveyBrief, generate_survey_draft, start_generation

        bad = _ai_blob(('en',))
        bad['sections'] = bad['sections'][:1]
        brief = SurveyBrief(
            name='telemetry_bad', goal='goal', audience='', map_target='',
            use_case='other',
        )
        event = start_generation(self.user, self.org, brief, ['en'])
        provider = _FakeProvider([bad, dict(bad)])

        with patch('survey.ai.generation.client.get_provider', return_value=provider):
            generate_survey_draft(event, brief, ['en'], {'name': 'telemetry_bad'})

        event.refresh_from_db()
        self.assertEqual(event.outcome, 'invalid_draft')
        self.assertIsNotNone(event.generated_blob)


class AIGeneratorKnowsEveryTypeTest(SimpleTestCase):
    """The generator's prompt must describe every type its schema permits.

    The schema derives its enum from INPUT_TYPE_CHOICES, so a new input type
    becomes emittable the moment it is added to the model — while the prompt,
    which is prose, keeps describing the old set. `ranking` shipped in exactly
    that state: allowed by the schema, unmentioned in the prompt, and exempt
    from the validator's "this type needs choices" rule.
    """

    def test_prompt_mentions_every_type_the_schema_allows(self):
        """
        GIVEN the input types the generation schema permits at top level
        WHEN the prompt text is searched for each one
        THEN every type is named, so the model knows it exists
        """
        from survey.ai.prompts import PLATFORM_DESCRIPTION
        from survey.ai.schema import TOP_LEVEL_INPUT_TYPES

        missing = [t for t in TOP_LEVEL_INPUT_TYPES if f'`{t}`' not in PLATFORM_DESCRIPTION]

        self.assertEqual(missing, [], f'input types absent from the prompt: {missing}')

    def test_types_whose_choices_are_their_content_are_required_to_have_them(self):
        """
        GIVEN the types whose choices carry the question's content
        WHEN the validator's requirement list is checked
        THEN each is present, so a generated draft cannot ship one empty
        """
        from survey.ai.validator import CHOICE_REQUIRED_INPUT_TYPES

        for input_type in ('choice', 'multichoice', 'range', 'rating', 'ranking'):
            self.assertIn(input_type, CHOICE_REQUIRED_INPUT_TYPES)



class CreateSteerAITest(TestCase):
    """Create-page steering toward the AI draft (openspec: steer-to-ai-generation).

    Everything here is markup-level on purpose: the intercept and the wizard
    skip live in JS the test client cannot execute, so these tests pin what the
    server ships to the browser, and the browser-driven pass covers behavior.
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Steer Org")
        self.user = User.objects.create_user('steer_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.force_login(self.user)

    def _page(self):
        return self.client.get('/editor/surveys/new/').content.decode()

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test',
                       MOBILE_EDITOR_NAV=True, CREATE_STEER_AI=False)
    def test_flag_off_restores_the_flat_panel(self):
        """
        GIVEN CREATE_STEER_AI off (the kill switch)
        WHEN the create page renders
        THEN no disclosure, no autofocus, no intercept container, and no
             wizard skip branch -- the pre-change markup exactly
        """
        html = self._page()
        self.assertNotIn('<details class="ai-more"', html)
        self.assertNotIn('id="ai-intercept"', html)
        self.assertNotIn('id="example-chips"', html)
        self.assertNotIn("if (p === 'empty')", html)
        goal_tag = re.search(r'<[^>]*id="id_goal"[^>]*>', html)
        self.assertNotIn('autofocus', goal_tag.group(0))

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test',
                       MOBILE_EDITOR_NAV=True, CREATE_STEER_AI=True)
    def test_flag_on_collapses_the_brief_to_one_field(self):
        """
        GIVEN CREATE_STEER_AI on and an untouched brief
        WHEN the create page renders
        THEN the steering fields sit in a closed "Add details" disclosure, the
             goal takes autofocus, and the intercept container is shipped hidden
        """
        html = self._page()
        details = re.search(r'<details class="ai-more"[^>]*>', html)
        self.assertIsNotNone(details)
        self.assertNotIn(' open', details.group(0))
        self.assertIn('Add details (optional)', html)
        self.assertIn('id="ai-intercept"', html)
        self.assertIn('id="example-chips"', html)
        self.assertIn('Try an example:', html)
        self.assertIn("if (p === 'empty')", html)
        goal_tag = re.search(r'<[^>]*id="id_goal"[^>]*>', html)
        self.assertIn('autofocus', goal_tag.group(0))

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test',
                       MOBILE_EDITOR_NAV=False, CREATE_STEER_AI=True)
    def test_no_autofocus_while_the_name_field_is_visible(self):
        """
        GIVEN the wizard flag off, so the name input keeps first position
        WHEN the create page renders with steering on
        THEN the goal does NOT carry autofocus (focus stays uncontested)
        """
        goal_tag = re.search(r'<[^>]*id="id_goal"[^>]*>', self._page())
        self.assertNotIn('autofocus', goal_tag.group(0))

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test',
                       MOBILE_EDITOR_NAV=True, CREATE_STEER_AI=True)
    def test_disclosure_reopens_for_dirty_fields(self):
        """
        GIVEN an invalid manual POST that carried an audience value
        WHEN the page re-renders
        THEN the disclosure is rendered open and the typed value survives
        """
        html = self.client.post('/editor/surveys/new/', {
            'name': '', 'available_languages': '["en"]', 'action': 'empty',
            'goal': 'Parks in Berlin', 'audience': 'Residents of Pankow',
        }).content.decode()
        details = re.search(r'<details class="ai-more"[^>]*>', html)
        self.assertIn(' open', details.group(0))
        self.assertIn('Residents of Pankow', html)
        self.assertIn('Parks in Berlin', html)

    @override_settings(AI_PROVIDER='', MOBILE_EDITOR_NAV=True, CREATE_STEER_AI=True)
    def test_no_provider_means_no_intercept(self):
        """
        GIVEN no configured LLM provider
        WHEN the create page renders with steering on
        THEN the intercept container is not shipped -- there is nothing to offer
        """
        self.assertNotIn('id="ai-intercept"', self._page())


class BriefLanguageHintTest(TestCase):
    """The brief may be written in any language (openspec: creator-ui-localization).

    Markup-level like CreateSteerAITest above: the create page is English-only,
    and nothing told a non-English creator the brief itself need not be. These
    pin what the server ships; the browser pass covers that it is visible.
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Hint Org")
        self.user = User.objects.create_user('hint_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.force_login(self.user)

    #: The rendered element. The bare class name also matches the stylesheet,
    #: which ships regardless of whether a provider is configured.
    HINT = 'class="pr-help ai-lang-hint"'

    def _page(self):
        return self.client.get('/editor/surveys/new/').content.decode()

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test',
                       MOBILE_EDITOR_NAV=True, CREATE_STEER_AI=True)
    def test_hint_is_shipped_with_the_brief(self):
        """
        GIVEN a configured provider
        WHEN the create page renders
        THEN the goal field carries a hint that the brief may be written in any
             language, naming languages a non-English reader recognises
        """
        html = self._page()
        self.assertIn(self.HINT, html)
        self.assertIn('whatever language you think in', html)
        self.assertIn('Bahasa Indonesia', html)

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test',
                       MOBILE_EDITOR_NAV=True, CREATE_STEER_AI=False)
    def test_hint_survives_the_steering_kill_switch(self):
        """
        GIVEN CREATE_STEER_AI off
        WHEN the create page renders
        THEN the hint is still shipped -- it is not part of the steering
             experiment and must not disappear with it
        """
        self.assertIn(self.HINT, self._page())

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test',
                       MOBILE_EDITOR_NAV=True, CREATE_STEER_AI=True)
    def test_hint_sits_outside_the_panel_intro(self):
        """
        GIVEN the mobile wizard hides .ai-panel-intro by CSS
        WHEN the create page renders
        THEN the hint sits after the goal input, which is below that intro --
             so the wizard's goal step still shows it
        """
        html = self._page()
        # The class name alone also matches the stylesheet in <head>, which is
        # not gated on a provider; assert on the element instead.
        self.assertGreater(html.index(self.HINT), html.index('id="id_goal"'))
        self.assertLess(html.index('ai-panel-intro'), html.index('id="id_goal"'))

    @override_settings(AI_PROVIDER='', MOBILE_EDITOR_NAV=True, CREATE_STEER_AI=True)
    def test_no_provider_means_no_hint(self):
        """
        GIVEN no configured LLM provider
        WHEN the create page renders
        THEN no hint element is shipped -- there is no brief to write in any
             language. The stylesheet may still ship; it styles nothing.
        """
        self.assertNotIn(self.HINT, self._page())

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test',
                       MOBILE_EDITOR_NAV=True, CREATE_STEER_AI=True)
    def test_blank_goal_path_is_instrumented(self):
        """
        GIVEN the intercept only fires for a non-empty goal
        WHEN the create page renders
        THEN the blank-goal path still reports an outcome, so "opened the page,
             wrote nothing, created empty" stops being invisible
        """
        html = self._page()
        self.assertIn("capture('blank_goal')", html)
        self.assertIn('blankReported', html)
