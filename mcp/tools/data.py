"""Data tools (change data-api, #674): datasets, views, versions and survey links — the REST
schemas and helpers of `api.v1.datasets`, every write through `data.services` with
`Actor(surface='mcp')`. An agent can upload a register, describe it and link it into a survey with
these alone."""
import base64
import binascii
from typing import List, Optional
from uuid import UUID

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from pydantic import Field

from data import services
from data.models import DatasetLink, DatasetView

from api import scopes
from api.errors import VALIDATION, ApiError, not_found
from api.v1.datasets import (DatasetPatchIn, FieldIn, ViewIn, dataset_for, dataset_out, job_for, job_out,
                             link_out, refused, view_out, workspace_of)

from .common import actor, survey
from .registry import args_model, tool

DATASET = (int, Field(description='A dataset id from list_datasets.'))
SURVEY = (UUID, Field(description='The survey uuid (from list_surveys).'))
FILENAME = (str, Field(min_length=1, max_length=255, description='The file name with its extension: .geojson, .json, .csv, .kml, .gpkg or .zip (a shapefile).'))
CONTENT = (Optional[str], Field(None, description='The file as text (GeoJSON, CSV, KML).'))
CONTENT_B64 = (Optional[str], Field(None, description='The file as base64 (GeoPackage, zipped shapefile, or any text format).'))


