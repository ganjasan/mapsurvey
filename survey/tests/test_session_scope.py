"""Spec: session-scope (change data-scope, Data epic #676, ADR-001 moves 0+1).

One builder (`data.scope.SessionScope`) decides which sessions a surface counts; the
owner's decisions of 2026-11-14 (ADR-001 §6.1, §6.2, §6.5) live in the surfaces' switches;
a ratchet guard keeps new hand-written copies out.
"""
import os
import re

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from data.scope import SessionScope
from survey.models import Answer, Membership, Question, SurveyHeader, SurveySection, SurveySession

from .helpers import _make_org


class _ScopeFixture(TestCase):
    """A published survey with a choice question and a last-section question."""

    def setUp(self):
        self.org = _make_org('ScopeOrg')
        self.owner = User.objects.create_user('scopeowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='scope_survey', organization=self.org, created_by=self.owner, status='published',
        )
        self.s1 = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.s2 = SurveySection.objects.create(survey_header=self.survey, name='s2', code='S2')
        self.s1.next_section = self.s2
        self.s1.save()
        self.q = Question.objects.create(
            survey_section=self.s1, code='SC_Q', name='Pick', input_type='choice',
            choices=[{'code': 1, 'name': 'A'}, {'code': 2, 'name': 'B'}],
        )
        self.q_last = Question.objects.create(
            survey_section=self.s2, code='SC_L', name='Last', input_type='text',
        )

    def _session(self, status='', deleted=False, answered=True, last=False, kind='external'):
        sess = SurveySession.objects.create(
            survey=self.survey, validation_status=status, is_deleted=deleted, opened_by_kind=kind,
        )
        if answered:
            Answer.objects.create(survey_session=sess, question=self.q, selected_choices=[1])
        if last:
            Answer.objects.create(survey_session=sess, question=self.q_last, text='done')
        return sess


class SessionScopeTest(_ScopeFixture):
    """Requirement: One builder decides which sessions a surface counts."""

    def setUp(self):
        super().setUp()
        self.ok = self._session('approved')
        self.hold = self._session('on_hold')
        self.rejected = self._session('not_approved')
        self.trashed = self._session(deleted=True)

    def test_default_scope_is_clean(self):
        """
        GIVEN an approved, an on-hold, a not-approved and a trashed session
        WHEN a scope is built with no switches
        THEN it holds only the approved session
        """
        self.assertEqual(SessionScope([self.survey.id]).ids(), {self.ok.id})

    def test_include_moderated_keeps_moderated_not_trashed(self):
        """
        GIVEN the same sessions
        WHEN the scope is built with include_moderated=True
        THEN it holds the approved, on-hold and not-approved sessions but not the trashed one
        """
        ids = SessionScope([self.survey.id], include_moderated=True).ids()
        self.assertEqual(ids, {self.ok.id, self.hold.id, self.rejected.id})

    def test_include_deleted_and_moderated_is_everything(self):
        """
        GIVEN the same sessions
        WHEN both include switches are on
        THEN every session is in scope
        """
        ids = SessionScope([self.survey.id], include_deleted=True, include_moderated=True).ids()
        self.assertEqual(ids, {self.ok.id, self.hold.id, self.rejected.id, self.trashed.id})

    def test_nonempty_drops_sessions_without_a_top_level_answer(self):
        """
        GIVEN an extra approved session with no answer
        WHEN the scope is built with nonempty=True
        THEN the empty session is out and the answered one stays
        """
        empty = self._session('approved', answered=False)
        ids = SessionScope([self.survey.id], nonempty=True).ids()
        self.assertIn(self.ok.id, ids)
        self.assertNotIn(empty.id, ids)

    def test_completed_headers_keep_sessions_that_reached_the_last_section(self):
        """
        GIVEN one approved session that answered the last section and one that did not
        WHEN the scope is built with completed_headers=[survey]
        THEN only the completed session is in scope
        """
        done = self._session('approved', last=True)
        ids = SessionScope([self.survey.id], completed_headers=[self.survey]).ids()
        self.assertEqual(ids, {done.id})

    def test_external_only(self):
        """
        GIVEN an approved session opened by the owner
        WHEN the scope is built with external_only=True
        THEN the owner's session is out
        """
        own = self._session('approved', kind='owner')
        ids = SessionScope([self.survey.id], external_only=True).ids()
        self.assertIn(self.ok.id, ids)
        self.assertNotIn(own.id, ids)

    def test_related_rows_follow_the_same_rule(self):
        """
        GIVEN answers of every session
        WHEN answers are filtered with the clean scope's related expression
        THEN only the approved session's answer remains
        """
        scope = SessionScope([self.survey.id])
        sessions = set(Answer.objects.filter(scope.q('survey_session'))
                       .values_list('survey_session_id', flat=True))
        self.assertEqual(sessions, {self.ok.id})
        sessions = set(Answer.objects.filter(SessionScope(()).related_q('survey_session'))
                       .values_list('survey_session_id', flat=True))
        self.assertEqual(sessions, {self.ok.id})


