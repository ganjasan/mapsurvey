"""Datasets, views, versions and survey links in REST API v1 (change data-api, #674).

Same rules as the editor, because every write is `data.services` with an `Actor`: the catalogue's
visibility, the dataset page's edit rule, private fields never read, collected answers only as a grid
view, links guarded. Scopes are the surveys' (`surveys:read` / `surveys:write`): a dataset is what a
survey's layers and answers became, and a token already handed to an agent keeps working.
"""
from typing import List, Literal, Optional
from uuid import UUID

from ninja import File, Form, Router, Schema, Status
from ninja.files import UploadedFile
from pydantic import ConfigDict, Field

from data import services
from data.models import DataImportJob, Dataset, DatasetLink, DatasetView
from survey.models import Membership
from survey.permissions import ORG_ROLE_RANK, get_org_membership

from .. import gates, scopes
from ..errors import CONFLICT, FORBIDDEN_ROLE, VALIDATION, ApiError, not_found
from . import deps
from .auth import Bearer
from .docs import errors, list_errors

router = Router(tags=['Datasets'])
READ = Bearer(scopes.SURVEYS_READ)
WRITE = Bearer(scopes.SURVEYS_WRITE)
_LAYER_TEXT = ('layer__geojson_gz', 'layer__geojson_legacy')


class _In(Schema):
    model_config = ConfigDict(extra='forbid')


class DatasetPatchIn(_In):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    theme: Optional[str] = Field(None, description='A DCAT-AP theme code (ENVI, TRAN, …) or "".')
    maintainer: Optional[str] = Field(None, max_length=200, description='The team or role that keeps the dataset current.')
    update_frequency: Optional[str] = Field(None, description='as_needed | daily | weekly | monthly | quarterly | yearly | never | "".')
    licence: Optional[str] = Field(None, description='ogl-uk-3.0 | cc-by-4.0 | cc0-1.0 | dl-de-by-2.0 | "".')
    privacy_class: Optional[Literal['public', 'private']] = Field(None, description='Layer datasets only; a linked dataset stays public.')
    tags: Optional[List[str]] = Field(None, max_length=10, description='Replace the workspace tags.')


class FieldIn(_In):
    name: str = Field(description='An existing field name of the dataset.')
    label: Optional[str] = Field(None, max_length=200)
    type: Optional[Literal['text', 'number', 'date', 'boolean']] = None
    description: Optional[str] = Field(None, max_length=500)
    private: Optional[bool] = Field(None, description='A private field never leaves the dataset\'s own editor.')


class FieldsIn(_In):
    fields: List[FieldIn]


class ConditionIn(_In):
    field: str
    op: Literal['eq', 'in', 'gt', 'lt'] = 'eq'
    value: Optional[str] = None
    values: Optional[List[str]] = None


class ViewIn(_In):
    name: str = Field(min_length=1, max_length=120)
    color: Optional[str] = Field(None, description='#rrggbb')
    conditions: List[ConditionIn] = Field(default_factory=list, max_length=5,
                                          description='All must hold. Layer datasets only; collected answers are a grid.')
    fields: List[str] = Field(default_factory=list, description='Public fields the view keeps; empty = all.')


class ApplyIn(_In):
    note: str = Field('', max_length=300, description='What changed, shown in the version history.')


class LinkIn(_In):
    dataset: int
    view: Optional[int] = Field(None, description='A view of the dataset instead of all of it.')


# ─── Helpers shared with the MCP tools ────────────────────────────────────────

def refused(exc):
    """DataRefused → the REST envelope."""
    code = CONFLICT if exc.status == 409 else VALIDATION
    return ApiError(exc.status, code, exc.message, fields=exc.fields or None)


def _member_org_ids(principal):
    qs = Membership.objects.filter(user=principal.user)
    if principal.organization is not None:
        qs = qs.filter(organization=principal.organization)
    return list(qs.values_list('organization_id', flat=True))


