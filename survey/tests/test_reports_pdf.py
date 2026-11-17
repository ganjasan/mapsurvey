"""Spec: reports-pdf (change reports-pdf, #707, epic #712).

A report as an A4 PDF laid out from the page's own payload, rendered on the worker and never in a
web request; a frozen report's PDF is made once and offered on its page.
"""
import io
from unittest import mock

from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader

from api.tests.helpers import make_pro_org, make_v1_survey
from reports import services
from reports.models import Report, ReportBlock, ReportPdf
from reports.pdf import build_pdf
from reports.tasks import render_report_pdf
from survey.models import Answer, Question, SurveySession
from survey.services.context import Actor

PNG = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
       b'\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82')


def text_of(data):
    return '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(data)).pages)


class _Pdf(TestCase):
    """A survey of two choice questions and a point question, a report over all of it. The basemap
    service is never called: `fetch_basemap` answers None."""

    def setUp(self):
        patcher = mock.patch('survey.print.static_map.fetch_basemap', return_value=None)
        self.fetch = patcher.start()
        self.addCleanup(patcher.stop)
        self.org, self.owner = make_pro_org('PdfOrg', 'reportpdfowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Riverside', status='published')
        self.transport = Question.objects.create(survey_section=self.section, code='TRANSPORT', name='Transport',
                                                 input_type='choice',
                                                 choices=[{'code': 1, 'name': 'Car'}, {'code': 2, 'name': 'Bike'}])
        self.age = Question.objects.create(survey_section=self.section, code='AGE', name='Age', input_type='choice',
                                           choices=[{'code': 1, 'name': 'Under 30'}, {'code': 2, 'name': 'Over 60'}])
        self.spot = Question.objects.create(survey_section=self.section, code='SPOT', name='Where', input_type='point')
        self.respond(4, 1, 1)
        self.respond(1, 2, 1)
        self.actor = Actor(user=self.owner, ip=None, surface='editor')
        self.report = Report.objects.create(survey=self.survey, slug='riverside-paper', is_published=True,
                                            intro={'title': {'en': 'What we heard'}, 'body': {'en': 'In short.'},
                                                   'eyebrow': {'en': 'Survey report'}})
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.pdf_url = reverse('editor_report_pdf', args=[self.report.uuid])

    def respond(self, n, transport, age):
        for i in range(n):
            s = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(survey_session=s, question=self.transport, selected_choices=[transport])
            Answer.objects.create(survey_session=s, question=self.age, selected_choices=[age])
            Answer.objects.create(survey_session=s, question=self.spot, point=Point(30.0 + i * 1e-5, 59.0))

    def block(self, block_type, **fields):
        fields.setdefault('order', self.report.blocks.count())
        return ReportBlock.objects.create(report=self.report, block_type=block_type, **fields)

    def full_report(self):
        self.block('heading', content={'en': 'Getting around'})
        self.block('text', content={'en': '<p>{responses} people answered.</p><ol><li>Crossings first.</li><li>Then shade.</li></ol>'})
        self.block('numbers', config={'items': [{'value': '{marks:SPOT}', 'label': 'places pinned'}]})
        self.block('quotes', config={'items': [{'text': 'Give us the bridge back.', 'source': 'Pin: needs attention'}]})
        self.block('image', content={'en': 'Every pin'}, image=SimpleUploadedFile('pins.png', PNG, content_type='image/png'))
        self.block('chart', question=self.transport)
        services.add_view_block(self.actor, self.report, 'engagement', self.survey)
        services.add_view_block(self.actor, self.report, 'crosstab', self.survey, rows='TRANSPORT', columns='AGE')
        self.block('map', question=self.spot, content={'en': 'Most marks sit by the river.'})


