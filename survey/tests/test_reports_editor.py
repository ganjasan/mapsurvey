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


class BlockRowTest(_Editor):
    """Requirement: A block's row names its type."""

    def _rows(self, **extra):
        html = self.client.get(self.url('editor_report'), **extra).content.decode()
        return html[html.index('id="pr-blocks-list"'):] if 'id="pr-blocks-list"' in html else html

    def test_a_titled_block_names_its_type_in_the_interface_language(self):
        """
        GIVEN a Key numbers block titled "Who took part"
        WHEN an editor whose interface is German opens the report
        THEN the row reads the title with "Kennzahlen" under it, and the key "numbers" is not shown
        """
        ReportBlock.objects.create(report=self.report, block_type='numbers', order=0,
                                   custom_title={'en': 'Who took part'},
                                   config={'items': [{'value': '112', 'label': 'answered'}]})
        rows = self._rows(HTTP_ACCEPT_LANGUAGE='de')
        self.assertIn('<span class="pr-block-name">Who took part</span>', rows)
        self.assertIn('<span class="pr-block-type">Kennzahlen</span>', rows)
        self.assertNotIn('>numbers<', rows)

    def test_a_block_without_a_title_reads_its_type_once(self):
        """
        GIVEN a Quotes block with no title of its own
        WHEN the editor lists the report's blocks
        THEN the row's title is the type's name and no second line repeats it
        """
        ReportBlock.objects.create(report=self.report, block_type='quotes', order=0,
                                   config={'items': [{'quote': 'More benches.', 'source': ''}]})
        rows = self._rows()
        self.assertIn('<span class="pr-block-name">Quotes</span>', rows)
        self.assertNotIn('pr-block-type">', rows)


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

    def test_delete_in_the_list(self):
        """
        GIVEN an editor on the Reports list
        WHEN the list renders
        THEN the report's row carries a Delete action that leads to the page saying what goes
        """
        html = self.client.get(reverse('editor_reports')).content.decode()
        self.assertIn(self.url('editor_report_delete') + '?from=list', html)
        self.assertIn('data-testid="report-delete"', html)

    def test_a_member_who_may_not_edit(self):
        """
        GIVEN a viewer of the workspace
        WHEN they open the Reports list
        THEN no row offers Delete
        """
        viewer = make_member(self.org, 'reportlistviewer', role='viewer')
        self.login(viewer, self.org)
        html = self.client.get(reverse('editor_reports')).content.decode()
        self.assertIn('Blank one', html)
        self.assertNotIn('data-testid="report-delete"', html)

    def test_a_report_made_from_a_survey(self):
        """
        GIVEN a report whose home is a survey, the one the survey's Public results tab opens
        WHEN an editor opens its settings and then the delete page
        THEN "Delete report…" is offered and the page says what the tab will open afterwards
        """
        survey, _section = make_v1_survey(self.org, self.owner)
        self.report.survey = survey
        self.report.save()
        page = self.client.get(self.url('editor_report'))
        self.assertContains(page, self.url('editor_report_delete'))
        page = self.client.get(self.url('editor_report_delete'))
        self.assertContains(page, 'data-testid="report-delete-home"')
        self.client.post(self.url('editor_report_delete'))
        self.assertFalse(Report.objects.filter(pk=self.report.pk).exists())


