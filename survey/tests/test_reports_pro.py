"""Spec: reports-pro (change reports-pro, #709, epic #712).

Reports is a Pro module: writing a report needs the feature (by plan, by a live trial, or by
starting the trial with that write); the editor opens read-only without it; a published report of
a workspace without it is served as a frozen snapshot, never a 404; a command counts and freezes
the affected reports.
"""
import io
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from api.tests.helpers import make_free_org, make_pro_org, make_v1_survey
from billing import entitlements as ents
from billing.models import Subscription
from billing.tests.helpers import trial_used_elsewhere
from reports.models import Report, ReportBlock
from survey.models import Answer, Question, SurveySession


class _Plans(TestCase):
    def workspace(self, pro, name, username):
        org, owner = (make_pro_org if pro else make_free_org)(name, username)
        survey, section = make_v1_survey(org, owner, name=f'{name} survey', status='published')
        question = Question.objects.create(survey_section=section, code='PRIO', name='Top priority',
                                           input_type='choice', choices=[{'code': 1, 'name': 'Trees'}])
        report = Report.objects.create(survey=survey, slug=f'{username}-report', is_published=True,
                                       visibility='unlisted', intro={'title': {'en': 'What we heard'}})
        ReportBlock.objects.create(report=report, block_type='text', content={'en': '<p>{responses} people answered.</p>'})
        ReportBlock.objects.create(report=report, block_type='chart', question=question, order=1)
        for _i in range(4):
            self.answer(survey, question)
        return org, owner, survey, question, report

    def answer(self, survey, question):
        s = SurveySession.objects.create(survey=survey)
        Answer.objects.create(survey_session=s, question=question, selected_choices=[1])

    def login(self, user, org):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = org.id
        session.save()

    def add_block(self, report):
        return self.client.post(reverse('editor_report_block_add', args=[report.uuid]), {'block_type': 'heading'})

    def page(self, report):
        from django.core.cache import cache
        cache.clear()
        return self.client.get(reverse('public_results', args=[report.slug]))


