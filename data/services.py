"""The ONE write path of the Data module (change data-api, #674).

The dataset page, the REST API and the MCP server all call these with an `Actor` and plain values,
never a request — so a refusal reads the same on every surface and a rule is written once (the
private-field rebuild, the link guards, the version job). Refusals raise `DataRefused` with a
message and, for a form, its fields.
"""
import os

from django.utils import timezone
from django.utils.translation import gettext as _

from data.models import DataImportJob, Dataset, DatasetView

UPLOAD_EXTENSIONS = ('.gpkg', '.zip', '.kml', '.geojson', '.json', '.csv')
DETAIL_FIELDS = ('name', 'description', 'theme', 'maintainer', 'update_frequency', 'licence')


class DataRefused(Exception):
    def __init__(self, message, fields=None, status=422):
        super().__init__(message)
        self.message = message
        self.fields = fields or {}
        self.status = status


# ─── Reading: who may see / edit a dataset ────────────────────────────────────

def dataset_row(org, user, dataset_id):
    """The catalogue row of a dataset the member may see, or None (the catalogue's own rule)."""
    from data.datasets import catalogue_rows
    if not Dataset.objects.filter(pk=dataset_id, organization=org).exists():
        return None
    return next((r for r in catalogue_rows(org, user) if r.dataset.pk == dataset_id), None)


def can_edit(user, membership, row):
    if membership is None or membership.role not in ('owner', 'admin', 'editor'):
        return False
    if row.survey is None:
        return True   # a workspace upload: every editor of the workspace
    from survey.permissions import SURVEY_ROLE_RANK, get_effective_survey_role
    return SURVEY_ROLE_RANK.get(get_effective_survey_role(user, row.survey), -1) >= SURVEY_ROLE_RANK['editor']


# ─── Details, privacy, fields, tags ───────────────────────────────────────────

def details_form(data=None, instance=None):
    from django import forms

    class DatasetDetailsForm(forms.ModelForm):
        class Meta:
            model = Dataset
            fields = list(DETAIL_FIELDS)
            widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    form = DatasetDetailsForm(data, instance=instance)
    for name in ('theme', 'update_frequency', 'licence', 'description', 'maintainer'):
        form.fields[name].required = False
    return form


def update_details(actor, ds, values, partial=False):
    """Name, description, theme, maintainer, update frequency, licence (closed lists checked by the
    model form). `partial` keeps what `values` does not name. Raises DataRefused."""
    data = {k: getattr(ds, k) for k in DETAIL_FIELDS} if partial else {}
    data.update({k: v for k, v in values.items() if k in DETAIL_FIELDS})
    for k in DETAIL_FIELDS:
        data.setdefault(k, '')
        if data[k] is None:
            data[k] = ''
    form = details_form(data, instance=ds)
    if not form.is_valid():
        raise DataRefused(_('Check the highlighted fields.'), {k: [str(e) for e in v] for k, v in form.errors.items()})
    return form.save()


def set_privacy(actor, ds, value):
    """Public / private of a layer dataset; a linked dataset stays public (change data-links)."""
    if ds.kind != Dataset.KIND_LAYER:
        raise DataRefused(_('Only a layer dataset’s access can be changed; collected answers stay aggregated.'),
                          {'privacy_class': ['layer only']})
    if value not in (Dataset.PRIVACY_PUBLIC, Dataset.PRIVACY_PRIVATE):
        raise DataRefused(_('Access is public or private.'), {'privacy_class': ['public | private']})
    if value == Dataset.PRIVACY_PRIVATE and ds.links.exists():
        raise DataRefused(_('Linked datasets stay public. Unlink it from every survey and site below first.'),
                          {'privacy_class': ['linked']}, status=409)
    Dataset.objects.filter(pk=ds.pk).update(privacy_class=value)
    ds.privacy_class = value


def set_fields(actor, ds, entries):
    """Replace labels / types / descriptions / private flags for the names the dictionary knows;
    names it does not know are refused. Rebuilds the layer when the private set changes, so every
    surface reading its GeoJSON follows at once. Returns the stored dictionary."""
    from data.fields import FIELD_TYPES, dictionary, hidden_names
    if ds.kind != Dataset.KIND_LAYER:
        raise DataRefused(_('Only a layer dataset has a field dictionary.'), {'fields': ['layer only']})
    current = {f['name']: f for f in dictionary(ds)}
    given = {}
    for e in entries:
        name = e.get('name')
        if name not in current:
            raise DataRefused(_('The dataset has no field “%(name)s”.') % {'name': name}, {'fields': [str(name)]})
        given[name] = e
    before = hidden_names(ds.layer_id)
    stored = []
    for name, f in current.items():
        e = given.get(name)
        if e is None:
            stored.append(f)
            continue
        ftype = e.get('type') if e.get('type') in FIELD_TYPES else f.get('type', 'text')
        stored.append({'name': name,
                       'label': (str(e.get('label') or '').strip()[:200]) or f.get('label') or name,
                       'type': ftype,
                       'description': str(e.get('description') if e.get('description') is not None
                                          else f.get('description', '')).strip()[:500],
                       'private': bool(e['private']) if 'private' in e else bool(f.get('private'))})
    Dataset.objects.filter(pk=ds.pk).update(fields=stored, updated_at=timezone.now())
    ds.fields = stored
    after = frozenset(f['name'] for f in stored if f['private'])
    if after != before and ds.layer_id:
        from survey.layers import rebuild_layer
        from survey.models import SurveyMapLayer
        rebuild_layer(SurveyMapLayer.objects.get(pk=ds.layer_id))
    return stored


