"""Spec: reports-reuse (change reports-reuse, #711, epic #712).

A report is copied onto another survey — the next round — with its data blocks rebound by
question code and the blocks that found no question named; a Compare block shows one question in
two rounds.
"""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import V1Client, make_pro_org, make_v1_survey, mint
from reports import drafting, services
from reports.models import Report, ReportBlock
from reports.render import ReportService
from reports.tables import rows_of
from survey.models import Answer, Question, SurveySession
from survey.services.context import Actor

CHOICES = [{'code': 1, 'name': 'Trees'}, {'code': 2, 'name': 'Benches'}]


class _Rounds(TestCase):
    def setUp(self):
        cache.clear()
        self.org, self.owner = make_pro_org('RoundsOrg', 'roundsowner')
        self.actor = Actor(user=self.owner, ip=None, surface='editor')
        self.one, self.prio1 = self.round('Round one', {1: 6, 2: 4})
        self.two, self.prio2 = self.round('Round two', {1: 3, 2: 9})

    def round(self, name, votes, extra=()):
        survey, section = make_v1_survey(self.org, self.owner, name=name, status='published')
        prio = Question.objects.create(survey_section=section, code='PRIO', name='Top priority',
                                       input_type='choice', choices=CHOICES)
        for code in extra:
            Question.objects.create(survey_section=section, code=code, name=code.title(), input_type='choice',
                                    choices=[{'code': 1, 'name': 'Under 30'}, {'code': 2, 'name': '30 and over'}])
        for choice, count in votes.items():
            for _i in range(count):
                session = SurveySession.objects.create(survey=survey)
                Answer.objects.create(survey_session=session, question=prio, selected_choices=[choice])
        return survey, prio

    def report(self, survey=None):
        survey = survey or self.one
        report = Report.objects.create(survey=survey, slug='round-one-report', is_published=True, visibility='unlisted',
                                       intro={'title': {'en': 'What we heard'}, 'body': {'en': 'The first round.'}})
        ReportBlock.objects.create(report=report, block_type='text', order=0,
                                   content={'en': '<p>{responses} people answered.</p>'})
        services.add_question_block(self.actor, report, Question.objects.get(survey_section__survey_header=survey, code='PRIO'),
                                    custom_title={'en': 'Priorities'}, viz='bar')
        services.add_view_block(self.actor, report, 'engagement', survey)
        return report

    def login(self):
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def payloads(self, report):
        return ReportService(report).build_blocks()


class CopyOntoTest(_Rounds):
    """Requirement: A report can be copied onto another survey."""

    def test_a_second_round_with_the_same_codes(self):
        """
        GIVEN a report of round one with a text, a chart of PRIO and an engagement block
        WHEN an editor copies it onto round two from the start page
        THEN the copy has the same blocks in order, its home and data blocks are round two's, it is
             unpublished, and its numbers are round two's
        """
        report = self.report()
        self.login()
        response = self.client.post(reverse('editor_report_start'),
                                    {'kind': 'copy', 'report': str(report.uuid), 'onto': str(self.two.uuid)})
        self.assertEqual(response.status_code, 302)
        copy = Report.objects.exclude(pk=report.pk).get()
        self.assertEqual((copy.survey_id, copy.is_published, copy.visibility), (self.two.pk, False, 'workspace'))
        blocks = list(copy.blocks.select_related('dataset', 'view__dataset').order_by('order'))
        self.assertEqual([b.block_type for b in blocks], ['text', 'chart', 'engagement'])
        self.assertEqual(blocks[1].dataset.survey_id, self.two.pk)
        self.assertEqual((blocks[1].custom_title, blocks[1].viz), ({'en': 'Priorities'}, 'bar'))
        self.assertEqual(blocks[2].view.dataset.survey_id, self.two.pk)
        text, chart, _engagement = self.payloads(copy)
        self.assertIn('12 people answered.', text['html'])
        self.assertEqual([i['value'] for i in chart['items']], [3, 9])

    def test_copying_without_choosing_a_survey(self):
        """
        GIVEN the same report
        WHEN it is copied without a survey
        THEN the copy's chart reads round one
        """
        copy = drafting.copy_report(self.actor, self.report())
        self.assertEqual(copy.survey_id, self.one.pk)
        self.assertEqual(copy.blocks.get(block_type='chart').dataset.survey_id, self.one.pk)
        self.assertEqual(copy.copy_notes, [])