def _file(args):
    if bool(args.content) == bool(args.content_base64):
        raise ApiError(422, VALIDATION, 'Send the file as `content` or as `content_base64`, not both.',
                       fields={'content': ['one of content / content_base64']})
    if args.content is not None:
        raw = args.content.encode('utf-8')
    else:
        try:
            raw = base64.b64decode(args.content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ApiError(422, VALIDATION, 'content_base64 is not valid base64.', fields={'content_base64': ['base64']})
    if len(raw) > settings.MCP_IMPORT_MAX_BYTES:
        raise ApiError(422, VALIDATION, 'The file is too large for this tool.',
                       fields={'content': [f'Larger than {settings.MCP_IMPORT_MAX_BYTES} bytes.']})
    return SimpleUploadedFile(args.filename, raw)


@tool(
    'list_datasets',
    title='List datasets',
    description=(
        'The datasets of a workspace you may see: layers (uploaded or drawn), shared maps, answers to each map '
        'question and respondent rows, with privacy, tags, row counts and how many places use each. Filter by '
        'kind (layer, shared_map, answers, responses), a tag or a name.'
    ),
    scope=scopes.SURVEYS_READ, role='workspace member', read_only=True, idempotent=True,
    args=args_model(
        'ListDatasetsArgs',
        workspace=(Optional[str], Field(None, description='Workspace slug; needed when you belong to several.')),
        kind=(Optional[str], Field(None)), tag=(Optional[str], Field(None)), q=(Optional[str], Field(None)),
    ),
)
def list_datasets(request, args):
    from django.utils.text import slugify
    from data.datasets import catalogue_rows
    p = request.principal
    org = workspace_of(p, args.workspace)
    slug = slugify(args.tag, allow_unicode=True) if args.tag else ''
    items = []
    for row in catalogue_rows(org, p.user):
        ds = row.dataset
        if (args.kind and ds.kind != args.kind) or (args.q and args.q.lower() not in ds.name.lower()):
            continue
        if slug and not ds.tags.filter(slug=slug).exists():
            continue
        items.append(dataset_out(ds, row))
    return {'items': items}


@tool(
    'get_dataset',
    title='Get a dataset',
    description=(
        'One dataset: details (licence, theme, maintainer, update frequency), its field dictionary (names, labels, '
        'types, which are private — private values are never returned), views, versions and the places that use it.'
    ),
    scope=scopes.SURVEYS_READ, role='workspace member', read_only=True, idempotent=True,
    args=args_model('GetDatasetArgs', dataset_id=DATASET),
)
def get_dataset(request, args):
    ds, row = dataset_for(request.principal, args.dataset_id)
    return dataset_out(ds, row, detail=True)


@tool(
    'upload_dataset',
    title='Upload a dataset',
    description=(
        'Create a workspace dataset from a file (GeoJSON, CSV with coordinates, KML, GeoPackage, zipped shapefile). '
        'It runs in the background: poll get_dataset_job until done or failed. A new dataset is private, and columns '
        'that look like emails, phone numbers or names are marked private.'
    ),
    scope=scopes.SURVEYS_WRITE, role='workspace editor',
    args=args_model('UploadDatasetArgs', filename=FILENAME, content=CONTENT, content_base64=CONTENT_B64,
                    workspace=(Optional[str], Field(None, description='Workspace slug.'))),
)
def upload_dataset(request, args):
    org = workspace_of(request.principal, args.workspace, editor=True)
    try:
        job = services.start_upload(actor(request), org, _file(args))
    except services.DataRefused as exc:
        raise refused(exc)
    return job_out(job)


@tool(
    'get_dataset_job',
    title='Check a dataset job',
    description='An upload or a new version: status (queued, running, preview, applying, done, failed), the dataset, and the report or preview counts.',
    scope=scopes.SURVEYS_READ, role='-', read_only=True, idempotent=True,
    args=args_model('GetDatasetJobArgs', job_id=(int, Field(description='The job id an upload returned.'))),
)
def get_dataset_job(request, args):
    return job_out(job_for(request.principal, args.job_id))


@tool(
    'update_dataset',
    title='Describe a dataset',
    description=(
        'Change the details you name: name, description, theme (DCAT-AP code such as ENVI or TRAN), maintainer, '
        'update_frequency, licence (ogl-uk-3.0, cc-by-4.0, cc0-1.0, dl-de-by-2.0), access (public or private; a '
        'dataset shown somewhere stays public) and tags.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('UpdateDatasetArgs', DatasetPatchIn, dataset_id=DATASET),
)
def update_dataset(request, args):
    ds, row = dataset_for(request.principal, args.dataset_id, edit=True)
    body = args.model_dump(exclude_unset=True)
    body.pop('dataset_id', None)
    act = actor(request)
    try:
        details = {k: v for k, v in body.items() if k in services.DETAIL_FIELDS}
        if details:
            services.update_details(act, ds, details, partial=True)
        if 'privacy_class' in body:
            services.set_privacy(act, ds, body['privacy_class'])
        if 'tags' in body:
            services.set_tags(act, ds, body['tags'] or [])
    except services.DataRefused as exc:
        raise refused(exc)
    ds.refresh_from_db()
    return dataset_out(ds, row, detail=True)


@tool(
    'set_dataset_fields',
    title='Label dataset fields',
    description='Labels, types, descriptions and the private flag of named fields of a layer dataset. A private field never reaches a map, an export or the API.',
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('SetDatasetFieldsArgs', dataset_id=DATASET, fields=(List[FieldIn], Field(min_length=1))),
)
def set_dataset_fields(request, args):
    ds, row = dataset_for(request.principal, args.dataset_id, edit=True)
    try:
        services.set_fields(actor(request), ds, [f.model_dump(exclude_unset=True) for f in args.fields])
    except services.DataRefused as exc:
        raise refused(exc)
    return dataset_out(ds, row, detail=True)


@tool(
    'create_dataset_view',
    title='Save a dataset view',
    description=(
        'A named view of a dataset: on a layer, conditions on public fields (eq, in, gt, lt) and the fields it '
        'keeps; on collected answers, always a grid of counts with small groups hidden. Surveys and site map '
        'blocks can show a view instead of the whole dataset.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model('CreateDatasetViewArgs', ViewIn, dataset_id=DATASET),
)
def create_dataset_view(request, args):
    ds, _row = dataset_for(request.principal, args.dataset_id, edit=True)
    try:
        view = services.create_view(actor(request), ds, args.name, args.color or '',
                                    [c.model_dump(exclude_none=True) for c in args.conditions], args.fields)
    except services.DataRefused as exc:
        raise refused(exc)
    return view_out(view)


@tool(
    'upload_dataset_version',
    title='Upload a new dataset version',
    description=(
        'A new file for a layer dataset, matched row by row on its key field. The job stops at preview with '
        'added, changed, removed and unchanged counts — nothing is saved until apply_dataset_version.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model('UploadDatasetVersionArgs', dataset_id=DATASET, filename=FILENAME, content=CONTENT,
                    content_base64=CONTENT_B64),
)
def upload_dataset_version(request, args):
    ds, _row = dataset_for(request.principal, args.dataset_id, edit=True)
    try:
        job = services.start_version(actor(request), ds, _file(args))
    except services.DataRefused as exc:
        raise refused(exc)
    return job_out(job)


@tool(
    'apply_dataset_version',
    title='Apply a dataset version',
    description='Apply a previewed version with a note. Objects whose key stays are updated in place and keep their answers; every survey and site that shows the dataset shows the new version.',
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model('ApplyDatasetVersionArgs', job_id=(int, Field(description='The version job id.')),
                    note=(str, Field('', max_length=300, description='What changed.'))),
)
def apply_dataset_version(request, args):
    job = job_for(request.principal, args.job_id)
    if job.target_id is None:
        raise not_found()
    dataset_for(request.principal, job.target_id, edit=True)
    try:
        job = services.apply_version(actor(request), job, args.note)
    except services.DataRefused as exc:
        raise refused(exc)
    return job_out(job)


@tool(
    'link_dataset',
    title='Show a dataset in a survey',
    description=(
        'Add a public layer dataset (or one of its views) to a survey\'s reference layers — linked, not copied, so '
        'an edit of the dataset shows on the survey. Up to 5,000 objects and 10 layers per survey. Owner role.'
    ),
    scope=scopes.SURVEYS_WRITE, role='owner',
    args=args_model('LinkDatasetArgs', survey=SURVEY, dataset_id=DATASET,
                    view_id=(Optional[int], Field(None, description='A view id from get_dataset.'))),
)
def link_dataset(request, args):
    obj = survey(request, args.survey, role='owner')
    ds, _row = dataset_for(request.principal, args.dataset_id)
    if ds.organization_id != obj.organization_id:
        raise not_found()
    view = None
    if args.view_id is not None:
        view = DatasetView.objects.filter(pk=args.view_id, dataset=ds).first()
        if view is None:
            raise not_found()
    try:
        link = services.link_survey(actor(request), ds, obj, view=view)
    except services.DataRefused as exc:
        raise refused(exc)
    return link_out(link)


@tool(
    'unlink_dataset',
    title='Stop showing a dataset in a survey',
    description='Remove a linked dataset from a survey\'s reference layers; refused while a question of the survey shows it. Owner role.',
    scope=scopes.SURVEYS_WRITE, role='owner',
    args=args_model('UnlinkDatasetArgs', survey=SURVEY, link_id=(int, Field(description='The link id link_dataset returned.'))),
)
def unlink_dataset(request, args):
    from survey.layers import layer_owner
    obj = survey(request, args.survey, role='owner')
    link = DatasetLink.objects.filter(pk=args.link_id, survey=layer_owner(obj)).select_related('dataset', 'survey').first()
    if link is None:
        raise not_found()
    try:
        services.unlink_survey(actor(request), link)
    except services.DataRefused as exc:
        raise refused(exc)
    return {'deleted': args.link_id}
