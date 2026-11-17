"""Spec: reports-usage-api (change reports-usage-api, #710, epic #712).

A report counts how often it is read (no visitor stored, members not counted), takes workspace
tags, and is written through REST API v1 and MCP with the editor's rules.
"""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import V1Client, make_pro_org, make_v1_survey, mint
from billing.tests.helpers import trial_used_elsewhere
from mcp.tests.helpers import McpClient, data_of, error_of
from reports import usage
from reports.models import Report, ReportBlock
from django.contrib.auth.models import User

from survey.models import Answer, Membership, Question, SurveySession


class _Fixture(TestCase):
    def setUp(self):
        cache.clear()
        self.org, self.owner = make_pro_org('RepApiOrg', 'repapiowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Riverside survey', status='published')
        self.question = Question.objects.create(survey_section=self.section, code='PRIO', name='Top priority',
                                                input_type='choice', choices=[{'code': 1, 'name': 'Trees'},
                                                                              {'code': 2, 'name': 'Benches'}])
        for _i in range(4):
            session = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(survey_session=session, question=self.question, selected_choices=[1])
        self.token = mint(self.owner)[0]

    def report(self, published=True, **values):
        report = Report.objects.create(survey=self.survey, slug=values.pop('slug', 'riverside-report'),
                                       is_published=published, visibility='unlisted',
                                       intro={'title': {'en': 'What we heard'}}, **values)
        ReportBlock.objects.create(report=report, block_type='chart', question=self.question)
        return report

    def login(self, user=None):
        self.client.force_login(user or self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()


class ReadersTest(_Fixture):
    """Requirement: A report counts how often it is read."""

    def test_an_anonymous_reader(self):
        """
        GIVEN a published report
        WHEN an anonymous visitor opens it twice and its embedded form once
        THEN the counts are 2 opened and 1 embedded
        """
        report = self.report()
        url = reverse('public_results', args=[report.slug])
        self.client.get(url)
        self.client.get(url)
        self.client.get(url, {'embed': '1'})
        counts = usage.summary(report)
        self.assertEqual((counts['view']['total'], counts['embed']['total'], counts['pdf']['total']), (2, 1, 0))
        self.assertEqual(counts['view']['recent'], 2)

    def test_the_author(self):
        """
        GIVEN a published report
        WHEN a signed-in member of its workspace opens it
        THEN no count changes
        """
        report = self.report()
        self.login()
        self.assertEqual(self.client.get(reverse('public_results', args=[report.slug])).status_code, 200)
        self.assertEqual(usage.summary(report)['view']['total'], 0)

    def test_the_editor_shows_the_numbers(self):
        """
        GIVEN a report opened three times by anonymous visitors
        WHEN an editor opens its editor
        THEN the Readers card carries the count
        """
        report = self.report()
        for _i in range(3):
            self.client.get(reverse('public_results', args=[report.slug]))
        self.login()
        response = self.client.get(reverse('editor_report', args=[report.uuid]))
        self.assertContains(response, 'data-testid="report-usage"')
        self.assertEqual(response.context['usage']['view']['total'], 3)


class TagsTest(_Fixture):
    """Requirement: A report takes workspace tags."""

    def test_tagging_a_report(self):
        """
        GIVEN two reports
        WHEN an editor saves one's settings with the tags "Riverside, 2027"
        THEN it carries both tags, and the list filtered by "riverside" has it and not the other
        """
        tagged = self.report()
        other = self.report(slug='other-report')
        self.login()
        response = self.client.post(reverse('editor_report_save', args=[tagged.uuid]),
                                    {'intro_title': 'What we heard', 'tags': 'Riverside, 2027', 'k': '3'})
        self.assertLess(response.status_code, 400)
        self.assertEqual(sorted(t.name for t in tagged.tags.all()), ['2027', 'Riverside'])
        listing = self.client.get(reverse('editor_reports'), {'tag': 'riverside'})
        shown = [row['report'].pk if isinstance(row, dict) else row.report.pk for row in listing.context['rows']]
        self.assertIn(tagged.pk, shown)
        self.assertNotIn(other.pk, shown)


class RestTest(_Fixture):
    """Requirement: Reports in REST API v1."""

    def setUp(self):
        super().setUp()
        self.api = V1Client(self.client, self.token)

    def test_draft_write_and_publish(self):
        """
        GIVEN a token of a workspace editor
        WHEN it creates a report from the survey with the template summary, adds a text block and a chart of PRIO, and publishes
        THEN the report is published and its page shows the text and the chart's question
        """
        created = self.api.post('/reports', {'survey': str(self.survey.uuid), 'template': 'summary', 'title': 'Riverside: what we heard'})
        self.assertEqual(created.status_code, 201, created.content)
        body = created.json()
        self.assertEqual((body['published'], body['title']), (False, 'Riverside: what we heard'))
        uuid = body['uuid']
        text = self.api.post(f'/reports/{uuid}/blocks', {'type': 'text', 'html': '<p>Residents asked for shade.</p><script>x</script>'})
        self.assertEqual(text.status_code, 201, text.content)
        self.assertNotIn('script', text.json()['html'])
        chart = self.api.post(f'/reports/{uuid}/blocks', {'type': 'chart', 'question': 'PRIO', 'title': 'Priorities', 'viz': 'bar'})
        self.assertEqual(chart.status_code, 201, chart.content)
        self.assertEqual((chart.json()['question'], chart.json()['viz']), ('PRIO', 'bar'))
        checks = self.api.get(f'/reports/{uuid}/checks').json()
        published = self.api.post(f'/reports/{uuid}/publish', {'visibility': 'unlisted', 'confirm': checks['needs_confirm']})
        self.assertEqual(published.status_code, 200, published.content)
        self.assertTrue(published.json()['published'])
        self.client.logout()
        slug = Report.objects.get(uuid=uuid).slug
        self.assertTrue(published.json()['address'].endswith(f'/r/{slug}/'))
        page = self.client.get(reverse('public_results', args=[slug]))
        self.assertContains(page, 'Residents asked for shade.')
        self.assertContains(page, 'Priorities')

    def test_reading_changing_and_ordering(self):
        """
        GIVEN a report with two blocks
        WHEN the token patches its title and tags, changes a block, reorders the blocks and deletes one
        THEN each change shows in the report as read back
        """
        report = self.report(published=False)
        heading = ReportBlock.objects.create(report=report, block_type='heading', order=1)
        chart = report.blocks.get(block_type='chart')
        uuid = report.uuid
        patched = self.api.patch(f'/reports/{uuid}', {'title': 'New title', 'tags': ['Riverside'], 'k': 5})
        self.assertEqual(patched.status_code, 200, patched.content)
        self.assertEqual((patched.json()['title'], patched.json()['tags'], patched.json()['k']), ('New title', ['Riverside'], 5))
        changed = self.api.patch(f'/reports/{uuid}/blocks/{heading.pk}', {'text': 'Who took part', 'width': 'half'})
        self.assertEqual((changed.json()['text'], changed.json()['width']), ('Who took part', 'half'))
        ordered = self.api.put(f'/reports/{uuid}/blocks/order', {'order': [heading.pk, chart.pk]})
        self.assertEqual([b['id'] for b in ordered.json()['blocks']], [heading.pk, chart.pk])
        self.assertEqual(self.api.put(f'/reports/{uuid}/blocks/order', {'order': [heading.pk]}).status_code, 422)
        self.assertEqual(self.api.call('DELETE', f'/reports/{uuid}/blocks/{heading.pk}').status_code, 200)
        read = self.api.get(f'/reports/{uuid}').json()
        self.assertEqual([b['type'] for b in read['blocks']], ['chart'])
        self.assertEqual(read['readers'], {'view': 0, 'embed': 0, 'pdf': 0})
        listed = self.api.get('/reports', {'tag': 'riverside'}).json()['items']
        self.assertEqual([r['uuid'] for r in listed], [str(uuid)])

    def test_quotes_need_a_confirmation(self):
        """
        GIVEN an unpublished report with a visible quote
        WHEN the token publishes it without confirm, then with confirm
        THEN the first answer is 409 and the report stays unpublished; the second publishes it
        """
        report = self.report(published=False)
        added = self.api.post(f'/reports/{report.uuid}/blocks',
                              {'type': 'quotes', 'items': [{'text': 'More shade by the river, please.', 'source': 'Resident'}]})
        self.assertEqual(added.status_code, 201, added.content)
        self.assertTrue(self.api.get(f'/reports/{report.uuid}/checks').json()['needs_confirm'])
        refused = self.api.post(f'/reports/{report.uuid}/publish', {})
        self.assertEqual((refused.status_code, refused.json()['error']), (409, 'conflict'))
        report.refresh_from_db()
        self.assertFalse(report.is_published)
        self.assertEqual(self.api.post(f'/reports/{report.uuid}/publish', {'confirm': True}).status_code, 200)
        report.refresh_from_db()
        self.assertTrue(report.is_published)

    def test_a_block_the_survey_cannot_back(self):
        """
        GIVEN a report
        WHEN the token adds a chart naming a question code the survey does not have, and an unknown field
        THEN both answer 422 (the first naming `question`) and no block is added
        """
        report = self.report(published=False)
        refused = self.api.post(f'/reports/{report.uuid}/blocks', {'type': 'chart', 'question': 'NOPE'})
        self.assertEqual(refused.status_code, 422, refused.content)
        self.assertIn('question', refused.json()['fields'])
        self.assertEqual(self.api.post(f'/reports/{report.uuid}/blocks', {'type': 'heading', 'colour': 'red'}).status_code, 422)
        self.assertEqual(report.blocks.count(), 1)

    def test_another_workspaces_report(self):
        """
        GIVEN a report
        WHEN a token of a member of another workspace reads it or adds a block
        THEN both answer 404
        """
        report = self.report()
        _org, stranger = make_pro_org('StrangerRepOrg', 'strangerrepowner')
        api = V1Client(self.client, mint(stranger)[0])
        self.assertEqual(api.get(f'/reports/{report.uuid}').status_code, 404)
        self.assertEqual(api.post(f'/reports/{report.uuid}/blocks', {'type': 'heading'}).status_code, 404)

    def test_a_viewer_cannot_write(self):
        """
        GIVEN a workspace viewer's token
        WHEN it reads a report and then adds a block
        THEN the read works and the write is 403 forbidden_role
        """
        report = self.report()
        viewer = User.objects.create_user(username='repviewer', password='pass', email='repviewer@example.test')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        api = V1Client(self.client, mint(viewer)[0])
        self.assertEqual(api.get(f'/reports/{report.uuid}').status_code, 200)
        refused = api.post(f'/reports/{report.uuid}/blocks', {'type': 'heading'})
        self.assertEqual((refused.status_code, refused.json()['error']), (403, 'forbidden_role'))

    def test_without_the_reports_feature(self):
        """
        GIVEN a workspace with the API but whose Reports feature is gone
        WHEN its token adds a block
        THEN the answer is 403 pro_required and no block is added
        """
        from unittest.mock import patch
        report = self.report(published=False)
        trial_used_elsewhere(self.org)
        with patch('reports.gate.covered', return_value=False):
            refused = self.api.post(f'/reports/{report.uuid}/blocks', {'type': 'heading'})
        self.assertEqual((refused.status_code, refused.json()['error']), (403, 'pro_required'))
        self.assertEqual(report.blocks.count(), 1)

    def test_freeze_and_delete(self):
        """
        GIVEN a published report
        WHEN the token freezes it, returns it to live, and deletes it
        THEN its mode follows and then it is gone
        """
        report = self.report()
        self.assertEqual(self.api.post(f'/reports/{report.uuid}/freeze', {}).json()['mode'], 'frozen')
        self.assertEqual(self.api.post(f'/reports/{report.uuid}/freeze', {'frozen': False}).json()['mode'], 'live')
        self.assertEqual(self.api.call('DELETE', f'/reports/{report.uuid}').status_code, 200)
        self.assertFalse(Report.objects.filter(pk=report.pk).exists())


class McpTest(_Fixture):
    """Requirement: Reports in MCP."""

    def setUp(self):
        super().setUp()
        self.mcp = McpClient(self.client, self.token)
        self.mcp.initialize()

    def test_an_agent_writes_a_report(self):
        """
        GIVEN an MCP session of a workspace owner
        WHEN the agent creates a report from the survey, adds a numbers block with a {responses} token, reads the checks and publishes
        THEN the report is published and its page shows the filled number
        """
        report = data_of(self.mcp.call('create_report', {'survey': str(self.survey.uuid), 'title': 'Riverside'}))
        block = data_of(self.mcp.call('add_report_block', {
            'report': report['uuid'], 'type': 'numbers', 'items': [{'value': '{responses}', 'label': 'people answered'}]}))
        self.assertEqual(block['items'][0]['value'], '{responses}')
        data_of(self.mcp.call('update_report_block', {'report': report['uuid'], 'block_id': block['id'], 'title': 'In numbers'}))
        checks = data_of(self.mcp.call('get_report_checks', {'report': report['uuid']}))
        self.assertFalse(checks['needs_confirm'])
        published = data_of(self.mcp.call('publish_report', {'report': report['uuid'], 'visibility': 'unlisted'}))
        self.assertTrue(published['published'])
        self.assertIn(report['uuid'], [r['uuid'] for r in data_of(self.mcp.call('list_reports'))['items']])
        self.client.logout()
        slug = Report.objects.get(uuid=report['uuid']).slug
        page = self.client.get(reverse('public_results', args=[slug]))
        self.assertContains(page, 'people answered')
        self.assertContains(page, 'In numbers')
        self.assertNotContains(page, '{responses}')

    def test_confirmation(self):
        """
        GIVEN a report with a visible quote
        WHEN the agent calls delete_report without confirm, then publish_report without confirm
        THEN both answer confirmation_required and nothing changes; with confirm the report is published
        """
        report = self.report(published=False)
        ReportBlock.objects.create(report=report, block_type='quotes', order=1,
                                   config={'items': [{'text': 'More shade, please.', 'source': 'Resident'}]})
        uuid = str(report.uuid)
        self.assertEqual(error_of(self.mcp.call('delete_report', {'report': uuid}))['error'], 'confirmation_required')
        self.assertEqual(error_of(self.mcp.call('publish_report', {'report': uuid}))['error'], 'confirmation_required')
        report.refresh_from_db()
        self.assertFalse(report.is_published)
        self.assertTrue(data_of(self.mcp.call('publish_report', {'report': uuid, 'confirm': True}))['published'])

    def test_tools_follow_the_scopes(self):
        """
        GIVEN a token with surveys:read only
        WHEN it lists the tools
        THEN the reading report tools are there and the writing ones are not
        """
        mcp = McpClient(self.client, mint(self.owner, scopes_=('surveys:read',))[0])
        mcp.initialize()
        names = mcp.tools()
        self.assertIn('get_report', names)
        self.assertIn('get_report_checks', names)
        for hidden in ('add_report_block', 'publish_report', 'delete_report'):
            self.assertNotIn(hidden, names)