class WritesTest(_Plans):
    """Requirement: Writing a report needs the Reports feature."""

    def test_a_pro_workspace(self):
        """
        GIVEN an editor of a Pro workspace
        WHEN they add a block
        THEN the block is added
        """
        org, owner, _survey, _q, report = self.workspace(True, 'ProPlanOrg', 'proplanowner')
        self.login(owner, org)
        self.assertEqual(self.add_block(report).status_code, 302)
        self.assertEqual(report.blocks.count(), 3)

    def test_the_first_write_starts_the_trial(self):
        """
        GIVEN an editor of a workspace that never had a trial
        WHEN they add a block
        THEN the block is added and the workspace has a live trial that includes Reports
        """
        org, owner, _survey, _q, report = self.workspace(False, 'FreshFreeOrg', 'freshfreeowner')
        self.login(owner, org)
        self.assertFalse(ents.for_organization(org).covers('reports'))
        self.assertEqual(self.add_block(report).status_code, 302)
        self.assertEqual(report.blocks.count(), 3)
        ents.forget(org)
        self.assertTrue(ents.for_organization(org).covers('reports'))

    def test_after_the_trial(self):
        """
        GIVEN an editor of a free workspace whose owner's trial is over
        WHEN they add a block, publish, save settings, create a report and import one
        THEN each is refused with the upgrade page and nothing changes
        """
        org, owner, _survey, _q, report = self.workspace(False, 'SpentFreeOrg', 'spentfreeowner')
        trial_used_elsewhere(org)
        self.login(owner, org)
        report.is_published = False
        report.save()
        posts = [
            (reverse('editor_report_block_add', args=[report.uuid]), {'block_type': 'heading'}),
            (reverse('editor_report_set_published', args=[report.uuid]), {'publish': '1'}),
            (reverse('editor_report_save', args=[report.uuid]), {'intro_title': 'Changed'}),
            (reverse('editor_public_results_block_add', args=[report.survey.uuid]), {'block_type': 'heading'}),
            (reverse('editor_report_start'), {'kind': 'blank'}),
            (reverse('editor_report_create'), {}),
        ]
        for url, data in posts:
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 403, url)
        report.refresh_from_db()
        self.assertEqual((report.blocks.count(), report.is_published, report.title), (2, False, 'What we heard'))
        self.assertEqual(Report.objects.count(), 1)
        ajax = self.client.post(reverse('editor_report_block_add', args=[report.uuid]), {'block_type': 'heading'},
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual((ajax.status_code, ajax.json()['error']), (403, 'pro_required'))


class ReadOnlyTest(_Plans):
    """Requirement: The editor opens read-only without the feature."""

    def setUp(self):
        self.org, self.owner, self.survey, _q, self.report = self.workspace(True, 'LapsedOrg', 'lapsedowner')
        Subscription.objects.filter(organization=self.org).update(
            current_period_end=timezone.now() - timedelta(days=3))
        ents.forget(self.org)
        trial_used_elsewhere(self.org)
        self.login(self.owner, self.org)

    def test_a_lapsed_workspace_opens_its_report(self):
        """
        GIVEN a workspace whose subscription lapsed
        WHEN an editor opens a report, the Reports list and the start page
        THEN each opens, says reports are read-only on the current plan and links to the plan page;
             the editor lists the blocks
        """
        editor = self.client.get(reverse('editor_report', args=[self.report.uuid]))
        self.assertEqual(editor.status_code, 200)
        self.assertContains(editor, 'data-testid="reports-locked"')
        self.assertContains(editor, reverse('org_billing', args=[self.org.slug]))
        self.assertEqual(len(editor.context['blocks']), 2)
        for name in ('editor_reports', 'editor_report_start'):
            self.assertContains(self.client.get(reverse(name)), 'data-testid="reports-locked"')

    def test_export_still_works(self):
        """
        GIVEN that workspace
        WHEN the editor exports the report
        THEN the report file downloads
        """
        response = self.client.get(reverse('editor_report_export', args=[self.report.uuid]))
        self.assertEqual((response.status_code, response['Content-Type']), (200, 'application/zip'))

    def test_a_covered_workspace_shows_no_banner(self):
        """
        GIVEN a Pro workspace
        WHEN an editor opens a report
        THEN nothing says it is read-only
        """
        org, owner, _s, _q, report = self.workspace(True, 'StillProOrg', 'stillproowner')
        self.login(owner, org)
        self.assertNotContains(self.client.get(reverse('editor_report', args=[report.uuid])), 'data-testid="reports-locked"')


class FrozenTest(_Plans):
    """Requirement: A report of a workspace without the feature is served frozen."""

    def test_a_free_workspaces_published_page(self):
        """
        GIVEN a published live report of a free workspace with 4 answers
        WHEN it is requested, a fifth answer arrives, and it is requested again
        THEN both responses are 200, the report is frozen, and the second still shows 4
        """
        _org, _owner, survey, question, report = self.workspace(False, 'FreePageOrg', 'freepageowner')
        first = self.page(report)
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, '4 people answered.')
        report.refresh_from_db()
        self.assertEqual(report.mode, 'frozen')
        self.answer(survey, question)
        second = self.page(report)
        self.assertContains(second, '4 people answered.')
        self.assertContains(second, 'Data as of')

    def test_a_lapsed_subscription(self):
        """
        GIVEN a Pro workspace whose subscription ends
        WHEN its published live report is requested
        THEN the page opens with a "Data as of" date and the report is frozen
        """
        org, _owner, _survey, _q, report = self.workspace(True, 'EndedOrg', 'endedowner')
        self.assertNotContains(self.page(report), 'Data as of')
        Subscription.objects.filter(organization=org).update(current_period_end=timezone.now() - timedelta(days=1))
        ents.forget(org)
        response = self.page(report)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Data as of')
        report.refresh_from_db()
        self.assertEqual(report.mode, 'frozen')

    def test_a_pro_workspace_stays_live(self):
        """
        GIVEN a Pro workspace's published live report
        WHEN it is requested twice with a new answer in between
        THEN the second response shows the new number
        """
        _org, _owner, survey, question, report = self.workspace(True, 'LiveProOrg', 'liveproowner')
        self.assertContains(self.page(report), '4 people answered.')
        self.answer(survey, question)
        self.assertContains(self.page(report), '5 people answered.')
        report.refresh_from_db()
        self.assertEqual(report.mode, 'live')

    def test_a_blocks_page_and_its_csv(self):
        """
        GIVEN a free workspace's published live report
        WHEN the chart's own page, then its CSV after a new answer, are requested
        THEN the report is frozen and the CSV holds the snapshot's number
        """
        _org, _owner, survey, question, report = self.workspace(False, 'FreeBlockOrg', 'freeblockowner')
        chart = report.blocks.get(block_type='chart')
        page = self.client.get(reverse('report_block', args=[report.slug, chart.pk]))
        self.assertEqual(page.status_code, 200)
        report.refresh_from_db()
        self.assertEqual(report.mode, 'frozen')
        self.answer(survey, question)
        csv_text = self.client.get(reverse('report_block_csv', args=[report.slug, chart.pk])).content.decode()
        self.assertIn('Trees,4', csv_text)


class CommandTest(_Plans):
    """Requirement: Affected reports can be counted and frozen at once."""

    def setUp(self):
        _o, _u, _s, _q, self.free = self.workspace(False, 'CmdFreeOrg', 'cmdfreeowner')
        _o, _u, _s, _q, self.pro = self.workspace(True, 'CmdProOrg', 'cmdproowner')

    def run_command(self, *args):
        out = io.StringIO()
        call_command('freeze_reports_without_pro', *args, stdout=out)
        return out.getvalue()

    def test_dry_run(self):
        """
        GIVEN one free and one Pro workspace with a published live report each
        WHEN the command runs with --dry-run
        THEN it names the free workspace's report only and changes nothing
        """
        text = self.run_command('--dry-run')
        self.assertIn(f'/r/{self.free.slug}/', text)
        self.assertNotIn(f'/r/{self.pro.slug}/', text)
        self.assertIn('1 report(s) in 1 workspace(s)', text)
        self.free.refresh_from_db()
        self.assertEqual(self.free.mode, 'live')

    def test_freezing(self):
        """
        GIVEN the same two reports
        WHEN the command runs without --dry-run
        THEN the free workspace's report is frozen and the Pro workspace's is not
        """
        self.run_command()
        self.free.refresh_from_db()
        self.pro.refresh_from_db()
        self.assertEqual((self.free.mode, self.pro.mode), ('frozen', 'live'))
        self.assertIn('0 report(s)', self.run_command('--dry-run'))