class UnmatchedTest(_Rounds):
    """Requirement: Blocks that cannot be rebound are named."""

    def test_a_question_the_second_round_lacks(self):
        """
        GIVEN a report of a survey with PRIO and AGE, with a chart of each
        WHEN it is copied onto a survey that has PRIO only
        THEN the copy has the PRIO chart and a hidden note in the AGE chart's place, the message
             after the copy names the AGE block, and the copy's page shows no trace of it
        """
        first, _prio = self.round('Round with age', {1: 5}, extra=('AGE',))
        report = Report.objects.create(survey=first, slug='with-age', intro={'title': {'en': 'With age'}})
        for code in ('AGE', 'PRIO'):
            services.add_question_block(self.actor, report, Question.objects.get(survey_section__survey_header=first, code=code),
                                        custom_title={'en': f'By {code}'})
        self.login()
        response = self.client.post(reverse('editor_report_start'),
                                    {'kind': 'copy', 'report': str(report.uuid), 'onto': str(self.two.uuid)}, follow=True)
        notes = [str(m) for m in response.context['messages']]
        self.assertEqual(len(notes), 1)
        self.assertIn('By AGE', notes[0])
        self.assertIn('AGE', notes[0])
        copy = Report.objects.exclude(pk=report.pk).get()
        blocks = list(copy.blocks.order_by('order'))
        self.assertEqual([(b.block_type, b.is_hidden) for b in blocks], [('text', True), ('chart', False)])
        self.assertIn('By AGE', blocks[0].content['en'])
        self.assertEqual([p['block_type'] for p in self.payloads(copy)], ['chart'])

    def test_a_plain_import_still_leaves_the_block_out(self):
        """
        GIVEN a report file naming a survey another workspace does not have
        WHEN it is imported there
        THEN the data blocks are left out and named, with no hidden note
        """
        import io
        from reports.files import export_report, import_report
        _name, data = export_report(self.report())
        other_org, other_owner = make_pro_org('ElsewhereOrg', 'elsewhereowner')
        copy, notes = import_report(Actor(user=other_owner, ip=None, surface='editor'), other_org, io.BytesIO(data))
        self.assertEqual([b.block_type for b in copy.blocks.all()], ['text'])
        self.assertEqual(len(notes), 2)
        self.assertIn('Priorities', notes[0])


class CompareTest(_Rounds):
    """Requirement: A Compare block shows one question in two rounds."""

    def test_two_rounds_side_by_side(self):
        """
        GIVEN round one (6 Trees, 4 Benches) and round two (3 Trees, 9 Benches)
        WHEN an editor adds a Compare block of PRIO with round two through the Add block dialog
        THEN the page shows both surveys' names, 10 and 12 answered, and the shares 60/40 and 25/75
        """
        report = self.report()
        self.login()
        response = self.client.post(reverse('editor_report_block_add', args=[report.uuid]),
                                    {'block_type': 'compare', 'compare_question': 'PRIO', 'other': str(self.two.uuid)})
        self.assertEqual(response.status_code, 302, response.content)
        payload = next(p for p in self.payloads(report) if p['block_type'] == 'compare')
        self.assertEqual(payload['rounds'], [{'name': 'Round one', 'n': '10'}, {'name': 'Round two', 'n': '12'}])
        self.assertEqual([[c['share'] for c in line['cells']] for line in payload['rows']], [[60, 25], [40, 75]])
        self.client.logout()
        page = self.client.get(reverse('public_results', args=[report.slug]))
        self.assertContains(page, 'Round two')
        self.assertContains(page, '75%')
        self.assertEqual(rows_of(payload)[2], ['Trees', '6', 60, '3', 25])

    def test_small_groups(self):
        """
        GIVEN an option chosen by 2 people in round two and a threshold of 3
        WHEN the Compare block is rendered
        THEN that round's cell reads "<3" with no share, and the other round's cell is shown
        """
        third, _q = self.round('Round three', {1: 2, 2: 8})
        report = self.report()
        services.add_compare_block(self.actor, report, self.prio1, third)
        payload = next(p for p in self.payloads(report) if p['block_type'] == 'compare')
        trees = payload['rows'][0]['cells']
        self.assertEqual((trees[0]['share'], trees[0]['masked']), (60, False))
        self.assertEqual((trees[1]['display'], trees[1]['share'], trees[1]['masked']), ('<3', None, True))
        self.assertTrue(payload['masked'])

    def test_no_such_question_in_the_other_survey(self):
        """
        GIVEN a survey without a PRIO question
        WHEN an editor adds a Compare block naming it, in the editor and through the API
        THEN both are refused and nothing is added
        """
        bare, _section = make_v1_survey(self.org, self.owner, name='Bare survey', status='published')
        report = self.report()
        before = report.blocks.count()
        self.login()
        response = self.client.post(reverse('editor_report_block_add', args=[report.uuid]),
                                    {'block_type': 'compare', 'compare_question': 'PRIO', 'other': str(bare.uuid)})
        self.assertEqual(response.status_code, 400)
        api = V1Client(self.client, mint(self.owner)[0])
        refused = api.post(f'/reports/{report.uuid}/blocks', {'type': 'compare', 'question': 'PRIO', 'other': str(bare.uuid)})
        self.assertEqual(refused.status_code, 422, refused.content)
        self.assertIn('other', refused.json()['fields'])
        self.assertEqual(report.blocks.count(), before)

    def test_the_api_and_the_report_file_carry_it(self):
        """
        GIVEN a Compare block added through the API
        WHEN the report is copied
        THEN the API names the question and the other survey, and the copy compares the same two
        """
        report = self.report()
        api = V1Client(self.client, mint(self.owner)[0])
        added = api.post(f'/reports/{report.uuid}/blocks', {'type': 'compare', 'question': 'PRIO', 'other': str(self.two.uuid)})
        self.assertEqual(added.status_code, 201, added.content)
        self.assertEqual((added.json()['question'], added.json()['other']), ('PRIO', str(self.two.uuid)))
        copy = drafting.copy_report(self.actor, report)
        block = copy.blocks.get(block_type='compare')
        self.assertEqual((block.question_code, block.config), ('PRIO', {'other': str(self.two.uuid)}))
        self.assertEqual(copy.copy_notes, [])