class CanvasTest(_Editor):
    """Requirement: The report is the editor's canvas."""

    def test_opening_a_report(self):
        """
        GIVEN a report with a heading and a key-numbers block
        WHEN an editor opens it
        THEN the page draws both blocks under the report's opening, the outline lists them, the
             panel shows the report's settings, and there is no preview frame
        """
        heading = ReportBlock.objects.create(report=self.report, block_type='heading', content={'en': 'Who took part'}, order=0)
        numbers = ReportBlock.objects.create(report=self.report, block_type='numbers', order=1,
                                             config={'items': [{'value': '447', 'label': 'residents answered'}]})
        html = self.client.get(self.url('editor_report')).content.decode()
        opening, first, second = (html.index('data-page-field="intro_title"'), html.index(f'id="block-{heading.pk}"'),
                                  html.index(f'id="block-{numbers.pk}"'))
        self.assertTrue(opening < first < second)
        self.assertIn('<h2 data-field="content" data-placeholder="Heading">Who took part</h2>', html)
        self.assertIn('data-row-field="value" data-placeholder="447">447</b>', html)
        self.assertEqual(html.count('class="lb-oi rb-oi'), 2)
        self.assertIn('data-selected="page"', html)
        self.assertIn('<div class="lb-pane" data-pane="page" id="lb-page-pane">', html)
        self.assertNotIn('<iframe', html)

    def test_a_block_is_selected_by_its_address(self):
        """
        GIVEN a report with two blocks
        WHEN the editor is opened with ?block=<id> of the second
        THEN that block is selected and its settings are the visible pane
        """
        ReportBlock.objects.create(report=self.report, block_type='heading', content={'en': 'A'}, order=0)
        text = ReportBlock.objects.create(report=self.report, block_type='text', order=1)
        html = self.client.get(self.url('editor_report') + f'?block={text.pk}').content.decode()
        self.assertIn(f'data-selected="{text.pk}"', html)
        self.assertIn(f'<div class="lb-pane" data-pane="{text.pk}">', html)
        self.assertIn('data-pane="page" id="lb-page-pane" hidden', html)

    def test_the_same_builder_through_the_survey(self):
        """
        GIVEN a survey with its report
        WHEN an editor opens the survey's Public results tab
        THEN the same builder opens, with the way back to the survey
        """
        survey, _section = make_v1_survey(self.org, self.owner, name='Round one', status='published')
        page = self.client.get(reverse('editor_survey_public_results', args=[survey.uuid]))
        self.assertTemplateUsed(page, 'reports/builder.html')
        self.assertContains(page, reverse('editor_survey_detail', args=[survey.uuid]))

    def test_a_plan_without_reports_reads_only(self):
        """
        GIVEN a workspace whose plan has no Reports
        WHEN an editor opens a report with a text block
        THEN the canvas shows it without editing controls and the panel's fields are disabled
        """
        from unittest import mock
        ReportBlock.objects.create(report=self.report, block_type='text', content={'en': '<p>Hello</p>'}, order=0)
        with mock.patch('reports.gate.may_write', return_value=False):
            html = self.client.get(self.url('editor_report')).content.decode()
        self.assertIn('data-may-edit=""', html)
        self.assertNotIn('class="lb-tools"', html)
        self.assertNotIn('data-add-after', html)
        self.assertIn('<fieldset disabled>', html)


