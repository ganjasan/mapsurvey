"""REST API v1 (change rest-api-v1, #380): django-ninja over the authorization
layer and the survey service layer.

Mounted at `/api/v1/`; the OpenAPI document is `/api/v1/openapi.json` (public:
it is the contract). The interactive docs page is not mounted -- the help
centre renders the reference. Every route authenticates with `auth.Bearer`
(its scopes checked before the body is read), resolves the survey through
`deps.survey` (404 for what the caller cannot see, Pro on the owning
workspace) and writes only through `survey/services/`. Errors are the one
envelope (`errors.register`).
"""
from ninja import NinjaAPI

from . import data, errors, me, questions, sections, surveys
from .auth import Bearer

api = NinjaAPI(
    title='Mapsurvey API',
    version='1',
    description=(
        'Create, edit and publish map surveys, and read their responses. '
        'Authenticate with `Authorization: Bearer <token>` -- a personal token from '
        'Account → API & connections, or an OAuth 2.1 access token. The API is part of '
        'the Pro plan of the workspace that owns the survey.'
    ),
    urls_namespace='api_v1',
    auth=Bearer(),
    docs_url=None,
    openapi_url='/openapi.json',
)
errors.register(api)
api.add_router('', me.router)
api.add_router('', data.imports_router)
api.add_router('', surveys.router)
api.add_router('', sections.router)
api.add_router('', questions.router)
api.add_router('', data.router)
