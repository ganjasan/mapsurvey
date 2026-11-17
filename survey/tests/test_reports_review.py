"""Spec: reports-review (change reports-review, #706, epic #712).

Before a report is published its author sees what it says about people — every picked quote, every
map of marks — and confirms it; the same dialog names what looks unfinished, with a fix, and takes
the audience and live-or-frozen. A map says what it shows; the preview has two widths.
"""
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_pro_org, make_v1_survey
from reports.checks import run
from reports.models import Report, ReportBlock
from survey.models import Answer, Question, SurveySession


class _Review(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org('ReviewOrg', 'reportreviewowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Riverside', status='published')
        self.choice = Question.objects.create(survey_section=self.section, code='PRIO', name='Top priority',
                                              input_type='choice', choices=[{'code': 1, 'name': 'Trees'}])
        self.spot = Question.objects.create(survey_section=self.section, code='SPOT', name='Where', input_type='point')
        for i in range(4):
            s = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(survey_session=s, question=self.choice, selected_choices=[1])
            Answer.objects.create(survey_session=s, question=self.spot, point=Point(30.0 + i * 1e-5, 59.0))
        self.report = Report.objects.create(survey=self.survey, slug='riverside-review',
                                            intro={'title': {'en': 'What we heard'}})
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.checks_url = reverse('editor_report_checks', args=[self.report.uuid])
        self.publish_url = reverse('editor_report_set_published', args=[self.report.uuid])

    def block(self, block_type, **fields):
        fields.setdefault('order', self.report.blocks.count())
        return ReportBlock.objects.create(report=self.report, block_type=block_type, **fields)

    def quotes(self, *texts, **fields):
        return self.block('quotes', config={'items': [{'text': t, 'source': 'Open answer'} for t in texts]}, **fields)

    def dialog(self):
        return self.client.get(self.checks_url).content.decode()

    def publish(self, **data):
        data.setdefault('publish', '1')
        return self.client.post(self.publish_url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def published(self):
        self.report.refresh_from_db()
        return self.report.is_published


class PeopleTest(_Review):
    """Requirement: The author sees what a report says about people before publishing."""

    def test_picked_quotes_are_named(self):
        """
        GIVEN a visible Quotes block with two quotes and a hidden one with three
        WHEN the publish dialog opens
        THEN it writes out the two quotes and none of the three
        """
        self.quotes('The bridge is gone.', 'Give us shade.')
        self.quotes('Hidden one.', 'Hidden two.', 'Hidden three.', is_hidden=True)
        html = self.dialog()
        self.assertIn('“The bridge is gone.”', html)
        self.assertIn('“Give us shade.”', html)
        self.assertNotIn('Hidden one.', html)
        self.assertIn('2 quotes will be published as written', html)

    def test_a_map_of_marks(self):
        """
        GIVEN a map block that shows marks
        WHEN the publish dialog opens
        THEN it names the block and says a mark can point at someone's home
        """
        self.block('map', question=self.spot, config={'marks': True})
        html = self.dialog()
        self.assertIn('data-check="marks"', html)
        self.assertIn('Where', html)
        self.assertIn('point at someone', html)

    def test_nothing_to_check(self):
        """
        GIVEN a report of a heading, a text and a chart with the threshold at 3
        WHEN the publish dialog opens
        THEN it says there is nothing to check
        """
        self.block('heading', content={'en': 'Priorities'})
        self.block('text', content={'en': '<p>Trees first.</p>'})
        self.block('chart', question=self.choice)
        self.assertTrue(run(self.report).clean)
        self.assertIn('data-testid="pr-checks-clean"', self.dialog())

    def test_a_threshold_of_one_is_listed_but_does_not_block(self):
        """
        GIVEN a report whose threshold is 1
        WHEN the dialog opens and the report is published without a confirmation
        THEN the dialog warns and the report is published
        """
        self.block('chart', question=self.choice)
        self.report.k_anonymity_threshold = 1
        self.report.save()
        self.assertIn('data-check="k"', self.dialog())
        self.assertEqual(self.publish().status_code, 200)
        self.assertTrue(self.published())


class ConfirmationTest(_Review):
    """Requirement: Quotes and marks are published only after a confirmation."""

    def test_without_the_confirmation(self):
        """
        GIVEN a report with a visible quote
        WHEN an editor publishes without ticking the confirmation
        THEN the report stays unpublished and the answer names what is missing
        """
        self.quotes('The bridge is gone.')
        self.assertIn('data-testid="pr-publish-ack"', self.dialog())
        response = self.publish()
        self.assertEqual((response.status_code, response.json()['error']), (400, 'ack_required'))
        self.assertFalse(self.published())

    def test_with_the_confirmation(self):
        """
        GIVEN the same report
        WHEN the editor ticks the confirmation and publishes
        THEN the report is published
        """
        self.quotes('The bridge is gone.')
        self.assertEqual(self.publish(ack='1').status_code, 200)
        self.assertTrue(self.published())

    def test_a_report_without_quotes_or_marks(self):
        """
        GIVEN a report of a chart and text
        WHEN an editor publishes through the survey's tab without a confirmation
        THEN it is published, and taking it down needs none either
        """
        self.block('chart', question=self.choice)
        self.assertNotIn('data-testid="pr-publish-ack"', self.dialog())
        url = reverse('editor_public_results_set_published', args=[self.survey.uuid])
        self.client.post(url, {'publish': '1'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(self.published())
        self.quotes('Added after publishing.')
        self.client.post(url, {'publish': '0'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertFalse(self.published())


class UnfinishedTest(_Review):
    """Requirement: The dialog names what looks unfinished and offers the fix."""

    def test_an_empty_block(self):
        """
        GIVEN a visible Quotes block with no quote
        WHEN the dialog opens, then its delete button is used
        THEN the list offers to delete the block, and afterwards no longer names it
        """
        empty = self.quotes()
        delete_url = reverse('editor_report_block_delete', args=[self.report.uuid, empty.pk])
        html = self.dialog()
        self.assertIn('data-check="empty"', html)
        self.assertIn(f'data-url="{delete_url}"', html)
        self.client.post(delete_url, HTTP_HX_REQUEST='true')
        self.assertNotIn('data-check="empty"', self.dialog())

    def test_a_map_nobody_described(self):
        """
        GIVEN a map block without a description, and a hidden block
        WHEN the dialog opens and the report is published
        THEN the list says so with a link to the block, counts the hidden block, and publishing works
        """
        block = self.block('map', question=self.spot)
        self.block('text', content={'en': '<p>Later.</p>'}, is_hidden=True)
        html = self.dialog()
        self.assertIn('data-check="map_description"', html)
        self.assertIn(f'?block={block.pk}', html)
        self.assertIn('1 hidden block will not be shown.', html)
        self.assertEqual(self.publish().status_code, 200)
        self.assertTrue(self.published())


class ChoicesTest(_Review):
    """Requirement: Publishing chooses audience and numbers."""

    def test_frozen_and_unlisted(self):
        """
        GIVEN a report with a live number
        WHEN an editor publishes choosing unlisted and frozen, and a fifth answer arrives
        THEN the report is published, unlisted, and still shows 4
        """
        self.block('text', content={'en': '<p>{responses} people answered.</p>'})
        self.publish(visibility='unlisted', mode='frozen')
        self.report.refresh_from_db()
        self.assertEqual((self.report.is_published, self.report.visibility, self.report.mode),
                         (True, 'unlisted', 'frozen'))
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.choice, selected_choices=[1])
        html = self.client.get(reverse('public_results', args=[self.report.slug])).content.decode()
        self.assertIn('4 people answered.', html)


class MapDescriptionTest(_Review):
    """Requirement: A map says what it shows."""

    def test_described(self):
        """
        GIVEN an editor gives a map block the description "Most marks sit along the river path"
        WHEN the page is opened
        THEN the sentence is under the map and is the map's accessible name
        """
        block = self.block('map', question=self.spot)
        self.client.post(reverse('editor_report_block_edit', args=[self.report.uuid, block.pk]),
                         {'content': 'Most marks sit along the river path', 'show_marks_present': '1'},
                         HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        html = self.client.get(reverse('editor_report_preview', args=[self.report.uuid])).content.decode()
        self.assertIn('role="img" aria-label="Most marks sit along the river path"', html)
        self.assertIn('<p class="block-note">Most marks sit along the river path</p>', html)
        self.assertNotIn('data-check="map_description"', self.dialog())


class PreviewTest(_Review):
    """Requirement: The preview shows a phone or a computer."""

    def test_the_two_widths(self):
        """
        GIVEN the report's editor
        WHEN the page is rendered
        THEN the canvas offers the phone and the computer width, and Publish opens the dialog
        """
        html = self.client.get(reverse('editor_report', args=[self.report.uuid])).content.decode()
        self.assertIn('data-width="mobile"', html)
        self.assertIn('data-width="desktop"', html)
        self.assertIn('data-rb-publish', html)
        self.assertIn(self.checks_url, html)
