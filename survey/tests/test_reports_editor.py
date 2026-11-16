"""Spec: reports-editor (change reports-story, #704, epic #712).

A report is edited on its own, with or without a home survey; the Reports list opens the editor,
starts a blank report and deletes one; only editors of the workspace get in.
"""
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_member, make_pro_org, make_v1_survey
from reports.models import Report, ReportBlock


class _Editor(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org('EditorOrg', 'reporteditorowner')
        self.login(self.owner, self.org)
        self.report = Report.objects.create(organization=self.org, slug='blank-one', visibility='workspace',
                                            intro={'title': {'en': 'Blank one'}}, created_by=self.owner)

    def login(self, user, org):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = org.id
        session.save()

    def url(self, name, *args):
        return reverse(name, args=[self.report.uuid, *args])


class OwnAddressTest(_Editor):
    """Requirement: A report is edited on its own."""

    def test_a_blank_report(self):
        """
        GIVEN an editor on the Reports list
        WHEN they press "New report"
        THEN an unpublished, workspace-only report without a home survey opens in the editor
        """
        r = self.client.post(reverse('editor_report_create'))
        report = Report.objects.exclude(pk=self.report.pk).get()
        self.assertRedirects(r, reverse('editor_report', args=[report.uuid]))
        self.assertEqual((report.survey_id, report.is_published, report.visibility, report.organization_id),
                         (None, False, 'workspace', self.org.id))
        self.assertEqual(self.client.get(reverse('editor_report', args=[report.uuid])).status_code, 200)

    def test_adding_and_writing_a_block_by_the_reports_address(self):
        """
        GIVEN a report without a home survey
        WHEN an editor adds a Key numbers block and enters two numbers
        THEN the block is saved and the report's preview shows them
        """
        r = self.client.post(self.url('editor_report_block_add'), {'block_type': 'numbers'})
        block = ReportBlock.objects.get(report=self.report)
        self.assertRedirects(r, self.url('editor_report') + f'?block={block.id}')
        page = self.client.get(self.url('editor_report') + f'?block={block.id}')
        self.assertContains(page, self.url('editor_report_block_edit', block.id))
        r = self.client.post(self.url('editor_report_block_edit', block.id),
                             {'items': '447 | residents answered\n77 | paper questionnaires', 'width': 'half'},
                             HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200, r.content)
        block.refresh_from_db()
        self.assertEqual((block.config['items'][1], block.width),
                         ({'value': '77', 'label': 'paper questionnaires'}, 'half'))
        preview = self.client.get(self.url('editor_report_preview')).content.decode()
        self.assertIn('<b>447</b><span>residents answered</span>', preview)

    def test_a_member_of_another_workspace(self):
        """
        GIVEN a member of another workspace
        WHEN they open the report's editor address or post a block
        THEN the answer is 404
        """
        other_org, other_owner = make_pro_org('OtherReportOrg', 'otherreportowner')
        self.login(other_owner, other_org)
        self.assertEqual(self.client.get(self.url('editor_report')).status_code, 404)
        self.assertEqual(self.client.post(self.url('editor_report_block_add'), {'block_type': 'text'}).status_code, 404)
        self.assertFalse(ReportBlock.objects.exists())

    def test_a_viewer(self):
        """
        GIVEN a member with the viewer role
        WHEN they post a block to the report
        THEN the answer is 404 and nothing is added
        """
        self.login(make_member(self.org, 'reportviewer', role='viewer'), self.org)
        self.assertEqual(self.client.post(self.url('editor_report_block_add'), {'block_type': 'text'}).status_code, 404)
        self.assertFalse(ReportBlock.objects.exists())

    def test_the_same_report_through_its_survey(self):
        """
        GIVEN a survey with its report
        WHEN an editor adds a Text block on the survey's Public results tab and a Heading at the
             report's own address
        THEN both blocks are on that survey's report, and both pages list them
        """
        survey, _section = make_v1_survey(self.org, self.owner, name='Round one', status='published')
        self.client.get(reverse('editor_survey_public_results', args=[survey.uuid]))
        report = Report.objects.get(survey=survey)
        self.client.post(reverse('editor_public_results_block_add', args=[survey.uuid]), {'block_type': 'text'})
        self.client.post(reverse('editor_report_block_add', args=[report.uuid]), {'block_type': 'heading'})
        self.assertEqual(sorted(report.blocks.values_list('block_type', flat=True)), ['heading', 'text'])
        by_survey = self.client.get(reverse('editor_survey_public_results', args=[survey.uuid]))
        by_report = self.client.get(reverse('editor_report', args=[report.uuid]))
        ids = [b.id for b in by_report.context['blocks']]
        self.assertEqual([b.id for b in by_survey.context['blocks']], ids)
        self.assertEqual(len(ids), 2)


class ListTest(_Editor):
    """Requirement: The Reports list opens the editor."""

    def test_an_editors_list(self):
        """
        GIVEN an editor
        WHEN they open the Reports list
        THEN the report links to its editor, and New report and Import a report are offered
        """
        html = self.client.get(reverse('editor_reports')).content.decode()
        self.assertIn(self.url('editor_report'), html)
        self.assertIn('data-testid="report-create"', html)
        self.assertIn('data-testid="report-import"', html)

    def test_a_viewers_list(self):
        """
        GIVEN a viewer
        WHEN they open the Reports list
        THEN the report is listed without an editor link, and neither action is offered
        """
        self.login(make_member(self.org, 'listviewer', role='viewer'), self.org)
        html = self.client.get(reverse('editor_reports')).content.decode()
        self.assertIn('Blank one', html)
        self.assertNotIn(self.url('editor_report'), html)
        self.assertNotIn('data-testid="report-create"', html)
        self.assertNotIn('data-testid="report-import"', html)


class DeleteTest(_Editor):
    """Requirement: A report can be deleted."""

    def test_deleting_an_imported_report(self):
        """
        GIVEN a report with two blocks
        WHEN an editor opens the delete page and confirms
        THEN the page first says what goes, then the report and its blocks are gone
        """
        ReportBlock.objects.create(report=self.report, block_type='heading', content={'en': 'A'}, order=0)
        ReportBlock.objects.create(report=self.report, block_type='text', order=1)
        page = self.client.get(self.url('editor_report_delete'))
        self.assertContains(page, 'Its 2 blocks')
        self.assertTrue(Report.objects.filter(pk=self.report.pk).exists())
        r = self.client.post(self.url('editor_report_delete'))
        self.assertRedirects(r, reverse('editor_reports'))
        self.assertFalse(Report.objects.filter(pk=self.report.pk).exists())
        self.assertFalse(ReportBlock.objects.exists())