class SurfaceScopeTest(_ScopeFixture):
    """Requirement: Each surface uses its named scope (and the owner's §6 decisions)."""

    def test_public_results_and_responses_agree_on_answered_responses(self):
        """
        GIVEN 5 approved answered sessions and 2 approved empty ones
        WHEN the public results counter and the Responses overview are computed
        THEN both count 5 (ADR-001 §6.2)
        """
        from survey.analytics import SurveyAnalyticsService
        from reports.models import Report
        from reports.render import ReportService
        for _ in range(5):
            self._session('approved')
        for _ in range(2):
            self._session('approved', answered=False)
        page = Report.objects.create(survey=self.survey, slug='scope-pr', is_published=True)
        self.assertEqual(ReportService(page).response_count(), 5)
        overview = SurveyAnalyticsService(self.survey, include_empty=False).get_overview()
        self.assertEqual(overview['total_sessions'], 5)

    def test_export_leaves_out_on_hold_unless_include_all(self):
        """
        GIVEN 3 approved answered sessions and 1 answered on-hold session
        WHEN the export's session gate runs with and without include_all
        THEN the on-hold session is excluded by default and kept with include_all (§6.1)
        """
        from survey.export import excluded_sessions
        kept = [self._session('approved') for _ in range(3)]
        hold = self._session('on_hold')
        parts = [(self.survey, '')]
        excluded = excluded_sessions(parts, include_all=False, completed_only=False)
        self.assertIn(hold.id, excluded)
        self.assertFalse(excluded & {s.id for s in kept})
        self.assertNotIn(hold.id, excluded_sessions(parts, include_all=True, completed_only=False))

    def test_api_summary_scope_equals_the_export(self):
        """
        GIVEN the same 3 approved and 1 on-hold answered sessions
        WHEN the API's response scope is built without include_all
        THEN it counts 3 responses, like the file
        """
        from survey.response_scope import responses_scope
        for _ in range(3):
            self._session('approved')
        self._session('on_hold')
        self.assertEqual(responses_scope(self.survey).sessions.count(), 3)
        self.assertEqual(responses_scope(self.survey, include_all=True).sessions.count(), 4)

    def test_api_structure_count_ignores_trashed_sessions(self):
        """
        GIVEN 4 answered sessions, one of them trashed
        WHEN the API structure builds the version entry
        THEN it reports 3 responses
        """
        from api.v1.structure import _version
        for _ in range(3):
            self._session('approved')
        self._session('approved', deleted=True)
        self.assertEqual(_version(self.survey, True, {})['responses'], 3)

    def test_mcp_count_keeps_moderated_external_answered_sessions(self):
        """
        GIVEN an approved and an on-hold external answered session, an owner session and an
              empty external one
        WHEN the MCP survey response count runs
        THEN it counts the two external answered sessions
        """
        from mcp.tools.surveys import answered_external_sessions
        self._session('approved')
        self._session('on_hold')
        self._session('approved', kind='owner')
        self._session('approved', answered=False)
        self.assertEqual(answered_external_sessions(self.survey), 2)


class ModeratedHeadlineTest(_ScopeFixture):
    """Spec responses-empty-sessions / Requirement: The headline names moderated responses."""

    def setUp(self):
        super().setUp()
        self.client.login(username='scopeowner', password='pass')
        s = self.client.session
        s['active_org_id'] = self.org.id
        s.save()
        self.url = f'/editor/surveys/{self.survey.uuid}/analytics/'

    def test_moderated_responses_are_named(self):
        """
        GIVEN 3 shown responses of which 2 are on hold and 1 is not approved
        WHEN the creator opens Responses
        THEN the headline states 2 on hold and 1 not approved
        """
        self._session('approved')
        self._session('on_hold')
        self._session('on_hold')
        self._session('not_approved')
        html = self.client.get(self.url).content.decode()
        self.assertIn('data-testid="rv2-moderated-sessions"', html)
        self.assertIn('including 2 on hold', html)
        self.assertIn('1 not approved', html)

    def test_nothing_to_name(self):
        """
        GIVEN responses none of which is moderated
        WHEN the creator opens Responses
        THEN the headline carries no moderation line
        """
        self._session('approved')
        html = self.client.get(self.url).content.decode()
        self.assertNotIn('data-testid="rv2-moderated-sessions"', html)