def workspace_of(principal, slug, editor=False):
    """The workspace named (or the token's binding / the only membership), gated on its plan."""
    memberships = Membership.objects.filter(user=principal.user).select_related('organization')
    if principal.organization is not None:
        memberships = memberships.filter(organization=principal.organization)
    if slug:
        memberships = memberships.filter(organization__slug=slug)
    memberships = list(memberships)
    if not memberships:
        raise not_found() if slug else ApiError(422, VALIDATION, 'Name a workspace.',
                                                fields={'workspace': ['You belong to no workspace.']})
    if len(memberships) > 1:
        raise ApiError(422, VALIDATION, 'Name a workspace.',
                       fields={'workspace': ['You belong to several workspaces; name one by its slug.']})
    m = memberships[0]
    if editor and ORG_ROLE_RANK.get(m.role, -1) < ORG_ROLE_RANK['editor']:
        raise ApiError(403, FORBIDDEN_ROLE, 'This needs the editor role in the workspace.', role='editor')
    gates.require_pro_api(principal, m.organization)
    return m.organization


def dataset_for(principal, dataset_id, edit=False):
    """(dataset, catalogue row) the caller may see — 404 otherwise; 403 under the edit rule."""
    ds = (Dataset.objects.select_related('layer', 'survey', 'organization').defer(*_LAYER_TEXT)
          .filter(pk=dataset_id, organization_id__in=_member_org_ids(principal)).first())
    if ds is None:
        raise not_found()
    gates.require_pro_api(principal, ds.organization)
    row = services.dataset_row(ds.organization, principal.user, ds.pk)
    if row is None:
        raise not_found()
    if edit and not services.can_edit(principal.user, get_org_membership(principal.user, ds.organization), row):
        raise ApiError(403, FORBIDDEN_ROLE, 'Editing this dataset needs the editor role on it.', role='editor')
    return row.dataset, row


def dataset_out(ds, row=None, detail=False):
    from data.fields import dictionary
    from data.links import used_by
    out = {
        'id': ds.pk, 'name': ds.name, 'kind': ds.kind, 'privacy_class': ds.privacy_class,
        'workspace': ds.organization.slug, 'survey': str(ds.survey.uuid) if ds.survey_id else None,
        'question_code': ds.question_code or None,
        'description': ds.description, 'theme': ds.theme, 'maintainer': ds.maintainer,
        'update_frequency': ds.update_frequency, 'licence': ds.licence,
        'tags': [t.name for t in ds.tags.all()],
        'rows': row.rows if row else None, 'used_by': row.used_by if row else None,
        'updated_at': ds.updated_at,
    }
    if detail:
        out['fields'] = ([{k: f.get(k) for k in ('name', 'label', 'type', 'description', 'private')}
                          for f in dictionary(ds)] if ds.kind == Dataset.KIND_LAYER else [])
        out['key_field'] = ds.layer.key_field if ds.layer_id else None
        out['views'] = [view_out(v) for v in ds.views.all()]
        out['versions'] = [{'number': v.number, 'note': v.note, 'created_at': v.created_at,
                            'added': v.added, 'changed': v.changed, 'removed': v.removed}
                           for v in ds.versions.all()[:20]]
        out['used_by_places'] = [{'kind': p.kind, 'label': p.label} for p in used_by(ds)]
    return out


def view_out(v):
    return {'id': v.pk, 'name': v.name, 'kind': v.kind, 'conditions': v.conditions, 'fields': v.fields,
            'color': v.color}


def job_out(job):
    return {'id': job.pk, 'status': job.status, 'file': job.original_name,
            'dataset': job.dataset_id or job.target_id, 'is_version': job.target_id is not None,
            'report': job.report or {}, 'error': job.error, 'created_at': job.created_at,
            'finished_at': job.finished_at}


def job_for(principal, job_id):
    job = DataImportJob.objects.filter(pk=job_id, user=principal.user).first()
    if job is None:
        raise not_found()
    return job


def link_out(link):
    return {'id': link.pk, 'dataset': link.dataset_id, 'view': link.view_id,
            'survey': str(link.survey.uuid) if link.survey_id else None, 'fields': link.fields}


# ─── Datasets ─────────────────────────────────────────────────────────────────

@router.get('/datasets', response=dict, auth=READ, openapi_extra=list_errors())
def list_datasets(request, workspace: Optional[str] = None, kind: Optional[str] = None,
                  tag: Optional[str] = None, q: Optional[str] = None):
    """The workspace's datasets you may see — layers, shared maps, answers to each map question,
    respondent rows — with their facts. Filter by `kind`, a `tag` (name or slug) or a name `q`."""
    from django.utils.text import slugify
    from data.datasets import catalogue_rows
    p = request.principal
    org = workspace_of(p, workspace)
    rows = catalogue_rows(org, p.user)
    slug = slugify(tag, allow_unicode=True) if tag else ''
    items = []
    for row in rows:
        ds = row.dataset
        if kind and ds.kind != kind:
            continue
        if q and q.lower() not in ds.name.lower():
            continue
        if slug and not ds.tags.filter(slug=slug).exists():
            continue
        items.append(dataset_out(ds, row))
    return {'items': items}


