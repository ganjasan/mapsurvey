"""Spec: reports-embed (change reports-embed, #708, epic #712).

A published report, or one of its blocks, framed by the sites its author allows; oEmbed for their
links; a block's numbers as CSV masked as the page; a block as PNG; all of them in one ZIP made on
the worker.
"""
import io
import zipfile
from unittest import mock

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_pro_org, make_v1_survey
from reports import services
from reports.models import Report, ReportBlock, ReportPdf
from reports.tasks import render_report_pdf
from survey.models import Answer, Question, SurveySession
from survey.services.context import Actor


class _Embed(TestCase):
    def setUp(self):
        patcher = mock.patch('survey.print.static_map.fetch_basemap', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.org, self.owner = make_pro_org('EmbedOrg', 'reportembedowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Riverside', status='published')
        self.transport = Question.objects.create(survey_section=self.section, code='TRANSPORT', name='Transport',
                                                 input_type='choice',
                                                 choices=[{'code': 1, 'name': 'Car'}, {'code': 2, 'name': 'Bike'}])
        self.age = Question.objects.create(survey_section=self.section, code='AGE', name='Age', input_type='choice',
                                           choices=[{'code': 1, 'name': 'Under 30'}, {'code': 2, 'name': 'Over 60'}])
        self.spot = Question.objects.create(survey_section=self.section, code='SPOT', name='Where', input_type='point')
        for transport, age, n in ((1, 1, 4), (2, 1, 1)):
            for i in range(n):
                s = SurveySession.objects.create(survey=self.survey)
                Answer.objects.create(survey_session=s, question=self.transport, selected_choices=[transport])
                Answer.objects.create(survey_session=s, question=self.age, selected_choices=[age])
                Answer.objects.create(survey_session=s, question=self.spot, point=Point(30.0 + i * 1e-5, 59.0))
        self.actor = Actor(user=self.owner, ip=None, surface='editor')
        self.report = Report.objects.create(survey=self.survey, slug='riverside-embed', is_published=True,
                                            visibility='unlisted', intro={'title': {'en': 'What we heard'}})
        self.chart = ReportBlock.objects.create(report=self.report, block_type='chart', question=self.transport, order=0)
        self.text = ReportBlock.objects.create(report=self.report, block_type='text',
                                               content={'en': '<p>Only words here.</p>'}, order=1)
        self.map = ReportBlock.objects.create(report=self.report, block_type='map', question=self.spot, order=2)
        self.page = reverse('public_results', args=[self.report.slug])

    def login(self):
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def block_url(self, block):
        return reverse('report_block', args=[self.report.slug, block.pk])


class FramingTest(_Embed):
    """Requirement: A published report can be framed by the sites its author allows."""

    def test_any_site_by_default(self):
        """
        GIVEN a published unlisted report with no allowed hosts
        WHEN its page is requested
        THEN the response allows any ancestor and carries no X-Frame-Options
        """
        response = self.client.get(self.page)
        self.assertEqual(response['Content-Security-Policy'], 'frame-ancestors *')
        self.assertFalse(response.has_header('X-Frame-Options'))

    def test_an_allow_list(self):
        """
        GIVEN the allowed hosts are saved as "city.example.org" in the editor
        WHEN the page and a block's page are requested
        THEN both name https://city.example.org and not every site
        """
        self.login()
        self.client.post(reverse('editor_report_save', args=[self.report.uuid]),
                         {'intro_title': 'What we heard', 'visibility': 'unlisted', 'embed_hosts': 'https://City.example.org/page'},
                         HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.report.refresh_from_db()
        self.assertEqual(self.report.embed_allowed_hosts, ['city.example.org'])
        self.client.logout()
        for url in (self.page, self.block_url(self.chart)):
            self.assertEqual(self.client.get(url)['Content-Security-Policy'],
                             "frame-ancestors 'self' https://city.example.org")

    def test_a_workspace_only_report(self):
        """
        GIVEN a workspace-only report
        WHEN a member opens it
        THEN the response keeps X-Frame-Options: SAMEORIGIN
        """
        self.report.visibility = 'workspace'
        self.report.save()
        self.login()
        response = self.client.get(self.page)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.assertFalse(response.has_header('Content-Security-Policy'))

    def test_not_a_host(self):
        """
        GIVEN an editor saves "not a host" as an allowed site
        WHEN the settings are posted
        THEN the save is refused and the list is unchanged
        """
        self.login()
        response = self.client.post(reverse('editor_report_save', args=[self.report.uuid]),
                                    {'intro_title': 'T', 'embed_hosts': 'not a host'},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual((response.status_code, response.json()['error']), (400, 'bad_host'))
        self.report.refresh_from_db()
        self.assertEqual(self.report.embed_allowed_hosts, [])


class HeightTest(_Embed):
    """Requirement: A framed report tells its host how tall it is."""

    def test_embed_mode(self):
        """
        GIVEN a published unlisted report
        WHEN it is requested with embed=1 and without
        THEN only the embedded page posts height messages, and it shows no ribbon
        """
        framed = self.client.get(self.page, {'embed': '1'}).content.decode()
        plain = self.client.get(self.page).content.decode()
        self.assertIn("mapsurvey: 'height'", framed)
        self.assertNotIn('class="ribbon"', framed)
        self.assertNotIn("mapsurvey: 'height'", plain)
        self.assertIn('class="ribbon"', plain)


class BlockPageTest(_Embed):
    """Requirement: One block has a page of its own."""

    def test_a_single_chart(self):
        """
        GIVEN a published report with a chart, a text and a map
        WHEN the chart's own address is requested
        THEN the page shows the chart and neither the report's title heading nor its other blocks
        """
        html = self.client.get(self.block_url(self.chart)).content.decode()
        self.assertIn(f'data-block-id="{self.chart.pk}"', html)
        self.assertNotIn(f'data-block-id="{self.map.pk}"', html)
        self.assertNotIn('Only words here.', html)
        self.assertNotIn('<h1>', html)

    def test_a_hidden_block(self):
        """
        GIVEN a hidden block, and a block of another report
        WHEN their addresses under this report are requested
        THEN both answer 404
        """
        self.map.is_hidden = True
        self.map.save()
        other = Report.objects.create(survey=self.survey, slug='other-embed', is_published=True)
        foreign = ReportBlock.objects.create(report=other, block_type='chart', question=self.transport)
        self.assertEqual(self.client.get(self.block_url(self.map)).status_code, 404)
        self.assertEqual(self.client.get(self.block_url(foreign)).status_code, 404)


class OembedTest(_Embed):
    """Requirement: Report and block links answer oEmbed."""

    def ask(self, path):
        return self.client.get(reverse('oembed'), {'url': 'http://testserver' + path, 'format': 'json'})

    def test_a_report_link(self):
        """
        GIVEN a published unlisted report
        WHEN oEmbed is asked about its link and about a block's link
        THEN both answers are rich with an iframe of that address, and the page carries the discovery link
        """
        whole = self.ask(self.page).json()
        self.assertEqual(whole['type'], 'rich')
        self.assertIn(f'/r/{self.report.slug}/?embed=1', whole['html'])
        block = self.ask(self.block_url(self.chart)).json()
        self.assertIn(f'/r/{self.report.slug}/block/{self.chart.pk}/?embed=1', block['html'])
        self.assertIn('application/json+oembed', self.client.get(self.page).content.decode())

    def test_a_workspace_only_report(self):
        """
        GIVEN a workspace-only report and an unpublished one
        WHEN oEmbed is asked about their links
        THEN the answers are 404
        """
        self.report.visibility = 'workspace'
        self.report.save()
        self.assertEqual(self.ask(self.page).status_code, 404)
        self.report.visibility, self.report.is_published = 'public', False
        self.report.save()
        self.assertEqual(self.ask(self.page).status_code, 404)


class CsvTest(_Embed):
    """Requirement: A block's numbers download as CSV, masked as the page."""

    def csv_of(self, block):
        return self.client.get(reverse('report_block_csv', args=[self.report.slug, block.pk]))

    def test_a_crosstab_with_a_hidden_group(self):
        """
        GIVEN a cross-tab where one respondent answered Bike and Under 30, K = 3
        WHEN its CSV is downloaded
        THEN that cell reads "<3", the totals of its row and column read "—", and no cell holds 1
        """
        block = services.add_view_block(self.actor, self.report, 'crosstab', self.survey, rows='TRANSPORT', columns='AGE')
        lines = self.csv_of(block).content.decode().splitlines()
        self.assertEqual(lines[0], 'Transport,Under 30,Over 60,total')
        self.assertEqual(lines[1], 'Car,4,0,4')
        self.assertEqual(lines[2], 'Bike,<3,0,—')
        self.assertEqual(lines[3], 'total,—,0,—')
        self.assertNotIn('1', ''.join(lines[1:]).replace('<3', ''))

    def test_a_grid_map(self):
        """
        GIVEN a map block showing squares over five points
        WHEN its CSV is downloaded
        THEN it lists cell bounds with respondent counts and no answer's point
        """
        text = self.csv_of(self.map).content.decode()
        self.assertTrue(text.startswith('west,south,east,north,respondents'))
        self.assertTrue(text.strip().splitlines()[1].endswith(',5'))
        self.assertNotIn('30.00001,59.0', text)

    def test_a_text_block(self):
        """
        GIVEN a text block
        WHEN its CSV is requested
        THEN the answer is 404
        """
        self.assertEqual(self.csv_of(self.text).status_code, 404)

    def test_an_unpublished_report(self):
        """
        GIVEN the report is unpublished
        WHEN an anonymous visitor asks for the chart's CSV, and its editor asks through the editor
        THEN the visitor gets 404 and the editor gets the file
        """
        self.report.is_published = False
        self.report.save()
        self.assertEqual(self.csv_of(self.chart).status_code, 404)
        self.login()
        response = self.client.get(reverse('editor_report_block_file', args=[self.report.uuid, self.chart.pk, 'csv']))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode().splitlines(), ['option,answers', 'Car,4', 'Bike,<3'])


class PictureTest(_Embed):
    """Requirement: A block downloads as a picture."""

    def test_a_chart_as_png(self):
        """
        GIVEN an editor
        WHEN they download the chart and the map as PNG, and ask for the text block's
        THEN the first two are PNG images and the third is 404
        """
        self.login()
        for block in (self.chart, self.map):
            response = self.client.get(reverse('editor_report_block_file', args=[self.report.uuid, block.pk, 'png']))
            self.assertEqual(response['Content-Type'], 'image/png')
            self.assertTrue(response.content.startswith(b'\x89PNG'))
        response = self.client.get(reverse('editor_report_block_file', args=[self.report.uuid, self.text.pk, 'png']))
        self.assertEqual(response.status_code, 404)
        self.client.logout()
        response = self.client.get(reverse('editor_report_block_file', args=[self.report.uuid, self.chart.pk, 'png']))
        self.assertEqual(response.status_code, 302)


class ZipTest(_Embed):
    """Requirement: Every chart and map comes in one archive, made on the worker."""

    def test_the_archive(self):
        """
        GIVEN a report with a chart, a text and a map
        WHEN an editor asks for the ZIP and the worker runs the job
        THEN nothing was built in the request, and the job serves a ZIP with a CSV and a PNG for
             the chart and for the map and nothing for the text
        """
        self.login()
        url = reverse('editor_report_pdf', args=[self.report.uuid])
        with mock.patch('reports.tasks.render_report_pdf.delay') as delay, \
                mock.patch('reports.tasks.build_zip') as build:
            job_id = self.client.post(url, {'kind': 'zip'}).json()['job']
        build.assert_not_called()
        delay.assert_called_once()
        self.assertEqual(ReportPdf.objects.get(pk=job_id).kind, 'zip')
        render_report_pdf(job_id)
        state = self.client.get(url, {'job': job_id}).json()
        self.assertEqual(state['status'], 'done')
        download = self.client.get(state['url'])
        self.assertEqual(download['Content-Type'], 'application/zip')
        names = sorted(zipfile.ZipFile(io.BytesIO(b''.join(download.streaming_content))).namelist())
        self.assertEqual(names, ['01-transport.csv', '01-transport.png', '03-where.csv', '03-where.png'])