class ExportDialogTextTest(SimpleTestCase):
    """Spec responses-export-formats / Requirement: On-hold sessions are exported only with include_all."""

    def test_dialog_names_on_hold_responses(self):
        """
        GIVEN the export dialog template
        WHEN its "Include excluded responses" explanation is read
        THEN it names trashed, on-hold and not-approved responses
        """
        from django.conf import settings
        path = os.path.join(settings.BASE_DIR, 'survey', 'templates', 'editor', 'partials', '_export_modal.html')
        text = open(path, encoding='utf-8').read()
        self.assertIn('Trashed, on-hold and not-approved responses are left out', text)


# ── Guard (ADR-001 move 0) ─────────────────────────────────────────────────

SESSION_FILTER = re.compile('|'.join([
    r'(?<![.\w])is_deleted\s*=(?!=)',     # keyword filter, not `session.is_deleted = …`
    r'__is_deleted\b',
    r'validation_status__in',
    r'exclude\(\s*validation_status',
    r'_has_top_level_answer',
]))
SCANNED_PACKAGES = ('survey', 'api', 'mcp', 'billing', 'newsletter', 'mapsurvey')

# Modules that may still write a session filter by hand, with why. This list may only
# shrink: rewire a module through data.scope, then lower or remove its entry.
ALLOWED_SESSION_FILTERS = {
    'survey/models.py': (3, 'the field itself and the SurveySession manager (active/deleted)'),
    'survey/views.py': (3, 'respondent flow: one session by id, and the editor-preview sessions of one survey'),
    'survey/analytics_views.py': (4, 'trash/restore and detail: one session by id'),
    'survey/paper_views.py': (1, 'paper entry: the session of one sheet'),
    'survey/paper/sheets.py': (1, 'paper entry: the sessions of one sheet'),
    'survey/paper/review.py': (1, 'paper entry: the session of one sheet'),
    'survey/operator_entry_views.py': (1, 'operator entry: one session by id'),
    'api/v1/responses.py': (1, 'response detail: one session by id'),
    'survey/funnel.py': (8, 'staff funnel dashboard over every workspace (growth module, not data)'),
    'survey/management/commands/backfill_posthog_events.py': (1, 'one-off staff backfill'),
    'survey/management/commands/export_creators.py': (1, 'staff export of creators'),
}


def session_filter_counts(root):
    counts = {}
    for package in SCANNED_PACKAGES:
        for dirpath, dirnames, filenames in os.walk(os.path.join(root, package)):
            dirnames[:] = [d for d in dirnames if d not in ('tests', 'migrations', '__pycache__')]
            for name in filenames:
                if not name.endswith('.py') or name.startswith('test'):
                    continue
                path = os.path.join(dirpath, name)
                n = 0
                with open(path, encoding='utf-8') as fh:
                    for line in fh:
                        if line.lstrip().startswith('#'):
                            continue
                        n += len(SESSION_FILTER.findall(line))
                if n:
                    counts[os.path.relpath(path, root)] = n
    return counts


class SessionFilterGuardTest(SimpleTestCase):
    """Requirement: No new hand-written session filter outside data."""

    def _counts(self):
        from django.conf import settings
        return session_filter_counts(str(settings.BASE_DIR))

    def test_no_new_hand_written_session_filter(self):
        """
        GIVEN every non-test product module outside data/
        WHEN its hand-written session filters are counted
        THEN none is off the allow-list or above its recorded count
        """
        over = {path: n for path, n in self._counts().items()
                if n > ALLOWED_SESSION_FILTERS.get(path, (0, ''))[0]}
        self.assertEqual(over, {}, 'Build these session sets with data.scope.SessionScope instead '
                                   'of filtering is_deleted / validation_status by hand.')

    def test_allow_list_only_shrinks(self):
        """
        GIVEN the allow-list
        WHEN a listed module holds fewer filters than recorded
        THEN the test fails until its entry is lowered or removed
        """
        counts = self._counts()
        stale = {path: (counts.get(path, 0), allowed)
                 for path, (allowed, _why) in ALLOWED_SESSION_FILTERS.items()
                 if counts.get(path, 0) < allowed}
        self.assertEqual(stale, {})

    def test_guard_catches_a_new_copy(self):
        """
        GIVEN a line that filters answers by session state by hand
        WHEN the guard's pattern reads it
        THEN it is counted, while attribute assignments are not
        """
        self.assertTrue(SESSION_FILTER.search('Answer.objects.filter(survey_session__is_deleted=False)'))
        self.assertTrue(SESSION_FILTER.search("qs.exclude(validation_status__in=('on_hold',))"))
        self.assertFalse(SESSION_FILTER.search('session.is_deleted = True'))