class DocumentTest(_Pdf):
    """Requirement: A report is laid out as an A4 document from the page's own numbers."""

    def test_the_numbers_equal_the_page(self):
        """
        GIVEN a report with a live number, frozen at 5 answers, and a sixth answer afterwards
        WHEN the PDF is built
        THEN its text holds 5, as the frozen page does
        """
        self.block('text', content={'en': '<p>{responses} people answered.</p>'})
        self.block('chart', question=self.transport)
        services.freeze(self.actor, self.report)
        self.respond(1, 1, 1)
        text = text_of(build_pdf(self.report, base_url='https://example.org'))
        self.assertIn('5 people answered.', text)
        page = self.client.get(reverse('public_results', args=[self.report.slug])).content.decode()
        self.assertIn('5 people answered.', page)

    def test_a_masked_cell(self):
        """
        GIVEN a cross-tab with one respondent in Bike and Under 30, K = 3
        WHEN the PDF is built
        THEN it reads "<3" in the table and withholds the totals that would give it away
        """
        services.add_view_block(self.actor, self.report, 'crosstab', self.survey, rows='TRANSPORT', columns='AGE')
        text = text_of(build_pdf(self.report))
        self.assertIn('<3', text)
        self.assertIn('—', text)
        self.assertIn('Groups too small to show', text)

    def test_every_block_kind(self):
        """
        GIVEN a report with a heading, text with a list, key numbers, quotes, a picture, a chart,
              an engagement block, a cross-tab and a map
        WHEN the PDF is built
        THEN it is a PDF whose text holds each of them and the address in the footer
        """
        self.full_report()
        data = build_pdf(self.report, base_url='https://example.org')
        self.assertTrue(data.startswith(b'%PDF'))
        text = text_of(data)
        for expected in ('SURVEY REPORT', 'What we heard', 'In short.', 'Getting around', '5 people answered.',
                         'Crossings first.', 'places pinned', 'Give us the bridge back.', 'Pin: needs attention',
                         'Every pin', 'Car', 'opened the survey', 'Under 30', 'Most marks sit by the river.',
                         'https://example.org/r/riverside-paper/', 'page 1'):
            self.assertIn(expected, text, expected)

    def test_hidden_blocks_stay_out(self):
        """
        GIVEN a report with a hidden text block
        WHEN the PDF is built
        THEN its text is not in the PDF
        """
        self.block('text', content={'en': '<p>Shown.</p>'})
        self.block('text', content={'en': '<p>Not for readers.</p>'}, is_hidden=True)
        text = text_of(build_pdf(self.report))
        self.assertIn('Shown.', text)
        self.assertNotIn('Not for readers.', text)


class MapTest(_Pdf):
    """Requirement: A map is drawn without a browser."""

    def test_no_basemap_service(self):
        """
        GIVEN the basemap cannot be fetched
        WHEN a report with a grid map and a map of marks is built
        THEN the PDF is produced with a picture for each map
        """
        from reports.pdf import map_image
        from reports.render import ReportService
        grid = self.block('map', question=self.spot)
        marks = self.block('map', question=self.spot, config={'marks': True})
        service = ReportService(self.report)
        for block in (grid, marks):
            image = map_image(service._build_block(block), self.survey)
            self.assertEqual(image.size, (1800, 1040))
        self.assertTrue(build_pdf(self.report).startswith(b'%PDF'))
        self.assertTrue(self.fetch.called)


class JobTest(_Pdf):
    """Requirement: The PDF is rendered on the worker."""

    def test_asking_returns_a_job(self):
        """
        GIVEN a 20-block report and a broker that takes the task
        WHEN an editor asks for the PDF
        THEN the answer names a queued job and nothing was rendered in the request
        """
        for i in range(20):
            self.block('heading', content={'en': f'Section {i}'})
        with mock.patch('reports.tasks.render_report_pdf.delay') as delay, \
                mock.patch('reports.pdf.build_pdf') as build:
            response = self.client.post(self.pdf_url)
        job = ReportPdf.objects.get()
        self.assertEqual((response.status_code, response.json()['status'], response.json()['job']),
                         (202, 'queued', job.pk))
        delay.assert_called_once()
        build.assert_not_called()

    def test_the_job_finishes(self):
        """
        GIVEN a queued job
        WHEN the worker runs the task
        THEN the job is done and its download serves a PDF to the editor
        """
        self.block('heading', content={'en': 'Getting around'})
        with mock.patch('reports.tasks.render_report_pdf.delay'):
            job_id = self.client.post(self.pdf_url).json()['job']
        render_report_pdf(job_id, 'https://example.org')
        state = self.client.get(self.pdf_url, {'job': job_id}).json()
        self.assertEqual(state['status'], 'done')
        download = self.client.get(state['url'])
        self.assertEqual(download['Content-Type'], 'application/pdf')
        self.assertIn('Getting around', text_of(b''.join(download.streaming_content)))

    def test_delivered_twice(self):
        """
        GIVEN a job that was already rendered
        WHEN the same task message arrives again
        THEN nothing is rendered a second time
        """
        with mock.patch('reports.tasks.render_report_pdf.delay'):
            job_id = self.client.post(self.pdf_url).json()['job']
        render_report_pdf(job_id)
        with mock.patch('reports.pdf.build_pdf') as build:
            render_report_pdf(job_id)
        build.assert_not_called()

    def test_a_failure_is_reported(self):
        """
        GIVEN rendering raises
        WHEN the task runs
        THEN the job is failed and the poll says so
        """
        with mock.patch('reports.tasks.render_report_pdf.delay'):
            job_id = self.client.post(self.pdf_url).json()['job']
        with mock.patch('reports.pdf.build_pdf', side_effect=RuntimeError('boom')):
            render_report_pdf(job_id)
        state = self.client.get(self.pdf_url, {'job': job_id}).json()
        self.assertEqual((state['status'], state['error'], state['url']), ('failed', True, ''))


