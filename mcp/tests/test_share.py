"""`mcp-server` (change api-v2-distribution, #410 PR 2): distribution tools over
survey/share.py -- the same URLs as REST, a QR as an image block."""
import base64

from django.test import TestCase, override_settings

from survey.models import TrackedLink

from api import scopes
from .helpers import (
    LOCMEM, MCP_SETTINGS, McpClient, data_of, error_of, make_member, make_pro_org, make_v1_survey, mint,
    result_of,
)

SITE = 'https://mapsurvey.example'


@LOCMEM
@MCP_SETTINGS
@override_settings(SITE_URL=SITE)
class ShareToolsTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, _section = make_v1_survey(self.org, self.owner, status='published')
        self.token, _ = mint(self.owner)
        self.mcp = McpClient(self.client, self.token)
        self.mcp.initialize()
        self.ref = {'survey': str(self.survey.uuid)}

    def test_share_links_equal_the_rest_answer(self):
        """
        GIVEN a published survey
        WHEN get_share_links is called and the REST share route is asked
        THEN the tool's data equals the REST body
        """
        from .helpers import bearer
        tool = data_of(self.mcp.call('get_share_links', self.ref))
        rest = self.client.get(f'/api/v1/surveys/{self.survey.uuid}/share', **bearer(self.token)).json()
        self.assertEqual(tool, rest)
        self.assertEqual(tool['url'], f'{SITE}/surveys/{self.survey.uuid}/')

    def test_qr_comes_as_an_image_block(self):
        """
        GIVEN a published survey
        WHEN get_qr_code is called
        THEN content holds a text block and an image/png block of the survey URL, and data names the URL
        """
        from survey.share import qr_image
        result = result_of(self.mcp.call('get_qr_code', {**self.ref, 'size': 4}))
        self.assertFalse(result['isError'])
        kinds = [c['type'] for c in result['content']]
        self.assertEqual(kinds, ['text', 'image'])
        image = result['content'][1]
        self.assertEqual(image['mimeType'], 'image/png')
        url = f'{SITE}/surveys/{self.survey.uuid}/'
        self.assertEqual(base64.b64decode(image['data']), qr_image(url, 'png', 4)[0])
        self.assertEqual(result['structuredContent']['data']['url'], url)

    def test_qr_of_a_draft_is_an_error(self):
        """
        GIVEN a draft survey
        WHEN get_qr_code is called
        THEN the result is the not_shareable envelope
        """
        self.survey.status = 'draft'
        self.survey.save()
        self.assertEqual(error_of(self.mcp.call('get_qr_code', self.ref))['error'], 'not_shareable')

    def test_tracked_link_from_a_chat(self):
        """
        GIVEN an editor's token with surveys:write
        WHEN create_tracked_link, list_tracked_links and delete_tracked_link are called
        THEN the link carries utm_source=newsletter, is listed with 0/0, and is gone after the delete
        """
        created = data_of(self.mcp.call('create_tracked_link', {**self.ref, 'utm_source': 'newsletter'}))
        self.assertIn('utm_source=newsletter', created['url'])
        items = data_of(self.mcp.call('list_tracked_links', self.ref))['items']
        self.assertEqual([(i['id'], i['started'], i['completed']) for i in items], [(created['id'], 0, 0)])
        data_of(self.mcp.call('delete_tracked_link', {**self.ref, 'link_id': created['id']}))
        self.assertFalse(TrackedLink.objects.filter(pk=created['id']).exists())

    def test_writes_need_scope_and_role(self):
        """
        GIVEN a read-only token, and a viewer with surveys:write
        WHEN tools are listed and create_tracked_link is called by the viewer
        THEN the write tools are not listed for the read-only token and the viewer gets forbidden_role
        """
        read_only, _ = mint(self.owner, scopes_=(scopes.SURVEYS_READ,))
        names = self.mcp.tools(token=read_only, session='')
        self.assertIn('get_qr_code', names)
        self.assertNotIn('create_tracked_link', names)
        self.assertNotIn('set_embed_hosts', names)
        viewer = make_member(self.org, 'mcp_share_viewer', role='viewer')
        error = error_of(self.mcp.call('create_tracked_link', {**self.ref, 'utm_source': 'x'},
                                       token=mint(viewer)[0], session=''))
        self.assertEqual(error['error'], 'forbidden_role')

    def test_embed_hosts(self):
        """
        GIVEN an invalid and then a valid host list
        WHEN set_embed_hosts is called
        THEN the first is a validation error naming the entry and the second is saved normalised
        """
        error = error_of(self.mcp.call('set_embed_hosts', {**self.ref, 'hosts': ['not a host!']}))
        self.assertEqual(error['error'], 'validation')
        data = data_of(self.mcp.call('set_embed_hosts', {**self.ref, 'hosts': ['Example.org']}))
        self.assertEqual(data['hosts'], ['example.org'])