class WritingOnThePageTest(_Editor):
    """Requirement: Words are written on the page."""

    def save(self, block, data):
        return self.client.post(self.url('editor_report_block_edit', block.pk), dict(data, autosave='1'),
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_key_numbers_row_by_row(self):
        """
        GIVEN a key-numbers block
        WHEN the builder saves it with two rows
        THEN the block holds the two numbers in that order and the answer carries the block,
             its outline row and its settings pane as they are now drawn
        """
        block = ReportBlock.objects.create(report=self.report, block_type='numbers', order=0)
        r = self.save(block, {'rows': '1', 'value': ['447', '77'], 'label': ['residents answered', 'paper questionnaires'],
                              'custom_title': 'Who took part', 'content': '', 'width': 'full'})
        self.assertEqual(r.status_code, 200, r.content)
        block.refresh_from_db()
        self.assertEqual(block.config['items'], [{'value': '447', 'label': 'residents answered'},
                                                 {'value': '77', 'label': 'paper questionnaires'}])
        body = r.json()
        self.assertTrue(body['ok'])
        self.assertIn('>77</b><span data-row-field="label"', body['block'])
        self.assertIn('<span class="pr-block-name">Who took part</span>', body['outline'])
        self.assertIn(f'data-pane="{block.pk}"', body['panel'])

    def test_a_number_that_follows_the_answers(self):
        """
        GIVEN a key number written as a live-number token in a report of a survey
        WHEN the builder draws the block
        THEN the page shows the number and keeps the token for editing
        """
        survey, _section = make_v1_survey(self.org, self.owner, name='Round one', status='published')
        report = Report.objects.create(survey=survey, slug='round-one-report')
        block = ReportBlock.objects.create(report=report, block_type='numbers', order=0,
                                           config={'items': [{'value': '{responses}', 'label': 'answered'}]})
        html = self.client.get(reverse('editor_report', args=[report.uuid])).content.decode()
        self.assertIn('data-raw="{responses}"', html)
        self.assertIn('data-placeholder="447">0</b>', html)
        block.refresh_from_db()
        self.assertEqual(block.config['items'][0]['value'], '{responses}')

    def test_a_question_blocks_title_left_alone(self):
        """
        GIVEN a chart block of a question, with no title of its own
        WHEN the builder saves the block with the title untouched
        THEN the block keeps no title, the canvas shows the question's name as the placeholder and
             readers see the question's name
        """
        from survey.models import Question
        survey, section = make_v1_survey(self.org, self.owner, name='Round one', status='published')
        question = Question.objects.create(survey_section=section, code='MODE', name='How do you get here?',
                                           input_type='choice', choices=[{'code': 'a', 'name': {'en': 'On foot'}}])
        report = Report.objects.create(survey=survey, slug='round-one-report')
        block = ReportBlock.objects.create(report=report, block_type='chart', question=question, order=0)
        r = self.client.post(reverse('editor_report_block_edit', args=[report.uuid, block.pk]),
                             {'autosave': '1', 'custom_title': '', 'viz': 'pie', 'width': 'full'},
                             HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        block.refresh_from_db()
        self.assertEqual((block.custom_title, block.viz), ({'en': ''}, 'pie'))
        self.assertIn('data-placeholder="How do you get here?" class="rb-default-title"></h2>', r.json()['block'])
        self.assertIn('data-results', r.json()['block'])
        preview = self.client.get(reverse('editor_report_preview', args=[report.uuid])).content.decode()
        self.assertIn('<h2>How do you get here?</h2>', preview)

    def test_the_opening(self):
        """
        GIVEN a report
        WHEN the builder saves the opening with a new title and paragraph
        THEN the report's title is the new one and the answer carries the opening as it is now drawn
        """
        r = self.client.post(self.url('editor_report_save'),
                             {'autosave': '1', 'intro_eyebrow': 'Park plan · 2027', 'intro_title': 'What we heard',
                              'intro_body': 'Three weeks of answers.', 'visibility': 'workspace',
                              'k_anonymity_threshold': '3', 'slug': self.report.slug},
                             HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200, r.content)
        self.report.refresh_from_db()
        self.assertEqual(self.report.title, 'What we heard')
        body = r.json()
        self.assertEqual(body['title'], 'What we heard')
        self.assertIn('data-page-field="intro_title" data-placeholder="blank-one">What we heard</h1>', body['hero'])
        self.assertIn('Park plan · 2027', body['hero'])

    def test_an_address_that_is_taken(self):
        """
        GIVEN another report at the address "taken"
        WHEN the builder saves this report's settings with that address
        THEN the answer names the address as the problem and the report keeps its own
        """
        Report.objects.create(organization=self.org, slug='taken')
        r = self.client.post(self.url('editor_report_save'),
                             {'autosave': '1', 'intro_title': 'Blank one', 'intro_body': '', 'visibility': 'workspace',
                              'k_anonymity_threshold': '3', 'slug': 'taken'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 422)
        self.assertIn('slug', r.json()['errors'])
        self.report.refresh_from_db()
        self.assertEqual(self.report.slug, 'blank-one')


class LibraryTest(_Editor):
    """Requirement: Blocks are added from a library, where they are wanted."""

    def test_a_block_between_two_others(self):
        """
        GIVEN a report with three blocks
        WHEN an editor adds a text block after the first
        THEN the blocks are the first, the new one, then the other two, and the editor opens
             with the new block selected
        """
        first, second, third = [ReportBlock.objects.create(report=self.report, block_type='heading',
                                                           content={'en': name}, order=i)
                                for i, name in enumerate('ABC')]
        r = self.client.post(self.url('editor_report_block_add'), {'block_type': 'text', 'after': str(first.pk)})
        new = ReportBlock.objects.get(report=self.report, block_type='text')
        self.assertRedirects(r, self.url('editor_report') + f'?block={new.pk}')
        self.assertEqual(list(self.report.blocks.values_list('pk', flat=True)), [first.pk, new.pk, second.pk, third.pk])
        top = self.client.post(self.url('editor_report_block_add'), {'block_type': 'quotes', 'after': 'top'})
        self.assertEqual(top.status_code, 302)
        self.assertEqual(self.report.blocks.first().block_type, 'quotes')

    def test_a_questions_chart_in_one_click(self):
        """
        GIVEN a report of a survey with a choice question and a free-text question
        WHEN an editor opens the library and picks the choice question
        THEN the library offered the choice question only, and a chart block of it is added
        """
        from survey.models import Question
        survey, section = make_v1_survey(self.org, self.owner, name='Round one', status='published')
        choice = Question.objects.create(survey_section=section, code='MODE', name='How do you get here?',
                                         input_type='choice', choices=[{'code': 'a', 'name': {'en': 'On foot'}}])
        Question.objects.create(survey_section=section, code='WHY', name='Tell us why', input_type='text', order_number=1)
        report = Report.objects.create(survey=survey, slug='round-one-report')
        html = self.client.get(reverse('editor_report', args=[report.uuid])).content.decode()
        self.assertIn(f'name="question_id" value="{choice.pk}"', html)
        self.assertEqual(html.count('name="question_id"'), 1)
        self.client.post(reverse('editor_report_block_add', args=[report.uuid]), {'question_id': choice.pk})
        block = ReportBlock.objects.get(report=report)
        self.assertEqual((block.block_type, block.question_code), ('chart', 'MODE'))

    def test_a_picture_block_without_a_picture(self):
        """
        GIVEN a report
        WHEN an editor adds a picture block and uploads nothing
        THEN the block exists, the canvas offers to drop a file on it, and the page leaves it out
        """
        self.client.post(self.url('editor_report_block_add'), {'block_type': 'image'})
        block = ReportBlock.objects.get(report=self.report)
        self.assertFalse(block.image)
        html = self.client.get(self.url('editor_report')).content.decode()
        self.assertIn('class="lb-drop" data-file="image"', html)
        preview = self.client.get(self.url('editor_report_preview')).content.decode()
        self.assertNotIn(f'data-block-id="{block.pk}"', preview)


class UnseenBlockTest(_Editor):
    """Requirement: A block readers do not see says why."""

    def test_a_hidden_block(self):
        """
        GIVEN a text block marked hidden
        WHEN the builder and the report's page are drawn
        THEN the canvas shows the block with a note that readers do not see it, and the page leaves it out
        """
        block = ReportBlock.objects.create(report=self.report, block_type='text', content={'en': '<p>Kept for later</p>'},
                                           is_hidden=True, order=0)
        html = self.client.get(self.url('editor_report')).content.decode()
        self.assertIn('Kept for later', html)
        self.assertIn('Hidden: readers do not see this block.', html)
        self.assertIn('data-shown="0"', html)
        self.assertNotIn(f'data-block-id="{block.pk}"', self.client.get(self.url('editor_report_preview')).content.decode())

    def test_an_empty_quotes_block(self):
        """
        GIVEN a quotes block with no quote
        WHEN the builder is drawn
        THEN the canvas shows it with a note that it is left out until it has one
        """
        ReportBlock.objects.create(report=self.report, block_type='quotes', order=0)
        html = self.client.get(self.url('editor_report')).content.decode()
        self.assertIn('Left out of the report until it has a quote.', html)
        self.assertIn('data-rows="quotes"', html)
