"""Spec: reports (change reports-object, #703, epic #712).

A report is a workspace object whose blocks read Data datasets; the public results pages became
the first reports; a survey opens its report; workspace-only visibility; the Reports list; a view a
block shows cannot be deleted.
"""
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from api.tests.helpers import make_pro_org, make_v1_survey
from data.models import Dataset, DatasetView
from reports.models import Report, ReportBlock
from reports.render import ReportService, render_data
from survey.models import (
    Answer, CommentThread, Membership, Question, SurveyHeader, SurveySection, SurveySession,
)


def _answer_choice(survey, question, code, text_q=None):
    session = SurveySession.objects.create(survey=survey)
    Answer.objects.create(survey_session=session, question=question, selected_choices=[code])
    return session


class _TwoSurveys(TestCase):
    """Survey A with a choice question, survey B with a point question, one workspace."""

    def setUp(self):
        self.org, self.owner = make_pro_org('ReportOrg', 'reportowner')
        self.a, self.a_section = make_v1_survey(self.org, self.owner, name='Round one', status='published')
        self.b, self.b_section = make_v1_survey(self.org, self.owner, name='Round two', status='published')
        self.choice = Question.objects.create(
            survey_section=self.a_section, code='Q_PRIO', name='Top priority', input_type='choice',
            choices=[{'code': 1, 'name': 'Crossings'}, {'code': 2, 'name': 'Trees'}])
        self.point = Question.objects.create(
            survey_section=self.b_section, code='Q_WHERE', name='Where', input_type='point')
        self.report = Report.objects.create(survey=self.a, slug='two-rounds', is_published=True)
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()


class ReportOverDatasetsTest(_TwoSurveys):
    """Requirement: A report is a workspace object over Data datasets."""

    def test_blocks_over_two_surveys(self):
        """
        GIVEN a report with a chart block over survey A and a map block over survey B
        WHEN the report is rendered
        THEN both blocks show, each with its own survey's aggregates
        """
        ReportBlock.objects.create(report=self.report, block_type='chart', question=self.choice, order=0)
        ReportBlock.objects.create(report=self.report, block_type='map', question=self.point, order=1)
        for _ in range(4):
            _answer_choice(self.a, self.choice, 1)
        for _ in range(3):
            s = SurveySession.objects.create(survey=self.b)
            Answer.objects.create(survey_session=s, question=self.point, point=Point(30.0, 60.0))

        chart, grid = ReportService(self.report).build_blocks()

        self.assertEqual({i['code']: i['value'] for i in chart['items']}[1], 4)
        self.assertEqual(grid['respondents_total'], 3)
        self.assertEqual(self.report.organization_id, self.org.id)

    def test_block_names_a_dataset_and_a_code(self):
        """
        GIVEN a chart block and a map block made from questions
        WHEN their sources are read
        THEN the chart reads the survey's responses dataset, the map the question's answers dataset
        """
        chart = ReportBlock.objects.create(report=self.report, block_type='chart', question=self.choice)
        grid = ReportBlock.objects.create(report=self.report, block_type='map', question=self.point)

        self.assertEqual((chart.dataset.kind, chart.dataset.survey_id, chart.question_code),
                         (Dataset.KIND_RESPONSES, self.a.id, 'Q_PRIO'))
        self.assertEqual((grid.dataset.kind, grid.dataset.survey_id, grid.dataset.question_code),
                         (Dataset.KIND_ANSWERS, self.b.id, 'Q_WHERE'))

    def test_question_row_replaced(self):
        """
        GIVEN a chart block and answers to its question in an archived version
        WHEN the canonical survey gets a new question row with the same code
        THEN the block shows the answers of both rows
        """
        ReportBlock.objects.create(report=self.report, block_type='chart', question=self.choice)
        version = SurveyHeader.objects.create(name='Round one v1', organization=self.org, is_canonical=False,
                                              canonical_survey=self.a, version_number=1)
        old_section = SurveySection.objects.create(survey_header=version, name='section_1', code='S1')
        self.choice.survey_section = old_section          # what publish_draft does to the old rows
        self.choice.save()
        new_row = Question.objects.create(
            survey_section=self.a_section, code='Q_PRIO', name='Top priority', input_type='choice',
            choices=[{'code': 1, 'name': 'Crossings'}, {'code': 2, 'name': 'Trees'}])
        for _ in range(3):
            _answer_choice(version, self.choice, 1)
        for _ in range(3):
            _answer_choice(self.a, new_row, 1)

        block = ReportBlock.objects.get(report=self.report)
        payload = ReportService(self.report).build_blocks()[0]

        self.assertEqual(block.question, new_row)
        self.assertEqual({i['code']: i['value'] for i in payload['items']}[1], 6)

    def test_question_gone(self):
        """
        GIVEN a report with a block whose question no longer exists and a text block
        WHEN the report is rendered
        THEN only the text block is there
        """
        ReportBlock.objects.create(report=self.report, block_type='chart', question=self.choice, order=0)
        ReportBlock.objects.create(report=self.report, block_type='text', content={'en': 'Hello'}, order=1)
        self.choice.delete()

        blocks = ReportService(self.report).build_blocks()

        self.assertEqual([b['block_type'] for b in blocks], ['text'])

    def test_other_workspace_question_refused(self):
        """
        GIVEN a question of a survey in another workspace
        WHEN it is added to the report through the service
        THEN the service refuses and no block is written
        """
        from reports import services
        from survey.services.context import Actor
        other_org, other_owner = make_pro_org('OtherOrg', 'otherowner')
        other, other_section = make_v1_survey(other_org, other_owner, name='Theirs', status='published')
        theirs = Question.objects.create(survey_section=other_section, code='Q_X', name='X', input_type='choice',
                                         choices=[{'code': 1, 'name': 'A'}])

        with self.assertRaises(services.ReportRefused):
            services.add_question_block(Actor(user=self.owner), self.report, theirs)

        self.assertFalse(self.report.blocks.exists())


