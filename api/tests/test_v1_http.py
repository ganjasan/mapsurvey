"""`rest-api-v1`: the HTTP surface -- CORS, the envelope, errors, metadata,
and the OpenAPI document as the contract."""
from unittest import mock

from django.test import TestCase, override_settings

from .. import errors as codes
from .helpers import LOCMEM, ISSUER, V1Client, make_pro_org, make_v1_survey, mint


@LOCMEM
class V1HttpTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.api = V1Client(self.client, mint(self.owner)[0])

    def test_preflight_from_another_origin_carries_no_credentials(self):
        """
        GIVEN a CORS preflight from https://evil.example
        WHEN OPTIONS /api/v1/surveys arrives without a bearer
        THEN 204 with Access-Control-Allow-Origin * and no Allow-Credentials header
        """
        response = self.client.options('/api/v1/surveys', HTTP_ORIGIN='https://evil.example',
                                       HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
                                       HTTP_ACCESS_CONTROL_REQUEST_HEADERS='authorization, content-type')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['Access-Control-Allow-Origin'], '*')
        self.assertIn('Authorization', response['Access-Control-Allow-Headers'])
        self.assertFalse(response.has_header('Access-Control-Allow-Credentials'))

    def test_every_answer_is_no_store_with_cors(self):
        """
        GIVEN an authenticated read
        WHEN it is answered
        THEN Cache-Control no-store and Access-Control-Allow-Origin * without credentials
        """
        response = self.api.get(f'/surveys/{self.survey.uuid}', HTTP_ORIGIN='https://app.example')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Access-Control-Allow-Origin'], '*')
        self.assertFalse(response.has_header('Access-Control-Allow-Credentials'))

    def test_unexpected_error_is_the_envelope_without_a_trace(self):
        """
        GIVEN a service that raises an unexpected error
        WHEN the route runs
        THEN 500 server_error with no traceback or model name, and PostHog gets no bearer value
        """
        with mock.patch('api.v1.surveys.out.survey_detail', side_effect=RuntimeError('SurveyHeader boom')), \
                mock.patch('api.v1.errors._capture') as capture:
            response = self.api.get(f'/surveys/{self.survey.uuid}')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {'error': 'server_error', 'detail': 'Something went wrong on our side.'})
        self.assertNotIn(b'Traceback', response.content)
        self.assertNotIn(b'SurveyHeader', response.content)
        capture.assert_called_once()
        self.assertNotIn(self.api.token, repr(capture.call_args))

    def test_unknown_route_is_the_envelope(self):
        """
        GIVEN a path under /api/v1/ that names nothing
        WHEN it is requested
        THEN 404 not_found in the envelope, not the site's HTML page
        """
        response = self.api.get('/nothing/here')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error'], 'not_found')

    @override_settings(OAUTH_ISSUER=ISSUER, API_RESOURCE_URLS={'api': ISSUER + '/api/', 'mcp': ISSUER + '/mcp/'})
    def test_protected_resource_metadata(self):
        """
        GIVEN the RFC 9728 document of the API
        WHEN it is fetched without authentication
        THEN it names the API resource, the issuer and the scopes registry
        """
        body = self.client.get('/.well-known/oauth-protected-resource/api/').json()
        self.assertEqual(body['resource'], ISSUER + '/api/')
        self.assertEqual(body['authorization_servers'], [ISSUER])
        self.assertIn('responses:read', body['scopes_supported'])
        self.assertEqual(body['bearer_methods_supported'], ['header'])


class V1ContractTest(TestCase):
    def setUp(self):
        self.doc = self.client.get('/api/v1/openapi.json')

    def test_document_is_public_and_valid(self):
        """
        GIVEN no credentials
        WHEN /api/v1/openapi.json is fetched
        THEN it is an OpenAPI 3.1 document that validates
        """
        self.assertEqual(self.doc.status_code, 200)
        doc = self.doc.json()
        self.assertTrue(doc['openapi'].startswith('3.1'))
        try:
            from openapi_spec_validator import validate
        except ImportError:
            self.assertIn('paths', doc)
            self.assertIn('components', doc)
        else:
            validate(doc)

    def test_every_operation_is_secured_and_lists_its_codes(self):
        """
        GIVEN the document
        WHEN every operation is read
        THEN each has a bearer security requirement, and the union of x-error-codes is every stable code
        """
        doc = self.doc.json()
        seen = set()
        for path, methods in doc['paths'].items():
            for method, op in methods.items():
                self.assertTrue(op.get('security'), f'{method.upper()} {path} has no security')
                seen.update(op.get('x-error-codes', []))
        self.assertEqual(seen, set(codes.ALL_CODES))


class ApiReferenceFreshnessTest(TestCase):
    def test_help_reference_matches_the_document(self):
        """
        GIVEN the help centre's REST API reference page
        WHEN it is rendered again from the current OpenAPI document
        THEN it is identical -- a route or schema change ships with a regenerated page
        """
        import importlib.util
        from pathlib import Path
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'build_api_reference.py'
        spec = importlib.util.spec_from_file_location('build_api_reference', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.PAGE.read_text(), module.render(module.openapi_document()),
                         'help/src/content/docs/reference/api.md is stale: run python scripts/build_api_reference.py')
