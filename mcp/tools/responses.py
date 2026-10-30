"""Responses: what came back -- the summary, text answers, one map question's
geometry, a download link for a person, and moderation (change
api-v2-responses, #409 PR 2). Every tool calls the REST routes' own functions
(`api.v1.responses`, `api.v1.data.response_page`), so the numbers an agent
reports equal the API's and the export's.

Respondent text reaches the model here more than anywhere else: write-ins,
free-text answers, sub-question values. It travels inside `data` like all
survey content, under the note that it is information, not instructions.
"""
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field

from survey import export as data_export

from api import scopes
from api.errors import VALIDATION, ApiError
from api.v1 import responses as api_responses
from api.v1.data import response_page

from .common import actor, question, survey
from .registry import args_model, tool

SURVEY = (UUID, Field(description='The survey uuid (from list_surveys).'))
QUESTION = (int, Field(description='A question id from get_survey.'))
VERSION = (Optional[str], Field(None, description='One version (v3), several separated by commas (v10,v11), or omit for every version.'))
INCLUDE_ALL = (bool, Field(False, description='Also count deleted and rejected responses.'))
COMPLETED_ONLY = (bool, Field(False, description='Only responses that reached the last section.'))
SCOPE_FIELDS = dict(version=VERSION, include_all=INCLUDE_ALL, completed_only=COMPLETED_ONLY)


def _scope(obj, args):
    return api_responses._scope(obj, args.version, args.include_all, args.completed_only)


@tool(
    'get_response_summary',
    title='Summarise responses',
    description=(
        'How many responses a survey has and what they say, question by question in section order: option '
        'counts with the most frequent "other" write-ins, number statistics, rating means, text and map '
        'answer counts. Sub-questions of map questions are nested under their map question; "Objects on '
        'the map" questions list each object with its answers. Counts the responses an export contains: '
        'no empty, deleted or rejected ones unless include_all. Start a report here, then use '
        'list_text_answers and get_answer_geojson for detail.'
    ),
    scope=scopes.RESPONSES_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model('ResponseSummaryArgs', survey=SURVEY, **SCOPE_FIELDS),
)
def get_response_summary(request, args):
    obj = survey(request, args.survey)
    return api_responses.build_summary(obj, _scope(obj, args))


@tool(
    'list_responses',
    title='List responses',
    description=(
        'Individual responses, newest first, each with its "#N" number, language, validation status and '
        'every answer (map answers as GeoJSON geometry with their sub-answers). Prefer '
        'get_response_summary for numbers; use this to read particular responses.'
    ),
    scope=scopes.RESPONSES_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model(
        'ListResponsesArgs', survey=SURVEY,
        include_empty=(bool, Field(False, description='Also responses that answered nothing.')),
        cursor=(Optional[str], Field(None, description='`next_cursor` of the previous page.')),
        limit=(int, Field(20, ge=1, le=200)),
    ),
)
def list_responses(request, args):
    return response_page(survey(request, args.survey), args.include_empty, args.cursor, args.limit)


@tool(
    'list_text_answers',
    title='List text answers',
    description=(
        'The non-blank answers to one text question or text sub-question, newest first, each with the '
        'response number. Page through with `next_cursor` to read every comment.'
    ),
    scope=scopes.RESPONSES_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model(
        'TextAnswersArgs', survey=SURVEY, question_id=QUESTION, **SCOPE_FIELDS,
        cursor=(Optional[str], Field(None, description='`next_cursor` of the previous page.')),
        limit=(int, Field(50, ge=1, le=200)),
    ),
)
def list_text_answers(request, args):
    obj = survey(request, args.survey)
    q = question(request, obj, args.question_id)
    return api_responses.text_answers(obj, q, _scope(obj, args), args.cursor, args.limit)


@tool(
    'get_answer_geojson',
    title='Get map answers as GeoJSON',
    description=(
        'The points, lines, areas or spray clouds respondents drew for one map question, as a GeoJSON '
        'FeatureCollection (WGS 84). Each feature carries the answers to the sub-questions as properties '
        'and the response it came from. Stops at `limit` features and then says `truncated: true`; for '
        'everything, hand the person a link from get_export_link.'
    ),
    scope=scopes.RESPONSES_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model(
        'AnswerGeoJSONArgs', survey=SURVEY, question_id=QUESTION, **SCOPE_FIELDS,
        limit=(int, Field(200, ge=1, le=5000, description='Most features to return.')),
    ),
)
def get_answer_geojson(request, args):
    obj = survey(request, args.survey)
    q = question(request, obj, args.question_id)
    return api_responses.question_geojson(q, _scope(obj, args), limit=args.limit)


@tool(
    'get_export_link',
    title='Get an export link',
    description=(
        'A link for the person to download the responses as a file -- xlsx (Excel), csv, zip (GeoJSON + '
        'CSV), gpkg (GeoPackage), shp (Shapefile) or kml. It works for 15 minutes and checks access '
        'again when opened. Give the person the link; do not try to open it yourself.'
    ),
    scope=scopes.RESPONSES_READ, role='viewer', read_only=True, idempotent=False,
    args=args_model(
        'ExportLinkArgs', survey=SURVEY,
        format=(Literal['xlsx', 'csv', 'zip', 'gpkg', 'shp', 'kml'], Field('xlsx')),
        **SCOPE_FIELDS,
        files=(bool, Field(False, description='Add files respondents uploaded.')),
    ),
)
def get_export_link(request, args):
    obj = survey(request, args.survey)
    refusal = data_export.check_format(args.format)
    if refusal:
        raise ApiError(400, VALIDATION, refusal, fields={'format': [refusal]})
    return api_responses.make_export_link(request, obj, {
        'f': args.format, 'v': args.version, 'a': args.include_all, 'c': args.completed_only, 'x': args.files})


@tool(
    'moderate_response',
    title='Approve, hold or reject a response',
    description=(
        'Set a response\'s status: approved, on_hold, not_approved (rejected responses leave exports, '
        'summaries and public results), or "" to clear it. It can be changed back. Needs the editor role.'
    ),
    scope=scopes.RESPONSES_MODERATE, role='editor', idempotent=True,
    args=args_model(
        'ModerateArgs', survey=SURVEY,
        response_id=(int, Field(description='The response id from list_responses.')),
        validation_status=(Literal['approved', 'not_approved', 'on_hold', ''], Field()),
    ),
)
def moderate_response(request, args):
    obj = survey(request, args.survey, role='editor')
    session = api_responses.set_status(request, obj, args.response_id, args.validation_status,
                                       actor=actor(request))
    return {'id': session.pk, 'validation_status': session.validation_status or ''}