class FrozenTest(_Pdf):
    """Requirement: A frozen report's PDF is made once and offered on its page."""

    def ask(self):
        with mock.patch('reports.tasks.render_report_pdf.delay', side_effect=lambda pk, base='': render_report_pdf(pk, base)):
            return self.client.post(self.pdf_url).json()['job']

    def test_rendered_once(self):
        """
        GIVEN a frozen report
        WHEN an editor asks twice for its PDF
        THEN both answers name the same job
        """
        self.block('heading', content={'en': 'Getting around'})
        services.freeze(self.actor, self.report)
        self.assertEqual(self.ask(), self.ask())
        self.assertEqual(ReportPdf.objects.count(), 1)

    def test_the_link_on_the_page(self):
        """
        GIVEN a published, frozen report whose PDF was made
        WHEN an anonymous visitor opens its page and follows the PDF link
        THEN the page links to the PDF and the link serves the file
        """
        self.block('heading', content={'en': 'Getting around'})
        services.freeze(self.actor, self.report)
        self.ask()
        self.client.logout()
        link = reverse('report_page_pdf', args=[self.report.slug])
        self.assertContains(self.client.get(reverse('public_results', args=[self.report.slug])), link)
        response = self.client.get(link)
        self.assertEqual((response.status_code, response['Content-Type']), (200, 'application/pdf'))

    def test_a_live_report(self):
        """
        GIVEN a published live report whose PDF was made, twice
        WHEN its page and the public PDF address are opened
        THEN each request was its own rendering, the page has no PDF link and the address is 404
        """
        self.block('heading', content={'en': 'Getting around'})
        self.assertNotEqual(self.ask(), self.ask())
        link = reverse('report_page_pdf', args=[self.report.slug])
        self.assertNotContains(self.client.get(reverse('public_results', args=[self.report.slug])), link)
        self.assertEqual(self.client.get(link).status_code, 404)

    def test_a_workspace_only_report(self):
        """
        GIVEN a workspace-only frozen report with a stored PDF
        WHEN an anonymous visitor asks for the PDF
        THEN they are sent to sign in
        """
        self.block('heading', content={'en': 'Getting around'})
        self.report.visibility = 'workspace'
        self.report.save()
        services.freeze(self.actor, self.report)
        self.ask()
        self.client.logout()
        response = self.client.get(reverse('report_page_pdf', args=[self.report.slug]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])


class RightsTest(_Pdf):
    """Requirement: Only editors ask for a PDF."""

    def test_a_stranger(self):
        """
        GIVEN a member of another workspace
        WHEN they post to the report's PDF address
        THEN the answer is 404 and no job is created
        """
        other_org, other_owner = make_pro_org('OtherPdfOrg', 'otherpdfowner')
        self.client.force_login(other_owner)
        session = self.client.session
        session['active_org_id'] = other_org.id
        session.save()
        self.assertEqual(self.client.post(self.pdf_url).status_code, 404)
        self.assertFalse(ReportPdf.objects.exists())
