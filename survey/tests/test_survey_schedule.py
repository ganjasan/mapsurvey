"""Tests for the `survey-schedule` capability (openspec/specs/survey-schedule/spec.md).

The survey period: "accepts answers from … to …". Fields and form rules, the respondent gate,
the periodic close through the lifecycle service, the reopen rule, copies and backups.
"""
from datetime import timedelta
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from survey import schedule
from survey.models import AuditLog, Membership, SurveyHeader, SurveySection, SurveySession
from survey.serialization import serialize_survey_to_dict
from survey.services import publishing as svc_publishing
from survey.services import surveys as svc_surveys
from survey.services.context import Actor
from survey.services.errors import ValidationFailed
from survey.tests.helpers import _make_org

BERLIN = ZoneInfo('Europe/Berlin')


def _survey(name, status='published', **fields):
    org = _make_org(f'{name} org')
    owner = User.objects.create_user(username=f'{name}_owner', password='x')
    Membership.objects.create(user=owner, organization=org, role='owner')
    survey = SurveyHeader.objects.create(
        name=name, organization=org, created_by=owner, status=status,
        available_languages=['en'], redirect_url='#', **fields)
    SurveySection.objects.create(survey_header=survey, name='sec_a', title='A', code='SA', is_head=True)
    return survey, owner


def _local(delta, tz=BERLIN):
    """A wall-clock string for a datetime-local input, `delta` from now, in `tz`,
    plus the instant it names."""
    instant = (timezone.now() + delta).astimezone(tz).replace(second=0, microsecond=0)
    return instant.strftime(schedule.INPUT_FORMAT), instant


def _set(survey, owner, **data):
    return svc_surveys.update_settings(Actor(user=owner), survey, data, partial=True)