@router.get('/datasets/{dataset_id}', response=dict, auth=READ, openapi_extra=errors())
def get_dataset(request, dataset_id: int):
    """One dataset: details, field dictionary (names and flags; private values never), views,
    versions and every place that uses it."""
    ds, row = dataset_for(request.principal, dataset_id)
    return dataset_out(ds, row, detail=True)


@router.get('/datasets/{dataset_id}/features', auth=READ, openapi_extra=errors(409))
def dataset_features(request, dataset_id: int):
    """A layer dataset's objects as GeoJSON, without private fields. Collected answers leave only
    as a grid: create a view and read its features."""
    from survey.models import SurveyMapLayer
    from survey.views import cached_geojson_response
    ds, _row = dataset_for(request.principal, dataset_id)
    if ds.kind not in Dataset.LAYER_KINDS:
        raise ApiError(409, CONFLICT, 'Collected answers are aggregated: create a view (a grid of counts) and read /datasets/{id}/views/{view}/features.')
    return cached_geojson_response(request, SurveyMapLayer.objects.get(pk=ds.layer_id))


@router.patch('/datasets/{dataset_id}', response=dict, auth=WRITE, openapi_extra=errors(409))
def patch_dataset(request, dataset_id: int, payload: DatasetPatchIn):
    """Details, access and tags; the fields you leave out keep their values."""
    ds, row = dataset_for(request.principal, dataset_id, edit=True)
    actor = deps.actor(request)
    body = payload.dict(exclude_unset=True)
    try:
        details = {k: v for k, v in body.items() if k in services.DETAIL_FIELDS}
        if details:
            services.update_details(actor, ds, details, partial=True)
        if 'privacy_class' in body:
            services.set_privacy(actor, ds, body['privacy_class'])
        if 'tags' in body:
            services.set_tags(actor, ds, body['tags'] or [])
    except services.DataRefused as exc:
        raise refused(exc)
    ds.refresh_from_db()
    return dataset_out(ds, row, detail=True)


@router.put('/datasets/{dataset_id}/fields', response=dict, auth=WRITE, openapi_extra=errors())
def put_fields(request, dataset_id: int, payload: FieldsIn):
    """Labels, types, descriptions and private flags of the named fields (layer datasets)."""
    ds, row = dataset_for(request.principal, dataset_id, edit=True)
    try:
        services.set_fields(deps.actor(request), ds,
                            [f.dict(exclude_unset=True) for f in payload.fields])
    except services.DataRefused as exc:
        raise refused(exc)
    return dataset_out(ds, row, detail=True)


@router.delete('/datasets/{dataset_id}', response=dict, auth=WRITE, openapi_extra=errors(409))
def delete_dataset(request, dataset_id: int):
    """Delete a dataset you uploaded; refused while a question shows it."""
    ds, _row = dataset_for(request.principal, dataset_id, edit=True)
    try:
        services.delete_dataset(deps.actor(request), ds)
    except services.DataRefused as exc:
        raise refused(exc)
    return {'deleted': dataset_id}


@router.post('/datasets', response={202: dict}, auth=WRITE, openapi_extra=errors())
def upload_dataset(request, file: File[UploadedFile], workspace: Form[Optional[str]] = None):
    """A new workspace dataset from a GeoPackage, zipped shapefile, KML, GeoJSON or CSV, as a job.
    Poll `/dataset-jobs/{id}` until `status` is `done` or `failed`; it starts private."""
    p = request.principal
    org = workspace_of(p, workspace, editor=True)
    try:
        job = services.start_upload(deps.actor(request), org, file)
    except services.DataRefused as exc:
        raise refused(exc)
    return Status(202, job_out(job))


@router.post('/datasets/{dataset_id}/versions', response={202: dict}, auth=WRITE, openapi_extra=errors())
def upload_version(request, dataset_id: int, file: File[UploadedFile]):
    """A new version of a layer dataset, matched by its key field. The job stops at `preview` with
    added / changed / removed / unchanged counts; apply it with `/dataset-jobs/{id}/apply`."""
    ds, _row = dataset_for(request.principal, dataset_id, edit=True)
    try:
        job = services.start_version(deps.actor(request), ds, file)
    except services.DataRefused as exc:
        raise refused(exc)
    return Status(202, job_out(job))