class SurveyOpensItsReportTest(_TwoSurveys):
    """Requirement: A survey opens its report."""

    def test_tab_shows_the_reports_blocks(self):
        """
        GIVEN a survey whose report has a chart block
        WHEN an editor opens the survey's Public results tab
        THEN the configuration lists that block and no second report is created
        """
        block = ReportBlock.objects.create(report=self.report, block_type='chart', question=self.choice)

        response = self.client.get(reverse('editor_survey_public_results', args=[self.a.uuid]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([b.pk for b in response.context['blocks']], [block.pk])
        self.assertEqual(Report.objects.filter(survey=self.a).count(), 1)

    def test_first_visit_creates_the_report(self):
        """
        GIVEN a published survey without a report
        WHEN an editor opens its Public results tab
        THEN a report of the survey's workspace exists with a block for its question
        """
        response = self.client.get(reverse('editor_survey_public_results', args=[self.b.uuid]))

        self.assertEqual(response.status_code, 200)
        report = self.b.report
        self.assertEqual(report.organization_id, self.org.id)
        self.assertEqual(list(report.blocks.values_list('block_type', 'question_code')), [('map', 'Q_WHERE')])


class WorkspaceOnlyTest(_TwoSurveys):
    """Requirement: Workspace-only visibility."""

    def setUp(self):
        super().setUp()
        self.report.visibility = 'workspace'
        self.report.save()
        self.url = reverse('public_results', args=[self.report.slug])

    def test_member_opens_it(self):
        """
        GIVEN a published workspace-only report
        WHEN a member of the workspace opens its address
        THEN it renders with noindex
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['noindex'])

    def test_stranger_gets_404(self):
        """
        GIVEN a published workspace-only report
        WHEN a signed-in user who is not a member opens it
        THEN the answer is 404
        """
        self.client.force_login(User.objects.create_user('stranger', password='x'))

        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_anonymous_is_sent_to_login(self):
        """
        GIVEN a published workspace-only report
        WHEN an anonymous visitor opens it
        THEN they are redirected to the login page
        """
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_not_in_the_sitemap(self):
        """
        GIVEN a published workspace-only report
        WHEN the sitemap is built
        THEN the report's address is not in it
        """
        self.assertNotIn('/r/two-rounds/', self.client.get('/sitemap.xml').content.decode())


class ReportsListTest(_TwoSurveys):
    """Requirement: The workspace lists its reports."""

    def test_lists_published_and_unpublished(self):
        """
        GIVEN a published report and an unpublished one
        WHEN a member opens Reports
        THEN both are listed with their state
        """
        Report.objects.create(survey=self.b, slug='round-two')

        html = self.client.get(reverse('editor_reports')).content.decode()

        self.assertIn('data-state="published"', html)
        self.assertIn('data-state="unpublished"', html)
        self.assertIn('Round two', html)

    def test_hides_reports_of_surveys_without_a_role(self):
        """
        GIVEN an editor of the workspace with no role on survey A
        WHEN they open Reports
        THEN survey A's report is not listed
        """
        editor = User.objects.create_user('justeditor', password='x')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        self.client.force_login(editor)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        response = self.client.get(reverse('editor_reports'))

        self.assertEqual(response.context['rows'], [])

    def test_sidebar_has_reports(self):
        """
        GIVEN a signed-in member
        WHEN an editor page renders
        THEN the sidebar links to Reports
        """
        self.assertIn(reverse('editor_reports'), self.client.get(reverse('editor_reports')).content.decode())


class ViewInUseTest(_TwoSurveys):
    """Requirement: A view shown by a report cannot be deleted."""

    def test_view_in_a_block_stays(self):
        """
        GIVEN a map block that shows a grid view of the question's answers
        WHEN the owner deletes the view
        THEN the service refuses and the view stays
        """
        from data import services as data_services
        from survey.services.context import Actor
        block = ReportBlock.objects.create(report=self.report, block_type='map', question=self.point)
        view = DatasetView.objects.create(dataset=block.dataset, name='All marks', kind='grid', color='#aa0000')
        block.view = view
        block.save()

        with self.assertRaises(data_services.DataRefused):
            data_services.delete_view(Actor(user=self.owner), view)

        self.assertTrue(DatasetView.objects.filter(pk=view.pk).exists())
        self.assertEqual(ReportService(self.report).build_blocks()[0]['color'], '#aa0000')


class PagesBecomeReportsTest(TransactionTestCase):
    """Requirement: Existing public results pages are reports (migrations reports/0002, survey/0131)."""

    BEFORE = [('reports', '0001_initial'), ('survey', '0130_map_layer_workspace')]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_page_with_blocks_and_a_thread_is_copied(self):
        """
        GIVEN a frozen, published page of a version copy with chart, map, text and orphan blocks,
              a comment thread on the chart block, and no registry rows yet
        WHEN the migrations run
        THEN the report has the same id, address, state and snapshot, its blocks the same ids and
             order with datasets of the CANONICAL survey, and the thread is still on its block
        """
        executor = MigrationExecutor(connection)
        executor.migrate(self.BEFORE)
        old = executor.loader.project_state(self.BEFORE).apps
        Org = old.get_model('survey', 'Organization')
        Header = old.get_model('survey', 'SurveyHeader')
        Section = old.get_model('survey', 'SurveySection')
        OldQuestion = old.get_model('survey', 'Question')
        Page = old.get_model('survey', 'PublicResultsPage')
        Block = old.get_model('survey', 'PublicResultsBlock')
        Thread = old.get_model('survey', 'CommentThread')

        org = Org.objects.create(name='Mig Org', slug='mig-org')
        canonical = Header.objects.create(name='Riverside', organization=org)
        version = Header.objects.create(name='Riverside v1', organization=org, is_canonical=False,
                                        canonical_survey=canonical, version_number=1)
        section = Section.objects.create(survey_header=version, name='s1', code='S1')
        choice = OldQuestion.objects.create(survey_section=section, code='Q_CH', name='Rate', input_type='choice')
        point = OldQuestion.objects.create(survey_section=section, code='Q_PT', name='Mark', input_type='point')
        snapshot = {'snapshot_version': 3, 'lang': 'en', 'response_count': 7, 'blocks': [{'id': 1}]}
        page = Page.objects.create(survey=canonical, slug='riverside', visibility='unlisted', is_published=True,
                                   mode='frozen', snapshot=snapshot, snapshot_version=3,
                                   k_anonymity_threshold=5, intro={'title': {'en': 'What we heard'}})
        chart = Block.objects.create(page=page, block_type='chart', question=choice, order=0, viz='pie')
        grid = Block.objects.create(page=page, block_type='map', question=point, order=1,
                                    geo_label_fields=['SQ'], basemap='satellite')
        text = Block.objects.create(page=page, block_type='text', order=2, content={'en': 'Hello'})
        orphan = Block.objects.create(page=page, block_type='chart', question=None, order=3)
        thread = Thread.objects.create(survey=canonical, anchor_kind='block', block=chart)

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

        report = Report.objects.get(pk=page.id)
        self.assertEqual((report.slug, report.visibility, report.is_published, report.mode,
                          report.k_anonymity_threshold, report.survey_id, report.organization_id),
                         ('riverside', 'unlisted', True, 'frozen', 5, canonical.id, org.id))
        self.assertEqual(report.snapshot, snapshot)
        self.assertEqual(render_data(report)['response_count'], 7)
        blocks = {b.id: b for b in report.blocks.select_related('dataset')}
        self.assertEqual(list(report.blocks.values_list('id', flat=True)), [chart.id, grid.id, text.id, orphan.id])
        self.assertEqual((blocks[chart.id].dataset.kind, blocks[chart.id].dataset.survey_id,
                          blocks[chart.id].question_code, blocks[chart.id].viz),
                         ('responses', canonical.id, 'Q_CH', 'pie'))
        self.assertEqual((blocks[grid.id].dataset.kind, blocks[grid.id].dataset.survey_id,
                          blocks[grid.id].dataset.question_code, blocks[grid.id].geo_label_fields,
                          blocks[grid.id].basemap),
                         ('answers', canonical.id, 'Q_PT', ['SQ'], 'satellite'))
        self.assertIsNone(blocks[text.id].dataset_id)
        self.assertEqual(blocks[text.id].content, {'en': 'Hello'})
        self.assertIsNone(blocks[orphan.id].dataset_id)
        self.assertEqual(CommentThread.objects.get(pk=thread.id).block_id, chart.id)
        # The sequences moved past the copied ids.
        fresh = Report.objects.create(organization_id=org.id, slug='fresh')
        self.assertGreater(fresh.id, report.id)
        self.assertGreater(ReportBlock.objects.create(report=fresh, block_type='text').id, orphan.id)