class PeriodFieldsTest(TestCase):
    """Requirement: A survey has an optional period."""

    def test_only_an_end_date_in_the_creators_zone(self):
        """
        GIVEN a published survey with no period
        WHEN the owner saves "Closes on" ten days ahead, typed in Europe/Berlin, and nothing else
        THEN closes_at is that Berlin wall-clock time as an instant, opens_at stays empty,
             the zone is recorded and the input renders the same wall-clock value back
        """
        survey, owner = _survey('period_end')
        typed, instant = _local(timedelta(days=10))
        _set(survey, owner, closes_at=typed, schedule_timezone='Europe/Berlin')
        survey.refresh_from_db()
        self.assertEqual(survey.closes_at, instant)
        self.assertIsNone(survey.opens_at)
        self.assertEqual(survey.schedule_timezone, 'Europe/Berlin')
        self.assertEqual(schedule.input_value(survey.closes_at, survey), typed)

    def test_end_before_start_is_refused(self):
        """
        GIVEN an opening time ten days ahead
        WHEN the closing time is five days ahead
        THEN the save fails on closes_at and nothing is written
        """
        survey, owner = _survey('period_order')
        opens, _ = _local(timedelta(days=10))
        closes, _ = _local(timedelta(days=5))
        with self.assertRaises(ValidationFailed) as ctx:
            _set(survey, owner, opens_at=opens, closes_at=closes, schedule_timezone='Europe/Berlin')
        self.assertIn('closes_at', ctx.exception.form.errors)
        survey.refresh_from_db()
        self.assertIsNone(survey.opens_at)
        self.assertIsNone(survey.closes_at)

    def test_a_new_closing_time_in_the_past_is_refused(self):
        """
        GIVEN a survey with no closing time
        WHEN the owner sets one that is already past
        THEN the save fails on closes_at
        """
        survey, owner = _survey('period_past')
        past, _ = _local(timedelta(days=-1))
        with self.assertRaises(ValidationFailed) as ctx:
            _set(survey, owner, closes_at=past, schedule_timezone='Europe/Berlin')
        self.assertIn('closes_at', ctx.exception.form.errors)

    def test_an_old_closing_time_survives_a_later_save(self):
        """
        GIVEN a survey closed automatically yesterday, closes_at still holding yesterday
        WHEN the owner saves another Settings field, with the PATCH shape and with the
             full-form shape that re-posts the stored value
        THEN both saves succeed and closes_at is unchanged
        """
        yesterday = timezone.now() - timedelta(days=1)
        survey, owner = _survey('period_old', status='closed', closes_at=yesterday, schedule_timezone='UTC')
        _set(survey, owner, visibility='public')
        survey.refresh_from_db()
        self.assertEqual(survey.closes_at, yesterday)
        _set(survey, owner, visibility='private', closes_at=schedule.input_value(yesterday, survey),
             schedule_timezone='UTC')
        survey.refresh_from_db()
        self.assertEqual(survey.closes_at, yesterday)

    def test_an_aware_value_is_kept_as_given(self):
        """
        GIVEN a value with an explicit offset (what the API sends)
        WHEN it is saved with a different schedule_timezone
        THEN the instant is the one the offset names, not re-read in the zone
        """
        survey, owner = _survey('period_aware')
        instant = (timezone.now() + timedelta(days=3)).replace(microsecond=0)
        _set(survey, owner, closes_at=instant.astimezone(ZoneInfo('Asia/Bishkek')).isoformat(),
             schedule_timezone='Europe/Berlin')
        survey.refresh_from_db()
        self.assertEqual(survey.closes_at, instant)

    def test_unknown_zone_is_refused(self):
        """
        GIVEN a zone name the tz database does not know
        WHEN it is saved
        THEN the save fails on schedule_timezone
        """
        survey, owner = _survey('period_zone')
        with self.assertRaises(ValidationFailed) as ctx:
            _set(survey, owner, schedule_timezone='Mars/Olympus')
        self.assertIn('schedule_timezone', ctx.exception.form.errors)

    def test_unpublished_changes_read_and_write_the_live_period(self):
        """
        GIVEN a published survey with a closing time and unpublished changes started
        WHEN the period is read on the draft copy and a new closing time is saved there
        THEN both reads are the canonical survey's, the canonical row holds the new time,
             the draft row holds nothing, and publishing the draft leaves it unchanged
        """
        survey, owner = _survey('period_draft')
        actor = Actor(user=owner)
        typed, instant = _local(timedelta(days=10))
        _set(survey, owner, closes_at=typed, schedule_timezone='Europe/Berlin')
        draft = svc_publishing.create_draft(actor, survey)
        self.assertEqual(schedule.next_event(draft)['at'], instant)
        typed2, instant2 = _local(timedelta(days=20))
        _set(draft, owner, closes_at=typed2)
        survey.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(survey.closes_at, instant2)
        self.assertIsNone(draft.closes_at)
        self.assertEqual(draft.schedule_timezone, '')
        svc_publishing.publish_draft(actor, draft, force=True, acknowledge_translation_gaps=True)
        survey.refresh_from_db()
        self.assertEqual(survey.closes_at, instant2)
        self.assertEqual(survey.schedule_timezone, 'Europe/Berlin')


