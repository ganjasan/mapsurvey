"""Layers (read-only), ZIP import as a job, responses and export."""
import json
from typing import List, Optional
from uuid import UUID

from django.db.models import Prefetch
from ninja import File, Form, Router, Status
from ninja.files import UploadedFile

from survey import export as data_export
from survey import product_events as pe
from survey.analytics import SurveyAnalyticsService
from survey.models import Answer, SurveyImportJob
from survey.tasks import run_survey_import
from survey.views import cached_geojson_response

from .. import limits, scopes
from ..errors import VALIDATION, ApiError, not_found
from . import deps, out
from .auth import Bearer
from .docs import errors, list_errors
from .pagination import page
from .schemas import ImportJobOut, LayerOut, ResponseList
from .surveys import _workspace

router = Router(tags=['Data'])
# Its own router, mounted BEFORE /surveys/{uuid}: ninja matches `{uuid}` as a
# string segment, so "import" would otherwise land on the survey routes.
imports_router = Router(tags=['Import'])

READ = Bearer(scopes.SURVEYS_READ)
WRITE = Bearer(scopes.SURVEYS_WRITE)
RESPONSES = Bearer(scopes.RESPONSES_READ)


# ─── Layers ──────────────────────────────────────────────────────────────────

@router.get('/surveys/{uuid}/layers', response=List[LayerOut], auth=READ, openapi_extra=errors())
def list_layers(request, uuid: UUID):
    """The survey's reference layers, metadata only; fetch geometry from `geojson_url`."""
    survey = deps.survey(request, uuid)
    return [out.layer(layer, survey) for layer in deps.layers_list(survey)]


@router.get('/surveys/{uuid}/layers/{layer_id}/geojson', auth=READ, url_name='layer_geojson',
            openapi_extra=errors())
def layer_geojson(request, uuid: UUID, layer_id: int):
    """The layer's GeoJSON FeatureCollection. Sent gzip-encoded to a client
    that accepts it (the stored bytes, passed through)."""
    survey = deps.survey(request, uuid)
    return cached_geojson_response(request, deps.layer(request, survey, layer_id, with_geojson=True))


# ─── Import ──────────────────────────────────────────────────────────────────

@imports_router.post('/surveys/import', response={202: ImportJobOut}, auth=WRITE, openapi_extra=errors())
def import_survey(request, file: File[UploadedFile], workspace: Form[Optional[str]] = None):
    """Import a survey ZIP (the editor's "Backup (survey file)") as a job.
    Poll `/import-jobs/{id}` until `status` is `done` or `failed`."""
    p = request.principal
    organization = _workspace(p, workspace)
    if not (file.name or '').lower().endswith('.zip'):
        raise ApiError(422, VALIDATION, 'Upload a .zip file.', fields={'file': ['Upload a .zip file.']})
    limits.hit(p, 'survey_import')
    job = SurveyImportJob.objects.create(
        user=p.user, organization=organization,
        original_name=(file.name or 'archive.zip')[:255], file=file,
    )
    run_survey_import.delay(job.pk)
    return Status(202, out.import_job(job))


@imports_router.get('/import-jobs/{job_id}', response=ImportJobOut, auth=READ, openapi_extra=errors())
def get_import_job(request, job_id: int):
    """One of your import jobs."""
    job = SurveyImportJob.objects.filter(pk=job_id, user=request.principal.user).select_related('survey').first()
    if job is None:
        raise not_found()
    return out.import_job(job)


# ─── Responses ───────────────────────────────────────────────────────────────

def _answer(answer, children):
    geometry = answer.geometry
    item = {
        'question': answer.question.code,
        'question_id': answer.question_id,
        'type': answer.question.input_type,
    }
    if answer.selected_choices is not None:
        item['choices'] = answer.selected_choices
    if answer.numeric is not None:
        item['number'] = answer.numeric
    if answer.text:
        item['text'] = answer.text
    if answer.yn is not None:
        item['yes'] = answer.yn
    if geometry is not None:
        item['geometry'] = json.loads(geometry.json)
    if answer.layer_object_id is not None:
        item['object'] = answer.layer_object.key
    if answer.upload_id is not None:
        item['file'] = answer.upload_id
    if children:
        item['answers'] = [_answer(c, []) for c in children]
    return item


def _response(session, numbers):
    answers = list(session.answer_set.all())
    children = {}
    for a in answers:
        if a.parent_answer_id_id is not None:
            children.setdefault(a.parent_answer_id_id, []).append(a)
    return {
        'id': session.pk,
        'number': numbers.get(session.pk),
        'survey': session.survey.uuid,
        'started_at': session.start_datetime,
        'language': session.language or None,
        'validation_status': session.validation_status or '',
        'answers': [_answer(a, children.get(a.pk, [])) for a in answers if a.parent_answer_id_id is None],
    }


@router.get('/surveys/{uuid}/responses', response=ResponseList, auth=RESPONSES, openapi_extra=list_errors())
def list_responses(request, uuid: UUID, include_empty: bool = False, cursor: Optional[str] = None,
                   limit: int = 50):
    """Responses of every version of the survey, newest first. Sessions that
    answered nothing are left out unless `include_empty=true`. Answers carry
    no respondent IP or browser."""
    return response_page(deps.survey(request, uuid), include_empty, cursor, limit)


def response_page(survey, include_empty=False, cursor=None, limit=50):
    """One page of responses -- the route's body, shared with the MCP tool."""
    service = SurveyAnalyticsService(survey, include_empty=include_empty)
    qs = service.base_qs.select_related('survey').prefetch_related(
        Prefetch('answer_set', queryset=Answer.objects.select_related('question', 'layer_object')
                 .order_by('question__order_number', 'id')))
    sessions, next_cursor = page(qs, f'responses:{survey.uuid}', cursor, limit)
    numbers = service.sequence_numbers()
    return {'items': [_response(s, numbers) for s in sessions], 'next_cursor': next_cursor}


@router.get('/surveys/{uuid}/export', auth=RESPONSES, openapi_extra=errors(400))
def export(request, uuid: UUID, format: str = 'zip', version: Optional[str] = None,
           include_all: bool = False, completed_only: bool = False, files: bool = False):
    """The Responses page's "Export data" as a file: `zip` (GeoJSON + CSV),
    `xlsx`, `csv`, `gpkg`, `shp`, `kml`; `files=true` adds uploads."""
    survey = deps.survey(request, uuid)
    refusal = data_export.check_format(format)
    if refusal:
        raise ApiError(400, VALIDATION, refusal, fields={'format': [refusal]})
    limits.hit(request.principal, 'export')
    pe.emit(pe.DATA_EXPORTED, request.principal.user.pk,
            {'survey_id': str(survey.id), 'format': format, 'surface': 'api'})
    return data_export.export_response(survey, format, version=version, include_all=include_all,
                                       completed_only=completed_only, include_files=files)
