"""Spec: reports-import-export (change reports-story, #704, epic #712).

A report leaves as a ZIP — `report.json` and its pictures — and comes back from one into a
workspace: unpublished, workspace-only, sanitised, its question blocks bound again by survey and
question code where the workspace has them.
"""
import io
import json
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_member, make_pro_org, make_v1_survey
from reports.models import Report, ReportBlock
from survey.models import Question

# A 1×1 PNG.
PNG = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
       b'\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82')


def report_zip(document, images=()):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('report.json', json.dumps(document))
        for path, data in images:
            archive.writestr(path, data)
    return SimpleUploadedFile('story.report.zip', buffer.getvalue(), content_type='application/zip')


class _Files(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org('FileOrg', 'reportfileowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Round one', status='published')
        self.question = Question.objects.create(
            survey_section=self.section, code='Q_PRIO', name='Top priority', input_type='choice',
            choices=[{'code': 1, 'name': 'Crossings'}, {'code': 2, 'name': 'Trees'}])
        self.login(self.owner, self.org)

    def login(self, user, org):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = org.id
        session.save()

    def make_report(self):
        report = Report.objects.create(
            survey=self.survey, slug='round-one-story', is_published=True, visibility='public',
            intro={'title': {'en': 'What we heard'}, 'body': {'en': 'In short.'}, 'eyebrow': {'en': 'Round one'}})
        ReportBlock.objects.create(report=report, block_type='heading', content={'en': 'Who answered'}, order=0)
        ReportBlock.objects.create(report=report, block_type='text', content={'en': '<p>Mostly <strong>new</strong> residents.</p>'}, order=1)
        ReportBlock.objects.create(report=report, block_type='image', content={'en': 'Every pin'}, order=2, width='half',
                                   image=SimpleUploadedFile('pins.png', PNG, content_type='image/png'))
        ReportBlock.objects.create(report=report, block_type='numbers', order=3, width='half',
                                   config={'items': [{'value': '447', 'label': 'residents answered'}]})
        ReportBlock.objects.create(report=report, block_type='quotes', order=4,
                                   config={'items': [{'text': 'Give us the bridge back.', 'source': 'Pin'}]})
        ReportBlock.objects.create(report=report, block_type='chart', question=self.question, viz='pie', order=5)
        return report

    def export(self, report):
        response = self.client.get(reverse('editor_report_export', args=[report.uuid]))
        self.assertEqual(response.status_code, 200)
        return response.content

    def upload(self, data):
        return self.client.post(reverse('editor_report_import'),
                                {'file': SimpleUploadedFile('r.report.zip', data, content_type='application/zip')})


class ExportTest(_Files):
    """Requirement: A report is exported as a file."""

    def test_exporting(self):
        """
        GIVEN a report with a heading, a text, a picture, key numbers, quotes and a chart
        WHEN an editor exports it
        THEN report.json lists the six blocks in order, the chart by survey and question code, and
             the ZIP holds the picture
        """
        archive = zipfile.ZipFile(io.BytesIO(self.export(self.make_report())))
        document = json.loads(archive.read('report.json'))
        self.assertEqual([b['type'] for b in document['blocks']],
                         ['heading', 'text', 'image', 'numbers', 'quotes', 'chart'])
        self.assertEqual((document['title'], document['eyebrow'], document['format']), ('What we heard', 'Round one', 1))
        chart = document['blocks'][5]
        self.assertEqual((chart['survey'], chart['question'], chart['viz']), (str(self.survey.uuid), 'Q_PRIO', 'pie'))
        self.assertNotIn(self.question.pk, chart.values())
        self.assertEqual(archive.read(document['blocks'][2]['image']), PNG)
        self.assertEqual(document['blocks'][2]['width'], 'half')

    def test_someone_who_may_not_edit(self):
        """
        GIVEN a member of another workspace
        WHEN they ask for the export
        THEN the answer is 404
        """
        report = self.make_report()
        other_org, other_owner = make_pro_org('OtherFileOrg', 'otherfileowner')
        self.login(other_owner, other_org)
        self.assertEqual(self.client.get(reverse('editor_report_export', args=[report.uuid])).status_code, 404)


class ImportTest(_Files):
    """Requirement: A report file is imported into a workspace."""

    def test_round_trip_in_the_same_workspace(self):
        """
        GIVEN an exported report
        WHEN the editor imports the file
        THEN a second report has the same opening and blocks in order, the chart still on its
             question, and is unpublished and workspace-only
        """
        original = self.make_report()
        response = self.upload(self.export(original))
        copy = Report.objects.exclude(pk=original.pk).get()
        self.assertRedirects(response, reverse('editor_report', args=[copy.uuid]))
        self.assertEqual((copy.is_published, copy.visibility, copy.survey_id), (False, 'workspace', self.survey.id))
        self.assertEqual(copy.intro['eyebrow'], {'en': 'Round one'})
        blocks = list(copy.blocks.all())
        self.assertEqual([b.block_type for b in blocks], ['heading', 'text', 'image', 'numbers', 'quotes', 'chart'])
        self.assertEqual((blocks[5].question_code, blocks[5].dataset.survey_id, blocks[5].viz),
                         ('Q_PRIO', self.survey.id, 'pie'))
        self.assertEqual((blocks[2].width, blocks[3].width), ('half', 'half'))
        with blocks[2].image.open('rb') as handle:
            self.assertEqual(handle.read(), PNG)
        self.assertEqual(original.blocks.count(), 6)

    def test_into_a_workspace_without_the_survey(self):
        """
        GIVEN a report file from another workspace
        WHEN it is imported
        THEN the story blocks and the picture arrive, the chart is left out, and the member is told
        """
        data = self.export(self.make_report())
        other_org, other_owner = make_pro_org('TargetFileOrg', 'targetfileowner')
        self.login(other_owner, other_org)
        response = self.client.post(
            reverse('editor_report_import'),
            {'file': SimpleUploadedFile('r.report.zip', data, content_type='application/zip')}, follow=True)
        copy = Report.objects.get(organization=other_org)
        self.assertEqual([b.block_type for b in copy.blocks.all()], ['heading', 'text', 'image', 'numbers', 'quotes'])
        self.assertEqual(copy.survey_id, None)
        self.assertContains(response, 'this workspace does not have')

    def test_a_report_made_by_hand(self):
        """
        GIVEN a file with an opening, key numbers, a heading, text with a numbered list, a picture
              with a caption, two half-width blocks and quotes
        WHEN it is imported and its preview is opened
        THEN the page shows them in that order, and each block opens in the editor
        """
        document = {'format': 1, 'title': 'Remington, in its own words', 'eyebrow': 'Survey report',
                    'lead': '447 residents answered.', 'visibility': 'public', 'k': 3, 'survey': None,
                    'blocks': [
                        {'type': 'numbers', 'width': 'full', 'items': [{'value': '447', 'label': 'residents answered'}],
                         'note': 'Online and paper together.'},
                        {'type': 'heading', 'width': 'full', 'text': 'One bridge'},
                        {'type': 'text', 'width': 'full', 'html': '<p>No place gets more attention.</p><ol><li><strong>The bridge</strong> first.</li></ol>'},
                        {'type': 'image', 'width': 'half', 'image': 'images/000.png', 'caption': 'Every pin'},
                        {'type': 'quotes', 'width': 'half', 'items': [{'text': 'Give us the bridge back.', 'source': 'Pin: needs attention'}]},
                    ]}
        self.client.post(reverse('editor_report_import'), {'file': report_zip(document, [('images/000.png', PNG)])})
        report = Report.objects.get()
        self.assertEqual((report.visibility, report.is_published, report.title),
                         ('workspace', False, 'Remington, in its own words'))
        html = self.client.get(reverse('editor_report_preview', args=[report.uuid])).content.decode()
        html = html[html.index('<body'):]
        marks = ['Survey report', 'Remington, in its own words', '447 residents answered.', '<b>447</b>',
                 'Online and paper together.', 'One bridge', '<li><strong>The bridge</strong> first.</li>',
                 'Every pin', 'Give us the bridge back.', '<cite>Pin: needs attention</cite>']
        positions = [html.index(m) for m in marks]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(html.count('class="row pair"'), 1)
        for block in report.blocks.all():
            page = self.client.get(reverse('editor_report', args=[report.uuid]) + f'?block={block.id}')
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, reverse('editor_report_block_edit', args=[report.uuid, block.id]))

    def test_script_in_an_imported_text(self):
        """
        GIVEN a file whose text block carries a script element
        WHEN it is imported
        THEN the stored text and the page carry no script
        """
        document = {'format': 1, 'title': 'T', 'blocks': [
            {'type': 'text', 'html': '<p>Fine.</p><script>alert("x")</script><img src=x onerror="alert(1)">'}]}
        self.client.post(reverse('editor_report_import'), {'file': report_zip(document)})
        block = ReportBlock.objects.get()
        self.assertNotIn('script', block.content['en'])
        self.assertNotIn('onerror', block.content['en'])

    def test_not_a_report_file(self):
        """
        GIVEN a ZIP without report.json, a file that is not a ZIP, and a report.json of an unknown format
        WHEN an editor uploads each
        THEN each is refused with a message and no report is created
        """
        empty = io.BytesIO()
        with zipfile.ZipFile(empty, 'w') as archive:
            archive.writestr('readme.txt', 'hello')
        unknown = io.BytesIO()
        with zipfile.ZipFile(unknown, 'w') as archive:
            archive.writestr('report.json', json.dumps({'format': 99, 'blocks': []}))
        for data in (empty.getvalue(), b'not a zip at all', unknown.getvalue()):
            response = self.client.post(
                reverse('editor_report_import'),
                {'file': SimpleUploadedFile('x.zip', data, content_type='application/zip')}, follow=True)
            self.assertRedirects(response, reverse('editor_reports'))
            self.assertTrue([m for m in response.context['messages'] if m.level_tag == 'error'])
        self.assertFalse(Report.objects.exists())

    def _live_report(self):
        from reports import services
        from survey.services.context import Actor
        age = Question.objects.create(survey_section=self.section, code='Q_AGE', name='Age', input_type='choice',
                                      choices=[{'code': 1, 'name': 'Under 30'}, {'code': 2, 'name': 'Over 60'}])
        where = Question.objects.create(survey_section=self.section, code='Q_WHERE', name='Where', input_type='point')
        report = Report.objects.create(survey=self.survey, slug='live-story', intro={'title': {'en': 'Live'}})
        actor = Actor(user=self.owner, ip=None, surface='editor')
        services.add_view_block(actor, report, 'crosstab', self.survey, rows='Q_PRIO', columns=age.code)
        services.add_view_block(actor, report, 'engagement', self.survey)
        ReportBlock.objects.create(report=report, block_type='map', question=where, config={'marks': True}, order=2)
        return report

    def test_round_trip_of_a_crosstab_and_a_map_with_marks(self):
        """
        GIVEN a report with a cross-tab, an engagement block and a map showing marks
        WHEN it is exported and imported in the same workspace
        THEN the copy has the three blocks, the cross-tab on the same questions, the map still showing marks
        """
        original = self._live_report()
        self.upload(self.export(original))
        copy = Report.objects.exclude(pk=original.pk).get()
        blocks = list(copy.blocks.select_related('view'))
        self.assertEqual([b.block_type for b in blocks], ['crosstab', 'engagement', 'map'])
        self.assertEqual(blocks[0].view.config, {'rows': 'Q_PRIO', 'columns': 'Q_AGE'})
        self.assertEqual(blocks[1].view.kind, 'engagement')
        self.assertEqual(blocks[2].config, {'marks': True})

    def test_live_blocks_into_a_workspace_without_the_survey(self):
        """
        GIVEN that file
        WHEN it is imported into another workspace
        THEN the three blocks are left out and the member is told
        """
        data = self.export(self._live_report())
        other_org, other_owner = make_pro_org('LiveTargetOrg', 'livetargetowner')
        self.login(other_owner, other_org)
        response = self.client.post(
            reverse('editor_report_import'),
            {'file': SimpleUploadedFile('r.report.zip', data, content_type='application/zip')}, follow=True)
        copy = Report.objects.get(organization=other_org)
        self.assertEqual(copy.blocks.count(), 0)
        self.assertContains(response, 'this workspace does not have')

    def test_a_viewer(self):
        """
        GIVEN a viewer of the workspace
        WHEN they post a report file
        THEN the answer is 404 and no report is created
        """
        self.login(make_member(self.org, 'fileviewer', role='viewer'), self.org)
        document = {'format': 1, 'title': 'T', 'blocks': []}
        response = self.client.post(reverse('editor_report_import'), {'file': report_zip(document)})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Report.objects.exists())