def set_tags(actor, ds_or_survey, names):
    from data.tags import set_tags as _set
    org = ds_or_survey.organization
    return _set(org, ds_or_survey, names)


# ─── Views ────────────────────────────────────────────────────────────────────

def create_view(actor, ds, name, color='', conditions=(), fields=()):
    """A view of `ds` (change data-views). `conditions`: [{field, op, value | values}]."""
    from data.dataviews import clean
    raw = {'name': name, 'color': color, 'fields': list(fields or [])}
    for i, c in enumerate(list(conditions or [])[:5]):
        raw[f'field_{i}'] = c.get('field', '')
        raw[f'op_{i}'] = c.get('op', 'eq')
        raw[f'value_{i}'] = ','.join(c['values']) if c.get('op') == 'in' and isinstance(c.get('values'), list) \
            else c.get('value', '')
    values, errors = clean(ds, raw)
    if errors:
        raise DataRefused(next(iter(errors.values())), {k: [v] for k, v in errors.items()})
    return DatasetView.objects.create(dataset=ds, created_by=actor.user, **values)


def delete_view(actor, view):
    if view.links.exists():
        raise DataRefused(_('“%(name)s” is shown in a survey or on a site. Unlink it there first.')
                          % {'name': view.name}, status=409)
    view.delete()


# ─── Uploads and versions ─────────────────────────────────────────────────────

def _check_upload(org, name, size):
    from data.tasks import limits_for
    if os.path.splitext(name or '')[1].lower() not in UPLOAD_EXTENSIONS:
        raise DataRefused(_('Upload a GeoPackage (.gpkg), a zipped shapefile (.zip), KML, GeoJSON or a CSV with coordinate columns.'),
                          {'file': ['format']})
    max_bytes, _features = limits_for(org)
    if size > max_bytes:
        raise DataRefused(_('The file is larger than %(mb)s MB, the limit for this workspace.')
                          % {'mb': max_bytes // (1024 * 1024)}, {'file': ['size']})


def _enqueue(task, *args):
    try:
        task.delay(*args)
    except Exception:  # noqa: BLE001 — no broker: run it here rather than leave the job stuck
        task(*args)


def start_upload(actor, org, file):
    """A new workspace dataset from a file, as a job (change data-upload)."""
    from data.tasks import run_data_import
    _check_upload(org, file.name, file.size)
    job = DataImportJob.objects.create(organization=org, user=actor.user, file=file,
                                       original_name=os.path.basename(file.name)[:255])
    _enqueue(run_data_import, job.pk)
    return job


def start_version(actor, ds, file):
    """A new version of a layer dataset, as a job that stops at `preview` (change data-versions)."""
    from data.tasks import run_data_version
    if not (ds.kind == Dataset.KIND_LAYER and ds.layer_id and ds.layer.source != 'question'):
        raise DataRefused(_('Only a layer of objects takes a new version.'), {'dataset': ['layer only']})
    _check_upload(ds.organization, file.name, file.size)
    DataImportJob.objects.filter(target=ds, status__in=('preview', 'failed', 'done')).delete()
    job = DataImportJob.objects.create(organization=ds.organization, user=actor.user, target=ds, file=file,
                                       original_name=os.path.basename(file.name)[:255])
    _enqueue(run_data_version, job.pk)
    return job


def apply_version(actor, job, note=''):
    from data.tasks import run_data_version
    if job.target_id is None or job.status != 'preview':
        raise DataRefused(_('Only a previewed version can be applied.'), {'job': [job.status]}, status=409)
    job.status = 'applying'
    job.note = str(note or '').strip()[:300]
    job.save(update_fields=['status', 'note'])
    _enqueue(run_data_version, job.pk, True)
    job.refresh_from_db()
    return job


def discard_version(actor, job):
    if job.status in ('preview', 'failed', 'done'):
        if job.file:
            job.file.delete(save=False)
        job.delete()


def delete_dataset(actor, ds):
    """Delete a workspace upload: refused while a question is bound to its layer; site blocks let go
    of it and its links go with it (change data-links)."""
    from django.db import transaction
    from data.links import bound_questions
    from survey.models import SurveyMapLayer
    if not (ds.kind == Dataset.KIND_LAYER and ds.layer_id and ds.layer.survey_id is None):
        raise DataRefused(_('Only a dataset you uploaded is deleted here; a survey’s layer is deleted in its survey.'),
                          status=409)
    questions = bound_questions(ds.layer_id)
    if questions:
        raise DataRefused(_('The question “%(name)s” shows this dataset. Remove the question or pick another layer for it first.')
                          % {'name': questions[0].name}, status=409)
    with transaction.atomic():
        for link in ds.links.filter(site_block__isnull=False).select_related('site_block'):
            block = link.site_block
            block.data = {**(block.data or {}), 'dataset': None, 'view': None, 'choice': ''}
            block.save(update_fields=['data'])
        SurveyMapLayer.objects.filter(pk=ds.layer_id).delete()   # cascades the dataset and its links


# ─── Links ────────────────────────────────────────────────────────────────────

def link_survey(actor, ds, survey, view=None):
    from data.links import LinkRefused, link_survey as _link
    try:
        return _link(ds, survey, actor.user, view=view)
    except LinkRefused as exc:
        raise DataRefused(exc.message, {'dataset': [exc.message]}, status=409) from exc


def unlink_survey(actor, link):
    from data.links import LinkRefused, unlink_survey as _unlink
    try:
        _unlink(link)
    except LinkRefused as exc:
        raise DataRefused(exc.message, {'link': [exc.message]}, status=409) from exc