class CompareInTheBlockTest(_Rounds):
    """Requirement: A Compare block shows one question in two rounds — added in one click and set
    up in its settings (change crosstab-settings-in-block, #751)."""

    def test_one_click(self):
        """
        GIVEN round one whose PRIO has a twin in round two
        WHEN an editor clicks the Compare tile (nothing else posted)
        THEN the report gets a Compare block of PRIO with round two
        """
        report = self.report()
        self.login()
        response = self.client.post(reverse('editor_report_block_add', args=[report.uuid]), {'block_type': 'compare'})
        self.assertEqual(response.status_code, 302, response.content)
        block = report.blocks.get(block_type='compare')
        self.assertEqual((block.question_code, block.config), ('PRIO', {'other': str(self.two.uuid)}))

    def test_changing_the_other_round(self):
        """
        GIVEN a Compare block of PRIO with round two, a round three with PRIO, and a survey without it
        WHEN its settings name round three, then the survey without PRIO
        THEN the first is saved, the second refused with a message and the block keeps round three
        """
        third, _q = self.round('Round three', {1: 5, 2: 5})
        bare, _section = make_v1_survey(self.org, self.owner, name='Bare survey', status='published')
        report = self.report()
        block = services.add_compare_block(self.actor, report, self.prio1, self.two)
        self.login()
        url = reverse('editor_report_block_edit', args=[report.uuid, block.id])
        ok = self.client.post(url, {'autosave': '1', 'cmp_question': 'PRIO', 'cmp_other': str(third.uuid)},
                              HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(ok.status_code, 200)
        refused = self.client.post(url, {'autosave': '1', 'cmp_question': 'PRIO', 'cmp_other': str(bare.uuid)},
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(refused.status_code, 422)
        self.assertIn('no comparable question', refused.content.decode())
        block.refresh_from_db()
        self.assertEqual(block.config, {'other': str(third.uuid)})


class EventTest(_Rounds):
    """Requirement: Reuse is measured."""

    def test_a_copy_onto_another_survey(self):
        """
        GIVEN a report with one chart the next round cannot back
        WHEN it is copied onto that round
        THEN report_reused is emitted with onto true and unmatched 1, ids only
        """
        first, _prio = self.round('Round with age', {1: 5}, extra=('AGE',))
        report = Report.objects.create(survey=first, slug='with-age', intro={'title': {'en': 'With age'}})
        services.add_question_block(self.actor, report, Question.objects.get(survey_section__survey_header=first, code='AGE'))
        with patch('survey.product_events.emit') as emit:
            copy = drafting.copy_report(self.actor, report, onto=self.two)
        event, user_id, props = emit.call_args[0]
        self.assertEqual((event, user_id), ('report_reused', self.owner.pk))
        self.assertEqual(props, {'source': str(report.pk), 'report': str(copy.pk), 'onto': True, 'blocks': 1, 'unmatched': 1})
