"""Tests for the `creator-funnel-events` capability (openspec/specs/creator-funnel-events/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from unittest import mock
from unittest.mock import patch
import re
from survey.models import SurveyHeader, SurveySection, SurveySession, Membership
from survey.models import AIGenerationEvent
from io import StringIO
from django.core.management import call_command
import datetime
from unittest.mock import patch as _ai_patch
from survey import product_events as _pe
from survey.tests.helpers import _FakeProvider, _ai_blob, _make_org


class CreatorFunnelEventTest(TestCase):
    """Forward emission of the creator-lifecycle events.

    These are the same events `backfill_posthog_events` reproduces from history,
    so the two must agree exactly on names and on what each step counts. A
    mismatch does not fail loudly — it produces a funnel with a step that
    silently halves at the cutover date.
    """

    def setUp(self):
        self.org = _make_org('FunnelEventOrg')
        self.user = User.objects.create_user(
            'funnelcreator', email='fc@example.com', password='pass',
        )
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

    def test_emit_is_a_noop_when_posthog_is_disabled(self):
        """
        GIVEN PostHog is unconfigured, as in tests and local development
        WHEN an event is emitted
        THEN nothing is captured and nothing raises
        """
        import posthog

        from survey import product_events as pe
        with mock.patch.object(posthog, 'disabled', True), \
                mock.patch('posthog.capture') as capture:
            pe.emit(pe.SURVEY_CREATED, self.user.pk, {'survey_id': '1'})
        capture.assert_not_called()

    def test_emit_never_raises(self):
        """
        GIVEN analytics must never be able to break a request
        WHEN the capture call itself fails
        THEN emit swallows it
        """
        import posthog

        from survey import product_events as pe
        with mock.patch.object(posthog, 'disabled', False), \
                mock.patch('posthog.capture', side_effect=RuntimeError('down')):
            pe.emit(pe.SURVEY_CREATED, self.user.pk)  # must not raise

    def test_emit_uses_user_pk_as_distinct_id(self):
        """
        GIVEN backfilled history must land on the same person as live traffic
        WHEN an event is emitted
        THEN the distinct id is the user's primary key, matching the snippet
        """
        import posthog

        from survey import product_events as pe
        with mock.patch.object(posthog, 'disabled', False), \
                mock.patch('posthog.capture') as capture:
            pe.emit(pe.SURVEY_CREATED, self.user.pk)
        self.assertEqual(capture.call_args.kwargs['distinct_id'], str(self.user.pk))
        self.assertEqual(
            capture.call_args.kwargs['properties']['timestamp_source'], pe.SOURCE_LIVE,
        )

    def test_first_response_fires_once_per_survey(self):
        """
        GIVEN the funnel step means "this survey got its first answer"
        WHEN several respondents start sessions on the same survey
        THEN the event is emitted exactly once, for the first
        """
        import posthog

        from survey import product_events as pe
        survey = SurveyHeader.objects.create(
            name='fe_survey', organization=self.org, redirect_url='#',
            status='published', created_by=self.user,
        )
        with mock.patch.object(posthog, 'disabled', False), \
                mock.patch('posthog.capture') as capture:
            SurveySession.objects.create(survey=survey)
            SurveySession.objects.create(survey=survey)
            SurveySession.objects.create(survey=survey)

        first = [c for c in capture.call_args_list
                 if c.args and c.args[0] == pe.SURVEY_FIRST_RESPONSE]
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].kwargs['distinct_id'], str(self.user.pk))

    def test_first_response_is_attributed_to_the_creator_only(self):
        """
        GIVEN respondents are anonymous and must not reach PostHog
        WHEN the first-response event is emitted
        THEN it carries the survey id and the owner, and nothing about the respondent
        """
        import posthog

        from survey import product_events as pe
        survey = SurveyHeader.objects.create(
            name='fe_survey2', organization=self.org, redirect_url='#',
            status='published', created_by=self.user,
        )
        with mock.patch.object(posthog, 'disabled', False), \
                mock.patch('posthog.capture') as capture:
            SurveySession.objects.create(survey=survey)

        call = next(c for c in capture.call_args_list
                    if c.args and c.args[0] == pe.SURVEY_FIRST_RESPONSE)
        self.assertEqual(set(call.kwargs['properties']) - {'timestamp_source'},
                         {'survey_id', 'creation_method', 'respondent_kind'})
        self.assertEqual(call.kwargs['properties']['respondent_kind'], 'external')

    def test_backfill_and_live_emission_use_the_same_event_names(self):
        """
        GIVEN a name that differs between the two halves splits the funnel
        WHEN the backfill command's stage list is compared with the constants
        THEN they are the same set
        """
        from survey import product_events as pe
        from survey.management.commands.check_posthog_funnel_parity import STAGE_EVENTS
        self.assertEqual({e for _, e in STAGE_EVENTS}, set(pe.CREATOR_FUNNEL_EVENTS))

    def test_backfill_event_ids_are_deterministic(self):
        """
        GIVEN the import must be safe to re-run
        WHEN the same (event, row) is hashed twice
        THEN the uuid is identical, so PostHog deduplicates instead of doubling
        """
        from survey.management.commands.backfill_posthog_events import event_uuid
        from survey import product_events as pe
        a = event_uuid(pe.SURVEY_CREATED, 42)
        b = event_uuid(pe.SURVEY_CREATED, 42)
        c = event_uuid(pe.SURVEY_CREATED, 43)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_backfill_reuses_the_dashboard_published_statuses(self):
        """
        GIVEN a restated copy of PUBLISHED_STATUSES would drift
        WHEN the backfill module is inspected
        THEN it imports the constant from funnel.py rather than defining its own

        'archived' belongs to that tuple and is easy to forget: counting only
        published+closed understates the stage by every archived survey.
        """
        from survey.funnel import PUBLISHED_STATUSES
        from survey.management.commands import backfill_posthog_events as cmd
        self.assertIs(cmd.PUBLISHED_STATUSES, PUBLISHED_STATUSES)
        self.assertIn('archived', PUBLISHED_STATUSES)

    def test_backfill_dry_run_sends_nothing(self):
        """
        GIVEN the volume must be known before anything is sent
        WHEN the command runs with --dry-run
        THEN it prints counts and captures nothing
        """
        from io import StringIO

        from django.core.management import call_command

        import posthog
        SurveyHeader.objects.create(
            name='bf_survey', organization=self.org, redirect_url='#',
            status='published', created_by=self.user,
        )
        out = StringIO()
        with mock.patch.object(posthog, 'disabled', False), \
                mock.patch('posthog.capture') as capture:
            call_command('backfill_posthog_events', '--dry-run', stdout=out)
        capture.assert_not_called()
        self.assertIn('creator_registered', out.getvalue())
        self.assertIn('dry run', out.getvalue())

    def test_backfill_refuses_without_a_key(self):
        """
        GIVEN a backfill against an unconfigured project would silently do nothing
        WHEN the command runs for real with no key
        THEN it fails loudly
        """
        from django.core.management import call_command
        from django.core.management.base import CommandError
        with self.settings(POSTHOG_PROJECT_KEY=''):
            with self.assertRaises(CommandError):
                call_command('backfill_posthog_events', verbosity=0)


class AIFunnelEventTest(TestCase):
    """The AI drafting sub-funnel in PostHog.

    The generator creates surveys through `materialize_draft`, not through the
    create view, so it emits no `survey_created` of its own unless this path
    does it. That absence is invisible in the product and fatal to the
    measurement: the manual/ai split would read 100% manual forever.
    """

    def setUp(self):
        self.org = _make_org('AIFunnelOrg')
        self.user = User.objects.create_user('aifunneluser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

    def _brief(self):
        from survey.ai.generation import SurveyBrief

        return SurveyBrief(
            name='funnel_survey', goal='Where is heat worst',
            audience='Residents', map_target='Hot spots',
            use_case='urban_planning',
        )

    def _run(self, provider, capture):
        """Run one generation with PostHog enabled and `capture` recording."""
        import posthog

        from survey.ai.generation import generate_survey_draft, start_generation

        brief = self._brief()
        event = start_generation(self.user, self.org, brief, ['en'])
        with mock.patch.object(posthog, 'disabled', False), \
                patch('posthog.capture', capture), \
                patch('survey.ai.generation.client.get_provider', return_value=provider):
            generate_survey_draft(event, brief, ['en'], {'name': 'funnel_survey'})
        event.refresh_from_db()
        return event

    @staticmethod
    def _calls(capture, name):
        return [c for c in capture.call_args_list if c.args and c.args[0] == name]

    def test_successful_generation_emits_survey_created_as_ai(self):
        """
        GIVEN the funnel's manual/ai split is the point of the instrumentation
        WHEN an AI draft is materialized successfully
        THEN one survey_created is emitted, marked ai, carrying the new survey's id
        """
        from survey import product_events as pe
        capture = mock.MagicMock()

        event = self._run(_FakeProvider([_ai_blob(('en',))]), capture)

        created = self._calls(capture, pe.SURVEY_CREATED)
        self.assertEqual(len(created), 1)
        props = created[0].kwargs['properties']
        self.assertEqual(props['creation_method'], pe.CREATION_AI)
        self.assertEqual(props['survey_id'], str(event.created_survey_id))
        self.assertEqual(created[0].kwargs['distinct_id'], str(self.user.pk))

    def test_survey_id_matches_the_manual_path_id_space(self):
        """
        GIVEN the manual path and the backfill both send the primary key
        WHEN the AI path emits survey_created
        THEN it sends the primary key too, not the uuid

        Two id spaces under one property name make the comparison the whole
        change exists for unjoinable — and it would look fine until someone
        tried to join.
        """
        from survey import product_events as pe
        capture = mock.MagicMock()

        event = self._run(_FakeProvider([_ai_blob(('en',))]), capture)

        props = self._calls(capture, pe.SURVEY_CREATED)[0].kwargs['properties']
        self.assertEqual(props['survey_id'], str(event.created_survey.id))
        self.assertNotEqual(props['survey_id'], str(event.created_survey.uuid))

    def test_generated_questions_count_as_the_question_step(self):
        """
        GIVEN survey_question_added fires when a human adds a question in the editor
        WHEN an AI draft arrives with its questions already written
        THEN the step is emitted anyway, marked ai

        Without this the funnel reports AI creators as "created a survey, never
        added a question" — the empty-editor drop-off the generator exists to
        remove, reported as though it got worse.
        """
        from survey import product_events as pe
        capture = mock.MagicMock()

        event = self._run(_FakeProvider([_ai_blob(('en',))]), capture)

        added = self._calls(capture, pe.SURVEY_QUESTION_ADDED)
        self.assertEqual(len(added), 1)
        props = added[0].kwargs['properties']
        self.assertEqual(props['creation_method'], pe.CREATION_AI)
        self.assertEqual(props['survey_id'], str(event.created_survey_id))

    def test_failed_generation_emits_no_question_step(self):
        """
        GIVEN a generation that produced no survey
        WHEN it ends
        THEN no question step is claimed for a survey that does not exist
        """
        from survey import product_events as pe
        bad = _ai_blob(('en',))
        bad['sections'] = bad['sections'][:1]
        capture = mock.MagicMock()

        self._run(_FakeProvider([bad, dict(bad)]), capture)

        self.assertEqual(self._calls(capture, pe.SURVEY_QUESTION_ADDED), [])

    def test_finished_event_carries_outcome_and_usage(self):
        """
        GIVEN cost and latency are worth watching per outcome
        WHEN a generation succeeds
        THEN ai_draft_finished reports the outcome with the provider's usage
        """
        from survey import product_events as pe
        capture = mock.MagicMock()

        self._run(_FakeProvider([_ai_blob(('en',))]), capture)

        finished = self._calls(capture, pe.AI_DRAFT_FINISHED)
        self.assertEqual(len(finished), 1)
        props = finished[0].kwargs['properties']
        self.assertEqual(props['outcome'], 'success')
        self.assertEqual(props['input_tokens'], 100)
        self.assertEqual(props['latency_ms'], 1234)

    def test_failed_generation_reports_the_outcome_and_creates_nothing(self):
        """
        GIVEN a draft rejected by the validator twice
        WHEN generation ends
        THEN ai_draft_finished says invalid_draft and no survey_created is emitted
        """
        from survey import product_events as pe
        bad = _ai_blob(('en',))
        bad['sections'] = bad['sections'][:1]
        capture = mock.MagicMock()

        self._run(_FakeProvider([bad, dict(bad)]), capture)

        finished = self._calls(capture, pe.AI_DRAFT_FINISHED)
        self.assertEqual(len(finished), 1)
        self.assertEqual(finished[0].kwargs['properties']['outcome'], 'invalid_draft')
        self.assertEqual(self._calls(capture, pe.SURVEY_CREATED), [])

    def test_no_brief_text_reaches_posthog(self):
        """
        GIVEN the brief is the creator's project description, often a client's
        WHEN the generation events are emitted
        THEN no free-text value from the brief appears in any payload
        """
        capture = mock.MagicMock()

        self._run(_FakeProvider([_ai_blob(('en',))]), capture)

        secrets = ('Where is heat worst', 'Residents', 'Hot spots', 'funnel_survey')
        for call in capture.call_args_list:
            payload = repr(call.kwargs.get('properties', {}))
            for secret in secrets:
                self.assertNotIn(secret, payload)


class AIFunnelViewEventTest(TestCase):
    """The two events that only the request cycle knows about."""

    def setUp(self):
        self.org = _make_org('AIFunnelViewOrg')
        self.user = User.objects.create_user('aifunnelview', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='aifunnelview', password='pass')

    @staticmethod
    def _calls(capture, name):
        return [c for c in capture.call_args_list if c.args and c.args[0] == name]

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_accepted_brief_emits_a_request_event_without_its_text(self):
        """
        GIVEN a valid brief submitted for generation
        WHEN the view enqueues the task
        THEN ai_draft_requested reports the shape of the request, never its words
        """
        import posthog

        from survey import product_events as pe
        capture = mock.MagicMock()
        with mock.patch.object(posthog, 'disabled', False), \
                patch('posthog.capture', capture), \
                patch('survey.editor_views.generate_survey_draft_task.delay'):
            self.client.post(reverse('editor_survey_create'), {
                'action': 'generate', 'name': 'brief_survey',
                'available_languages': '["en"]', 'goal': 'Find the noisiest streets',
                'audience': 'Neighbours', 'map_target': 'Noise sources',
                'use_case': 'urban_planning',
            })

        requested = self._calls(capture, pe.AI_DRAFT_REQUESTED)
        self.assertEqual(len(requested), 1)
        props = requested[0].kwargs['properties']
        self.assertEqual(props['language_count'], 1)
        self.assertTrue(props['has_use_case'])
        self.assertNotIn('Find the noisiest streets', repr(props))

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='')
    def test_unconfigured_provider_emits_nothing(self):
        """
        GIVEN no provider credentials
        WHEN a generation is somehow posted anyway
        THEN no request event is emitted, because no generation was started
        """
        import posthog

        from survey import product_events as pe
        capture = mock.MagicMock()
        with mock.patch.object(posthog, 'disabled', False), \
                patch('posthog.capture', capture):
            self.client.post(reverse('editor_survey_create'), {
                'action': 'generate', 'name': 'brief_survey',
                'available_languages': '["en"]', 'goal': 'g',
                'audience': 'a', 'map_target': 'm', 'use_case': 'urban_planning',
            })

        self.assertEqual(self._calls(capture, pe.AI_DRAFT_REQUESTED), [])

    def test_opened_event_fires_once_on_the_redirecting_poll(self):
        """
        GIVEN the redirect is what proves the creator waited for the draft
        WHEN the status endpoint is polled twice after success
        THEN ai_draft_opened is emitted on the first poll only

        The second poll is not hypothetical: the overlay keeps polling until the
        browser acts on HX-Redirect, and a reopened tab polls again.
        """
        import posthog

        from survey import product_events as pe
        survey = SurveyHeader.objects.create(
            name='generated_funnel', organization=self.org, created_by=self.user,
        )
        event = AIGenerationEvent.objects.create(
            kind='survey_draft', user=self.user, organization=self.org,
            outcome='success', created_survey=survey, languages=['en'],
        )
        url = reverse('editor_generation_status', kwargs={'event_id': event.id})

        capture = mock.MagicMock()
        with mock.patch.object(posthog, 'disabled', False), \
                patch('posthog.capture', capture):
            self.client.get(url)
            self.client.get(url)

        opened = self._calls(capture, pe.AI_DRAFT_OPENED)
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].kwargs['properties']['survey_id'], str(survey.id))


class AIBackfillCommandTest(TestCase):
    """Reconstructing the sub-funnel from AIGenerationEvent rows."""

    def setUp(self):
        self.org = _make_org('AIBackfillOrg')
        self.user = User.objects.create_user('aibackfill', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

    def _row(self, **kwargs):
        defaults = dict(
            kind='survey_draft', user=self.user, organization=self.org,
            outcome='success', languages=['en', 'de'], brief={'use_case': 'urban_planning'},
        )
        defaults.update(kwargs)
        return AIGenerationEvent.objects.create(**defaults)

    def _collected(self):
        from survey.management.commands.backfill_ai_events import Command

        return Command()._collect(None)

    def test_event_ids_are_deterministic(self):
        """
        GIVEN the import must be safe to re-run
        WHEN the same (event, row) is hashed twice
        THEN the uuid is identical, so PostHog deduplicates instead of doubling
        """
        from survey import product_events as pe
        from survey.posthog_backfill import event_uuid
        self.assertEqual(
            event_uuid(pe.AI_DRAFT_REQUESTED, 7), event_uuid(pe.AI_DRAFT_REQUESTED, 7),
        )
        self.assertNotEqual(
            event_uuid(pe.AI_DRAFT_REQUESTED, 7), event_uuid(pe.AI_DRAFT_REQUESTED, 8),
        )

    def test_row_without_redirect_produces_no_open_event(self):
        """
        GIVEN a creator who left before the draft finished
        WHEN history is reconstructed
        THEN no ai_draft_opened is invented for them

        A substituted timestamp here would erase the abandonment the metric is
        supposed to measure.
        """
        from survey import product_events as pe
        survey = SurveyHeader.objects.create(
            name='bf_survey', organization=self.org, created_by=self.user,
        )
        self._row(created_survey=survey, redirected_at=None)

        names = [e['event'] for e in self._collected()]

        self.assertIn(pe.AI_DRAFT_REQUESTED, names)
        self.assertIn(pe.AI_DRAFT_FINISHED, names)
        self.assertNotIn(pe.AI_DRAFT_OPENED, names)

    def test_pending_rows_produce_only_the_request(self):
        """
        GIVEN a row still pending, or one whose worker died
        WHEN history is reconstructed
        THEN the brief submission counts but no finish is claimed
        """
        from survey import product_events as pe
        self._row(outcome='pending')

        names = [e['event'] for e in self._collected()]

        self.assertEqual(names, [pe.AI_DRAFT_REQUESTED])

    def test_ai_surveys_are_not_labelled_manual_by_the_other_backfill(self):
        """
        GIVEN both commands derive the same uuid5 for one survey's creation
        WHEN the creator-funnel backfill reconstructs an AI-generated survey
        THEN it labels it ai, so whichever command runs first agrees with the other

        Dedup means the loser of that race is silently dropped. If the two
        disagreed, the surviving event would depend on run order.
        """
        from survey import product_events as pe
        from survey.management.commands.backfill_posthog_events import Command
        survey = SurveyHeader.objects.create(
            name='bf_ai_survey', organization=self.org, created_by=self.user,
        )
        self._row(created_survey=survey)

        created = [e for e in Command()._collect(None)
                   if e['event'] == pe.SURVEY_CREATED
                   and e['properties']['survey_id'] == str(survey.id)]

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]['properties']['creation_method'], pe.CREATION_AI)

    def test_later_events_carry_the_method_too(self):
        """
        GIVEN "do AI drafts get published and answered more often?" is the question
        WHEN a generated survey is published and receives its first response
        THEN both events carry creation_method, so it is a breakdown not a join
        """
        import posthog

        from survey import product_events as pe
        survey = SurveyHeader.objects.create(
            name='bf_later_events', organization=self.org, created_by=self.user,
            redirect_url='#', status='draft',
        )
        self._row(created_survey=survey)
        capture = mock.MagicMock()

        with mock.patch.object(posthog, 'disabled', False), \
                patch('posthog.capture', capture):
            SurveySession.objects.create(survey=survey)

        call = next(c for c in capture.call_args_list
                    if c.args and c.args[0] == pe.SURVEY_FIRST_RESPONSE)
        self.assertEqual(call.kwargs['properties']['creation_method'], pe.CREATION_AI)

    def test_manual_surveys_keep_their_label(self):
        """
        GIVEN a survey with no AI generation behind it
        WHEN the creator-funnel backfill runs
        THEN it is still labelled manual
        """
        from survey import product_events as pe
        from survey.management.commands.backfill_posthog_events import Command
        survey = SurveyHeader.objects.create(
            name='bf_manual_survey', organization=self.org, created_by=self.user,
        )

        created = [e for e in Command()._collect(None)
                   if e['event'] == pe.SURVEY_CREATED
                   and e['properties']['survey_id'] == str(survey.id)]

        self.assertEqual(created[0]['properties']['creation_method'], pe.CREATION_MANUAL)


class SessionOpenerKindTest(TestCase):
    """SurveySession.opened_by_kind and the external-only first response."""

    def setUp(self):
        self.org = _make_org('KindOrg')
        self.owner = User.objects.create_user('kind_owner', password='x')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='kind_survey', organization=self.org, redirect_url='#',
            status='published', created_by=self.owner,
        )
        SurveySection.objects.create(
            survey_header=self.survey, name='section1',
            start_map_postion=Point(0, 0), start_map_zoom=10,
        )

    def test_owner_session_is_owner_and_anonymous_is_external(self):
        """
        GIVEN the owner opens their published survey, then an anonymous visitor does
        WHEN the sessions are created by the section view
        THEN the first is kind owner and the second is external
        """
        self.client.force_login(self.owner)
        self.client.get(f'/surveys/{self.survey.uuid}/section1/')
        self.client.logout()
        anon = self.client_class()
        anon.get(f'/surveys/{self.survey.uuid}/section1/')
        kinds = list(SurveySession.objects.filter(survey=self.survey)
                     .order_by('id').values_list('opened_by_kind', flat=True))
        self.assertEqual(kinds, ['owner', 'external'])

    def test_first_response_fires_once_for_the_first_external_session(self):
        """
        GIVEN an owner test session, then two anonymous sessions
        WHEN sessions are saved
        THEN survey_first_response is emitted exactly once, at the first external one,
             with respondent_kind=external
        """
        with _ai_patch('survey.signals.pe.emit') as emit:
            SurveySession.objects.create(survey=self.survey, opened_by_kind='owner')
            SurveySession.objects.create(survey=self.survey, opened_by_kind='preview')
            first_calls = [c for c in emit.call_args_list if c.args[0] == _pe.SURVEY_FIRST_RESPONSE]
            self.assertEqual(first_calls, [])
            SurveySession.objects.create(survey=self.survey)              # external by default
            SurveySession.objects.create(survey=self.survey)
        first_calls = [c for c in emit.call_args_list if c.args[0] == _pe.SURVEY_FIRST_RESPONSE]
        self.assertEqual(len(first_calls), 1)
        self.assertEqual(first_calls[0].args[1], self.owner.pk)
        self.assertEqual(first_calls[0].args[2]['respondent_kind'], 'external')
        self.assertEqual(first_calls[0].args[2]['survey_id'], str(self.survey.id))


class BackfillBoundsTest(TestCase):
    """backfill_posthog_events --until / --events keep a re-run away from live rows."""

    def _run(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('backfill_posthog_events', '--dry-run', *args, stdout=out)
        return out.getvalue()

    def _count(self, out, name):
        import re
        m = re.search(rf'^{re.escape(name)}\s+(\d+)$', out, re.M)
        return int(m.group(1)) if m else None

    def test_until_excludes_rows_from_the_live_period(self):
        """
        GIVEN one creator registered before the cut-off and one after
        WHEN the backfill runs with --until at the cut-off
        THEN only the earlier registration is counted
        """
        from datetime import datetime, timezone as tz
        old = User.objects.create_user('bf_old', password='x')
        User.objects.filter(pk=old.pk).update(date_joined=datetime(2026, 8, 1, tzinfo=tz.utc))
        new = User.objects.create_user('bf_new', password='x')
        User.objects.filter(pk=new.pk).update(date_joined=datetime(2026, 8, 20, tzinfo=tz.utc))
        out = self._run('--until', '2026-08-16')
        self.assertEqual(self._count(out, 'creator_registered'), 1)

    def test_events_restricts_to_named_events_and_rejects_unknown(self):
        """
        GIVEN an active creator
        WHEN the backfill runs with --events creator_activated_account
        THEN only activation rows are counted, and an unknown name is refused
        """
        from django.core.management import CommandError
        User.objects.create_user('bf_active', password='x')
        out = self._run('--events', 'creator_activated_account')
        self.assertEqual(self._count(out, 'creator_activated_account'), 1)
        self.assertEqual(self._count(out, 'creator_registered'), 0)
        with self.assertRaises(CommandError):
            self._run('--events', 'not_an_event')
