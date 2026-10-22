"""`/api/v1/me` explains the token (spec api-access-rights)."""
from django.test import TestCase
from django.urls import reverse

from survey.models import Membership

from ..models import AUDIENCE_API, AUDIENCE_MCP
from .helpers import LOCMEM, bearer, make_free_org, make_pro_org, mint

ME = reverse('api_me')


@LOCMEM
class MeTest(TestCase):
    def setUp(self):
        self.pro, self.owner = make_pro_org()
        self.free, _ = make_free_org()
        Membership.objects.create(user=self.owner, organization=self.free, role='editor')

    def test_shape_with_free_and_pro_workspaces(self):
        """
        GIVEN a member of a Free and a Pro workspace
        WHEN /me is called
        THEN 200 with both workspaces, api true/false, and the token block
        """
        value, profile = mint(self.owner, scopes_=('surveys:write', 'surveys:read'), audiences=(AUDIENCE_API, AUDIENCE_MCP),
                              label='QGIS')
        response = self.client.get(ME, **bearer(value))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['user'], {'id': self.owner.pk, 'username': self.owner.username, 'email': self.owner.email})
        self.assertEqual(body['workspaces'], [
            {'id': self.free.pk, 'slug': self.free.slug, 'name': self.free.name, 'role': 'editor', 'plan': 'free',
             'api': False},
            {'id': self.pro.pk, 'slug': self.pro.slug, 'name': self.pro.name, 'role': 'owner', 'plan': 'pro',
             'api': True},
        ])
        self.assertEqual(body['token'], {
            'kind': 'personal', 'scopes': ['surveys:read', 'surveys:write'], 'audiences': ['api', 'mcp'],
            'organization': None, 'expires': profile.token.expires.isoformat(), 'label': 'QGIS',
        })
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_bound_token_lists_one_workspace(self):
        """
        GIVEN a token bound to the Free workspace
        WHEN /me is called
        THEN only that workspace is listed and token.organization names it
        """
        value, _ = mint(self.owner, organization=self.free)
        body = self.client.get(ME, **bearer(value)).json()
        self.assertEqual([w['slug'] for w in body['workspaces']], [self.free.slug])
        self.assertEqual(body['token']['organization'], self.free.slug)

    def test_needs_no_scope_and_no_pro(self):
        """
        GIVEN a token with only responses:read on a user with only Free workspaces
        WHEN /me is called
        THEN 200 -- the endpoint exists to explain pro_required before it happens
        """
        free2, owner2 = make_free_org('Solo', 'solo')
        value, _ = mint(owner2, scopes_=('responses:read',))
        response = self.client.get(ME, **bearer(value))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['workspaces'][0]['api'], False)

    def test_mcp_only_token_refused(self):
        """
        GIVEN a token whose audience is the MCP server only
        WHEN /me (audience api) is called
        THEN 401
        """
        value, _ = mint(self.owner, audiences=(AUDIENCE_MCP,))
        self.assertEqual(self.client.get(ME, **bearer(value)).status_code, 401)
