"""Builders shared by the mcp test modules: the api builders plus a JSON-RPC client."""
import json

from django.test import override_settings

from api.tests.helpers import (  # noqa: F401 -- re-exported for the mcp modules
    ISSUER, LOCMEM, RESOURCES, bearer, make_free_org, make_member, make_pro_org, make_user, make_v1_survey, mint,
)

ENDPOINT = '/mcp'
METADATA = '/.well-known/oauth-protected-resource/mcp'
VERSION = '2025-11-25'

#: The test client's host is `testserver`: issuer and resources follow it.
MCP_SETTINGS = override_settings(OAUTH_ISSUER=ISSUER, API_RESOURCE_URLS=RESOURCES, MCP_RESOURCE_URL=RESOURCES['mcp'])


def rpc(method, params=None, id=1):
    return {'jsonrpc': '2.0', 'id': id, 'method': method, 'params': params or {}}


class McpClient:
    """One client ↔ server conversation: bearer, protocol version, session id."""

    def __init__(self, client, token, version=VERSION):
        self.client, self.token, self.version = client, token, version
        self.session = None

    def post(self, body, token=None, path=ENDPOINT, session=None, version=None, **extra):
        headers = dict(bearer(token or self.token)) if (token or self.token) else {}
        headers['HTTP_ACCEPT'] = 'application/json, text/event-stream'
        version = self.version if version is None else version
        if version:
            headers['HTTP_MCP_PROTOCOL_VERSION'] = version
        session = self.session if session is None else session
        if session:
            headers['HTTP_MCP_SESSION_ID'] = session
        headers.update(extra)
        data = body if isinstance(body, str) else json.dumps(body)
        return self.client.post(path, data, content_type='application/json', **headers)

    def rpc(self, method, params=None, id=1, **kw):
        return self.post(rpc(method, params, id), **kw)

    def initialize(self, **kw):
        response = self.rpc('initialize', {
            'protocolVersion': self.version, 'capabilities': {}, 'clientInfo': {'name': 'tests', 'version': '0'},
        }, **kw)
        if response.has_header('Mcp-Session-Id'):
            self.session = response['Mcp-Session-Id']
        return response

    def call(self, name, arguments=None, **kw):
        return self.rpc('tools/call', {'name': name, 'arguments': arguments or {}}, **kw)

    def tools(self, **kw):
        return [t['name'] for t in self.rpc('tools/list', **kw).json()['result']['tools']]


def result_of(response):
    body = response.json()
    assert response.status_code == 200, (response.status_code, body)
    assert 'result' in body, body
    return body['result']


def data_of(response):
    """The `data` of a successful tool result."""
    result = result_of(response)
    assert result['isError'] is False, result
    return result['structuredContent']['data']


def error_of(response):
    """The envelope of an `isError` tool result."""
    result = result_of(response)
    assert result['isError'] is True, result
    return result['structuredContent']


def minimal_survey_json(name='Imported'):
    return {
        'version': '1.0', 'mode': 'structure',
        'survey': {
            'name': name, 'redirect_url': '#', 'available_languages': ['en'],
            'sections': [{
                'name': 'main', 'title': 'Main', 'code': 'MAIN', 'is_head': True,
                'start_map_zoom': 12, 'translations': [],
                'questions': [{
                    'code': 'Q1', 'order_number': 1, 'name': 'Where?', 'input_type': 'point',
                    'required': False, 'color': '#000000', 'translations': [], 'sub_questions': [],
                }],
            }],
        },
    }