@router.get('/dataset-jobs/{job_id}', response=dict, auth=READ, openapi_extra=errors())
def get_job(request, job_id: int):
    """One of your dataset jobs: an upload, or a version (with its preview counts)."""
    return job_out(job_for(request.principal, job_id))


@router.post('/dataset-jobs/{job_id}/apply', response={202: dict}, auth=WRITE, openapi_extra=errors(409))
def apply_job(request, job_id: int, payload: ApplyIn):
    """Apply a previewed version. Objects whose key stays keep their answers."""
    job = job_for(request.principal, job_id)
    if job.target_id is None:
        raise not_found()
    dataset_for(request.principal, job.target_id, edit=True)
    try:
        job = services.apply_version(deps.actor(request), job, payload.note)
    except services.DataRefused as exc:
        raise refused(exc)
    return Status(202, job_out(job))


# ─── Views ────────────────────────────────────────────────────────────────────

@router.post('/datasets/{dataset_id}/views', response={201: dict}, auth=WRITE, openapi_extra=errors())
def create_view(request, dataset_id: int, payload: ViewIn):
    """A saved view: conditions on public fields and the fields it keeps (layers), or a grid of
    counts (collected answers — the privacy class decides)."""
    ds, _row = dataset_for(request.principal, dataset_id, edit=True)
    try:
        view = services.create_view(deps.actor(request), ds, payload.name, payload.color or '',
                                    [c.dict(exclude_none=True) for c in payload.conditions], payload.fields)
    except services.DataRefused as exc:
        raise refused(exc)
    return Status(201, view_out(view))


def _view(request, dataset_id, view_id, edit=False):
    ds, _row = dataset_for(request.principal, dataset_id, edit=edit)
    view = DatasetView.objects.filter(pk=view_id, dataset=ds).select_related('dataset__layer', 'dataset__survey').first()
    if view is None:
        raise not_found()
    return view


@router.get('/datasets/{dataset_id}/views/{view_id}/features', auth=READ, openapi_extra=errors())
def view_features(request, dataset_id: int, view_id: int):
    """A view's GeoJSON: the matching objects with its fields, or the grid cells with their counts."""
    from data.dataviews import geojson_response
    return geojson_response(request, _view(request, dataset_id, view_id))


@router.delete('/datasets/{dataset_id}/views/{view_id}', response=dict, auth=WRITE, openapi_extra=errors(409))
def delete_view(request, dataset_id: int, view_id: int):
    """Delete a view nothing shows."""
    view = _view(request, dataset_id, view_id, edit=True)
    try:
        services.delete_view(deps.actor(request), view)
    except services.DataRefused as exc:
        raise refused(exc)
    return {'deleted': view_id}


# ─── Survey links ─────────────────────────────────────────────────────────────

@router.post('/surveys/{uuid}/datasets', response={201: dict}, auth=WRITE, openapi_extra=errors(409))
def link_dataset(request, uuid: UUID, payload: LinkIn):
    """Show a public layer dataset (or a view of it) among the survey's reference layers — linked,
    not copied. Owner role on the survey."""
    survey = deps.survey(request, uuid, role='owner')
    ds, _row = dataset_for(request.principal, payload.dataset)
    if ds.organization_id != survey.organization_id:
        raise not_found()
    view = None
    if payload.view is not None:
        view = DatasetView.objects.filter(pk=payload.view, dataset=ds).first()
        if view is None:
            raise not_found()
    try:
        link = services.link_survey(deps.actor(request), ds, survey, view=view)
    except services.DataRefused as exc:
        raise refused(exc)
    return Status(201, link_out(link))


@router.delete('/surveys/{uuid}/datasets/{link_id}', response=dict, auth=WRITE, openapi_extra=errors(409))
def unlink_dataset(request, uuid: UUID, link_id: int):
    """Stop showing a linked dataset; refused while a question of the survey shows it."""
    from survey.layers import layer_owner
    survey = deps.survey(request, uuid, role='owner')
    link = DatasetLink.objects.filter(pk=link_id, survey=layer_owner(survey)).select_related('dataset', 'survey').first()
    if link is None:
        raise not_found()
    try:
        services.unlink_survey(deps.actor(request), link)
    except services.DataRefused as exc:
        raise refused(exc)
    return {'deleted': link_id}