class PeriodSettingsUiTest(TestCase):
    """Requirement: The period is set in Settings."""

    def test_panel_saves_both_inputs_and_shows_the_next_event(self):
        """
        GIVEN an owner on the Settings panel
        WHEN both inputs are posted with the browser's zone
        THEN the survey holds the two instants, the zone is recorded, the JSON answer is ok,
             and the publishing widget reads "Closes <time>" on the editor page
        """
        survey, owner = _survey('period_panel')
        self.client.force_login(owner)
        opens, opens_at = _local(timedelta(days=-1))
        closes, closes_at = _local(timedelta(days=2))
        response = self.client.post(
            reverse('editor_survey_settings_panel', args=[survey.uuid]),
            {'name': survey.name, 'visibility': 'private', 'finish_action': 'thanks',
             'available_languages': '["en"]', 'basemaps': '["streets"]', 'default_basemap': 'streets',
             'show_branding': 'on', 'opens_at': opens, 'closes_at': closes,
             'schedule_timezone': 'Europe/Berlin'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content)
        survey.refresh_from_db()
        self.assertEqual((survey.opens_at, survey.closes_at), (opens_at, closes_at))
        page = self.client.get(reverse('editor_survey_detail', args=[survey.uuid]))
        self.assertContains(page, 'Closes ')
        self.assertContains(page, 'pub-next')

    def test_panel_renders_the_period_block_and_stored_values(self):
        """
        GIVEN a survey with a closing time in Europe/Berlin
        WHEN the Settings panel is rendered
        THEN the block names the zone and the input carries the Berlin wall-clock value
        """
        typed, instant = _local(timedelta(days=4))
        survey, owner = _survey('period_render', closes_at=instant, schedule_timezone='Europe/Berlin')
        self.client.force_login(owner)
        page = self.client.get(reverse('editor_survey_settings', args=[survey.uuid]))
        self.assertContains(page, 'Survey period')
        self.assertContains(page, 'Europe/Berlin')
        self.assertContains(page, f'value="{typed}"')

    def test_clearing_an_input_clears_the_instant(self):
        """
        GIVEN a survey with a closing time
        WHEN "Closes on" is saved empty
        THEN closes_at is NULL and no next event is shown
        """
        survey, owner = _survey('period_clear', closes_at=timezone.now() + timedelta(days=3))
        _set(survey, owner, closes_at='')
        survey.refresh_from_db()
        self.assertIsNone(survey.closes_at)
        self.assertIsNone(schedule.next_event(survey))

    def test_next_event_phases(self):
        """
        GIVEN a published survey with both ends
        WHEN the clock is before, between and after them
        THEN next_event says opens, closes, then nothing; a draft says nothing at any time
        """
        opens = timezone.now() + timedelta(days=1)
        closes = timezone.now() + timedelta(days=3)
        survey, _ = _survey('period_phases', opens_at=opens, closes_at=closes)
        self.assertEqual(schedule.next_event(survey)['kind'], 'opens')
        self.assertEqual(schedule.next_event(survey, now=opens + timedelta(hours=1))['kind'], 'closes')
        self.assertIsNone(schedule.next_event(survey, now=closes + timedelta(hours=1)))
        survey.status = 'draft'
        self.assertIsNone(schedule.phase(survey))
        self.assertIsNone(schedule.next_event(survey))


class PeriodRespondentGateTest(TestCase):
    """Requirement: Respondents see the period, to the minute."""

    def _urls(self, survey):
        return [reverse('survey', args=[survey.uuid]),
                f'/surveys/{survey.uuid}/sec_a/']

    def test_before_the_opening_time(self):
        """
        GIVEN a published survey opening tomorrow in Europe/Berlin
        WHEN an anonymous visitor requests the survey and its first section
        THEN both are 200 "opens on" pages naming the survey and the Berlin time, noindex,
             and no session exists afterwards
        """
        opens = timezone.now() + timedelta(days=1)
        survey, _ = _survey('period_before', opens_at=opens, schedule_timezone='Europe/Berlin')
        for url in self._urls(survey):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'survey_not_yet_open.html')
            self.assertContains(response, survey.name)
            self.assertContains(response, 'not open yet')
            self.assertContains(response, 'Europe/Berlin')
            self.assertContains(response, schedule.format_in_zone(opens, survey))
            self.assertEqual(response['X-Robots-Tag'], 'noindex')
        self.assertFalse(SurveySession.objects.filter(survey=survey).exists())

    def test_after_the_closing_time_before_the_job(self):
        """
        GIVEN a published survey whose closing time passed a minute ago
        WHEN an anonymous visitor requests it
        THEN the response is the closed page and the status is still published
        """
        survey, _ = _survey('period_after', closes_at=timezone.now() - timedelta(minutes=1))
        response = self.client.get(reverse('survey', args=[survey.uuid]))
        self.assertTemplateUsed(response, 'survey_closed.html')
        self.assertContains(response, 'no longer accepting responses')
        survey.refresh_from_db()
        self.assertEqual(survey.status, 'published')

    def test_section_post_after_the_closing_time(self):
        """
        GIVEN a respondent who submits a section after the closing time
        WHEN the POST arrives
        THEN it is answered with the closed page and no session or answer is stored
        """
        survey, _ = _survey('period_post', closes_at=timezone.now() - timedelta(minutes=1))
        response = self.client.post(f'/surveys/{survey.uuid}/sec_a/', {})
        self.assertTemplateUsed(response, 'survey_closed.html')
        self.assertFalse(SurveySession.objects.filter(survey=survey).exists())

    def test_inside_the_period_the_survey_is_open(self):
        """
        GIVEN a published survey that opened an hour ago and closes tomorrow
        WHEN an anonymous visitor requests it
        THEN they are sent to the first section as usual
        """
        survey, _ = _survey('period_open', opens_at=timezone.now() - timedelta(hours=1),
                            closes_at=timezone.now() + timedelta(days=1))
        response = self.client.get(reverse('survey', args=[survey.uuid]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('sec_a', response['Location'])

    def test_editors_walk_through_regardless(self):
        """
        GIVEN a published survey opening tomorrow
        WHEN its owner opens it
        THEN they reach the first section
        """
        survey, owner = _survey('period_editor', opens_at=timezone.now() + timedelta(days=1))
        self.client.force_login(owner)
        response = self.client.get(reverse('survey', args=[survey.uuid]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('sec_a', response['Location'])

    def test_testing_ignores_the_period(self):
        """
        GIVEN a testing survey opening tomorrow
        WHEN a tester opens it with the test token
        THEN they reach the first section
        """
        survey, _ = _survey('period_testing', status='testing', opens_at=timezone.now() + timedelta(days=1))
        response = self.client.get(reverse('survey', args=[survey.uuid]) + f'?token={survey.test_token}')
        self.assertEqual(response.status_code, 302)
        self.assertIn('sec_a', response['Location'])


class ScheduledCloseTest(TestCase):
    """Requirement: The close happens through the lifecycle service."""

    def test_due_survey_is_closed_with_an_audit_row(self):
        """
        GIVEN a published survey whose closing time passed two minutes ago
        WHEN the periodic function runs
        THEN it reports one close, the status is closed, the audit row is the ordinary
             status_transition with scheduled=True and no actor, and the editor offers Reopen
        """
        survey, owner = _survey('due_close', closes_at=timezone.now() - timedelta(minutes=2))
        self.assertEqual(schedule.close_due(), 1)
        survey.refresh_from_db()
        self.assertEqual(survey.status, 'closed')
        row = AuditLog.objects.get(survey_uuid=survey.uuid, action='status_transition')
        self.assertIsNone(row.actor)
        self.assertEqual(row.metadata, {'old_status': 'published', 'new_status': 'closed', 'scheduled': True})
        self.client.force_login(owner)
        page = self.client.get(reverse('editor_survey_detail', args=[survey.uuid]))
        self.assertContains(page, 'Reopen survey')

    def test_not_due_not_published_not_canonical_not_trashed(self):
        """
        GIVEN a survey closing tomorrow, a testing survey past its time, unpublished changes
              of a survey past its time, and a trashed survey past its time
        WHEN the periodic function runs
        THEN none of them changes status
        """
        past = timezone.now() - timedelta(hours=1)
        later, _ = _survey('due_later', closes_at=timezone.now() + timedelta(days=1))
        testing, _ = _survey('due_testing', status='testing', closes_at=past)
        live, owner = _survey('due_live')
        draft = svc_publishing.create_draft(Actor(user=owner), live)
        SurveyHeader.objects.filter(pk=draft.pk).update(closes_at=past, status='published')
        trashed, _ = _survey('due_trashed', closes_at=past, deleted_at=timezone.now())
        self.assertEqual(schedule.close_due(), 0)
        for s in (later, testing, live, trashed):
            s.refresh_from_db()
        self.assertEqual([later.status, testing.status, live.status, trashed.status],
                         ['published', 'testing', 'published', 'published'])

    def test_one_failure_does_not_stop_the_pass(self):
        """
        GIVEN two due surveys, the first of which raises inside the transition
        WHEN the periodic function runs
        THEN the second is closed and the first stays published
        """
        past = timezone.now() - timedelta(hours=1)
        first, _ = _survey('due_first', closes_at=past - timedelta(hours=1))
        second, _ = _survey('due_second', closes_at=past)
        real = svc_publishing.transition

        def flaky(actor, survey, status, **kw):
            if survey.pk == first.pk:
                raise RuntimeError('boom')
            return real(actor, survey, status, **kw)

        with mock.patch('survey.services.publishing.transition', side_effect=flaky), \
                self.assertLogs('survey.schedule', level='ERROR'):
            self.assertEqual(schedule.close_due(), 1)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.status, second.status), ('published', 'closed'))

    def test_management_command(self):
        """
        GIVEN one due survey
        WHEN `apply_survey_schedule` runs
        THEN it closes the survey and prints the count
        """
        survey, _ = _survey('due_command', closes_at=timezone.now() - timedelta(minutes=5))
        out = StringIO()
        call_command('apply_survey_schedule', stdout=out)
        self.assertIn('Closed 1 survey(s).', out.getvalue())
        survey.refresh_from_db()
        self.assertEqual(survey.status, 'closed')

    def test_celery_task_wraps_the_same_function(self):
        """
        GIVEN the beat schedule
        WHEN the task runs
        THEN it calls close_due and beat names it every five minutes
        """
        from django.conf import settings
        from survey.tasks import apply_survey_schedule
        entry = settings.CELERY_BEAT_SCHEDULE['apply-survey-schedule']
        self.assertEqual(entry['task'], 'survey.tasks.apply_survey_schedule')
        self.assertEqual(entry['schedule'], 300.0)
        with mock.patch('survey.schedule.close_due', return_value=3) as fn:
            self.assertEqual(apply_survey_schedule.apply().get(), 3)
        fn.assert_called_once()


class ReopenRuleTest(TestCase):
    """Requirement: Reopening by hand is final."""

    def test_reopen_after_an_automatic_close(self):
        """
        GIVEN a survey closed by the task yesterday, which also opened in the past
        WHEN the owner reopens it and the task runs again
        THEN the survey stays published, both instants are cleared, and an audit row
             schedule_cleared names them
        """
        opened = timezone.now() - timedelta(days=10)
        closed = timezone.now() - timedelta(days=1)
        survey, owner = _survey('reopen_auto', status='closed', opens_at=opened, closes_at=closed)
        svc_publishing.transition(Actor(user=owner), survey, 'published')
        survey.refresh_from_db()
        self.assertIsNone(survey.closes_at)
        self.assertIsNone(survey.opens_at)
        row = AuditLog.objects.get(survey_uuid=survey.uuid, action='schedule_cleared')
        self.assertEqual(row.metadata, {'closes_at': closed.isoformat(), 'opens_at': opened.isoformat()})
        self.assertEqual(schedule.close_due(), 0)
        survey.refresh_from_db()
        self.assertEqual(survey.status, 'published')

    def test_early_manual_close_keeps_the_plan(self):
        """
        GIVEN a survey closing next week, closed by hand today
        WHEN the owner reopens it
        THEN closes_at still holds next week and no schedule_cleared row is written
        """
        later = timezone.now() + timedelta(days=7)
        survey, owner = _survey('reopen_early', status='closed', closes_at=later)
        svc_publishing.transition(Actor(user=owner), survey, 'published')
        survey.refresh_from_db()
        self.assertEqual(survey.closes_at, later)
        self.assertFalse(AuditLog.objects.filter(survey_uuid=survey.uuid, action='schedule_cleared').exists())


class PeriodCopiesTest(TestCase):
    """Requirement: Copies and backups leave the period behind."""

    def test_duplicate_has_no_period(self):
        """
        GIVEN a survey closing next week in Europe/Berlin
        WHEN it is duplicated
        THEN the copy has no opens_at, no closes_at and an empty zone
        """
        from survey.cloning import SURVEY_COPY_EXCLUDED_FIELDS
        self.assertTrue({'opens_at', 'closes_at', 'schedule_timezone'} <= set(SURVEY_COPY_EXCLUDED_FIELDS))
        survey, owner = _survey('copy_src', opens_at=timezone.now() - timedelta(days=1),
                                closes_at=timezone.now() + timedelta(days=7), schedule_timezone='Europe/Berlin')
        from survey.cloning import clone_survey
        copy = clone_survey(survey, created_by=owner)
        self.assertIsNone(copy.opens_at)
        self.assertIsNone(copy.closes_at)
        self.assertEqual(copy.schedule_timezone, '')

    def test_backup_carries_no_period(self):
        """
        GIVEN a survey with a period
        WHEN its survey.json is built
        THEN it carries none of the period keys
        """
        survey, _ = _survey('backup_src', closes_at=timezone.now() + timedelta(days=7), schedule_timezone='UTC')
        data = serialize_survey_to_dict(survey)
        self.assertFalse({'opens_at', 'closes_at', 'schedule_timezone'} & set(data))
