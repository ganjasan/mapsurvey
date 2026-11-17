"""The Data catalogue (change data-catalogue, #667)."""
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from data import services
from data.datasets import catalogue_rows
from data.links import used_by
from data.models import DataImportJob, Dataset

UPLOAD_EXTENSIONS = ('.gpkg', '.zip', '.kml', '.geojson', '.json', '.csv')

FILTER_KINDS = [k for k, _label in Dataset.KIND_CHOICES]
FILTER_PRIVACY = [p for p, _label in Dataset.PRIVACY_CHOICES]


@login_required
def catalogue(request):
    org = getattr(request, 'active_org', None)
    if org is None:
        return redirect('editor')
    from survey.permissions import get_org_membership
    if get_org_membership(request.user, org) is None:
        return redirect('editor')
    rows = catalogue_rows(org, request.user)
    kind = request.GET.get('kind') if request.GET.get('kind') in FILTER_KINDS else ''
    privacy = request.GET.get('privacy') if request.GET.get('privacy') in FILTER_PRIVACY else ''
    query = (request.GET.get('q') or '').strip()[:100]
    # Tags (change data-tags): one query for every row's tags, a link per tag to filter by it.
    from data.models import Tag
    row_tags = {}
    for tag in Tag.objects.filter(organization=org).prefetch_related('datasets'):
        for ds_id in tag.datasets.values_list('pk', flat=True):
            row_tags.setdefault(ds_id, []).append(tag)
    tag = request.GET.get('tag') or ''
    for row in rows:
        row.extra['tags'] = row_tags.get(row.dataset.pk, [])
    counts_kind = {k: 0 for k in FILTER_KINDS}
    counts_privacy = {p: 0 for p in FILTER_PRIVACY}
    for row in rows:
        counts_kind[row.dataset.kind] += 1
        counts_privacy[row.dataset.privacy_class] += 1
    shown = [r for r in rows
             if (not kind or r.dataset.kind == kind)
             and (not privacy or r.dataset.privacy_class == privacy)
             and (not tag or any(t.slug == tag for t in r.extra['tags']))
             and (not query or query.lower() in r.dataset.name.lower()
                  or (r.survey is not None and query.lower() in r.survey.name.lower()))]
    shown.sort(key=lambda r: (r.survey.name.lower() if r.survey else '', FILTER_KINDS.index(r.dataset.kind),
                              r.dataset.name.lower()))
    return render(request, 'data/catalogue.html', {
        'org': org,
        **_jobs_context(org, request.user),
        'can_upload': _can_upload(request.user, org),
        'rows': shown,
        'total': len(rows),
        'kind': kind, 'privacy': privacy, 'q': query, 'tag': tag,
        'tag_filters': sorted({t.slug: t for ts in row_tags.values() for t in ts}.values(), key=lambda t: t.name.lower()),
        'kind_filters': [(k, label, counts_kind[k]) for k, label in Dataset.KIND_CHOICES],
        'privacy_filters': [(p, label, counts_privacy[p]) for p, label in Dataset.PRIVACY_CHOICES],
    })


def _member(request):
    org = getattr(request, 'active_org', None)
    if org is None:
        return None, None
    from survey.permissions import get_org_membership
    return org, get_org_membership(request.user, org)


def _can_upload(user, org):
    from survey.permissions import get_org_membership
    m = get_org_membership(user, org)
    return m is not None and m.role in ('owner', 'admin', 'editor')


def _jobs(org, user):
    """The member's open import jobs and those finished in the last 24 h."""
    since = timezone.now() - timezone.timedelta(hours=24)
    from django.db.models import Q
    return list(DataImportJob.objects.filter(organization=org, user=user, target__isnull=True)
                .filter(Q(status__in=('queued', 'running')) | Q(finished_at__gte=since))
                .select_related('dataset')[:10])


def _jobs_context(org, user):
    jobs = _jobs(org, user)
    return {'jobs': jobs, 'jobs_open': any(j.status in ('queued', 'running') for j in jobs)}


@login_required
@require_POST
def upload(request):
    """Store the file on the private tier and start the import job (change data-upload)."""
    org, membership = _member(request)
    if org is None or membership is None or membership.role not in ('owner', 'admin', 'editor'):
        return redirect('editor_data')
    upload = request.FILES.get('file')
    if upload is None:
        return redirect('editor_data')
    try:
        services.start_upload(_actor(request), org, upload)
    except services.DataRefused as exc:
        messages.error(request, exc.message)
    return redirect('editor_data')


def _actor(request):
    from survey.services.context import Actor
    return Actor.from_request(request)


@login_required
def jobs(request):
    """The job cards, polled by the catalogue while a job is open."""
    org, membership = _member(request)
    if org is None or membership is None:
        raise Http404
    return render(request, 'data/_jobs.html', _jobs_context(org, request.user))


@login_required
@require_POST
def dismiss(request, job_id):
    org, membership = _member(request)
    if org is None or membership is None:
        raise Http404
    job = get_object_or_404(DataImportJob, pk=job_id, organization=org, user=request.user)
    if job.status in ('done', 'failed'):
        job.delete()
    return redirect('editor_data')


# ─── The dataset page (change data-metadata, #669) ───────────────────────────

def _dataset_row(request, dataset_id):
    """(org, membership, row) for a dataset the member may see — 404 otherwise. The catalogue's
    own visibility rule decides, so the page and the list can never disagree."""
    org, membership = _member(request)
    if org is None or membership is None:
        raise Http404
    row = services.dataset_row(org, request.user, dataset_id)
    if row is None:
        raise Http404
    return org, membership, row


_can_edit = services.can_edit
_details_form = services.details_form


@login_required
def dataset(request, dataset_id):
    from data.fields import FIELD_TYPES, dictionary
    org, membership, row = _dataset_row(request, dataset_id)
    ds = row.dataset
    can_edit = _can_edit(request.user, membership, row)
    form = _details_form(instance=ds)
    view_errors = {}
    if request.method == 'POST':
        if not can_edit:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden()
        action = request.POST.get('action')
        if action == 'details':
            form = _details_form(request.POST, instance=ds)
            if form.is_valid():
                services.update_details(_actor(request), ds, request.POST)
                services.set_tags(_actor(request), ds, request.POST.get('tags', ''))
                messages.success(request, _('Details saved.'))
                return redirect('editor_data_dataset', dataset_id=ds.pk)
        elif action == 'fields' and ds.kind == Dataset.KIND_LAYER:
            _save_dictionary(request, ds)
            messages.success(request, _('Field dictionary saved.'))
            return redirect('editor_data_dataset', dataset_id=ds.pk)
        elif action == 'view_create':
            errors = _create_view(request, ds)
            if errors:
                view_errors = errors
            else:
                messages.success(request, _('View saved.'))
                return redirect('editor_data_dataset', dataset_id=ds.pk)
        elif action == 'view_delete':
            _delete_view(request, ds)
            return redirect('editor_data_dataset', dataset_id=ds.pk)
        elif action in ('version', 'apply', 'discard') and _versionable(ds):
            _version_action(request, ds, action)
            return redirect('editor_data_dataset', dataset_id=ds.pk)
        elif action == 'privacy' and ds.kind == Dataset.KIND_LAYER:
            try:
                services.set_privacy(_actor(request), ds, request.POST.get('privacy_class'))
            except services.DataRefused as exc:
                messages.error(request, exc.message)
            return redirect('editor_data_dataset', dataset_id=ds.pk)
    version_job = _version_job(ds) if _versionable(ds) else None
    return render(request, 'data/dataset.html', {
        'org': org,
        'row': row,
        'ds': ds,
        'form': form,
        'can_edit': can_edit,
        'fields': dictionary(ds) if ds.kind == Dataset.KIND_LAYER else [],
        'field_types': FIELD_TYPES,
        'has_dictionary': ds.kind == Dataset.KIND_LAYER,
        'used_by': used_by(ds),
        'tags_text': ', '.join(t.name for t in ds.tags.all()),
        'can_delete': can_edit and _deletable(ds),
        'versionable': _versionable(ds),
        'version_job': version_job,
        'can_upload_version': (can_edit and _versionable(ds) and bool(ds.layer.key_field)
                               and (version_job is None or version_job.status in ('done', 'failed'))),
        'versions': list(ds.versions.select_related('created_by')[:20]),
        **_views_context(ds),
        'view_errors': view_errors,
        'posted_kind': request.POST.get('kind', '') if view_errors else '',
        'condition_rows': range(3),
    })


def _views_context(ds):
    """The views card (change data-views): the dataset's views with how many places use each."""
    from django.db.models import Count
    from django.urls import reverse
    from data import responses_views
    from data.dataviews import crosstab_questions, kind_for, kind_labels, kinds_for, public_fields
    from data.models import DatasetView
    kind = kind_for(ds)
    if kind is None:
        return {'view_kind': None}
    labels = public_fields(ds) if kind == 'objects' else {}
    views = list(ds.views.annotate(link_uses=Count('links', distinct=True),
                                   block_uses=Count('report_blocks', distinct=True)).order_by('name'))
    questions = crosstab_questions(ds) if ds.kind == Dataset.KIND_RESPONSES else []
    names = {q.code: q.name or q.code for q in questions}
    for v in views:   # labels, not raw names, in the summary (change data-metadata)
        v.uses = v.link_uses + v.block_uses
        v.summary = [{**c, 'label': labels.get(c.get('field'), c.get('field'))} for c in v.conditions or []]
        v.detail, v.open_url = '', ''
        if v.kind == DatasetView.KIND_RESPONSES:
            v.detail, v.open_url = responses_views.summary(v), responses_views.open_url(v)
        elif v.kind != DatasetView.KIND_OBJECTS:
            v.open_url = reverse('editor_data_view', args=[ds.pk, v.pk])
            if v.kind == DatasetView.KIND_CROSSTAB:
                config = v.config or {}
                v.detail = '%s × %s' % (names.get(config.get('rows'), config.get('rows')),
                                       names.get(config.get('columns'), config.get('columns')))
    # A Responses filter is saved on the Responses page, never typed here.
    creatable = [k for k in kinds_for(ds) if k != DatasetView.KIND_RESPONSES]
    return {
        'view_kind': kind,
        'dataset_views': views,
        'view_kind_choices': kind_labels(creatable),
        'crosstab_questions': questions,
        'view_fields': list(public_fields(ds).items()) if kind == 'objects' else [],
    }


def _create_view(request, ds):
    conditions = []
    for i in range(5):
        field = request.POST.get(f'field_{i}')
        if not field:
            continue
        op = request.POST.get(f'op_{i}') or 'eq'
        value = request.POST.get(f'value_{i}') or ''
        conditions.append({'field': field, 'op': op, 'values': [v.strip() for v in value.split(',') if v.strip()]}
                          if op == 'in' else {'field': field, 'op': op, 'value': value})
    kind = request.POST.get('kind') or ''
    if kind == 'responses':
        return {'kind': _('A Responses filter is saved on the Responses page.')}
    try:
        services.create_view(_actor(request), ds, request.POST.get('name', ''), request.POST.get('color', ''),
                             conditions, request.POST.getlist('fields'), kind=kind,
                             config={'rows': request.POST.get('rows', ''), 'columns': request.POST.get('columns', '')})
    except services.DataRefused as exc:
        return {k: v[0] for k, v in exc.fields.items()} or {'name': exc.message}
    return {}


@login_required
def view_preview(request, dataset_id, view_id):
    """What a computed view yields, as its readers will get it (change data-analysis-views): a
    table for a cross-tab, the three steps and their series for engagement, a summary of the cells
    for a grid, coverage or density. Masked for everyone — this is the published result."""
    from data.dataviews import result
    from data.models import DatasetView
    org, _membership, row = _dataset_row(request, dataset_id)
    view = get_object_or_404(DatasetView.objects.select_related('dataset__survey'), pk=view_id, dataset=row.dataset)
    if view.kind in (DatasetView.KIND_OBJECTS, DatasetView.KIND_RESPONSES):
        raise Http404
    data = result(view, lang=getattr(request, 'LANGUAGE_CODE', 'en') or 'en')
    context = {'org': org, 'ds': row.dataset, 'view': view, 'data': data}
    if view.kind == DatasetView.KIND_CROSSTAB and 'cells' in data:
        context['table_rows'] = [{'item': item, 'cells': data['cells'][i]}
                                 for i, item in enumerate(data['rows']['items'])]
    return render(request, 'data/view.html', context)


def _delete_view(request, ds):
    view = ds.views.filter(pk=request.POST.get('view') or 0).first()
    if view is None:
        return
    try:
        services.delete_view(_actor(request), view)
    except services.DataRefused as exc:
        messages.error(request, exc.message)


def _versionable(ds):
    """A layer of objects (not a shared map) can take a new version (change data-versions)."""
    return ds.kind == Dataset.KIND_LAYER and ds.layer_id is not None and ds.layer.source != 'question'


def _version_job(ds):
    """The version job the page shows: an open one, or one that finished in the last hour."""
    since = timezone.now() - timezone.timedelta(hours=1)
    from django.db.models import Q
    return (DataImportJob.objects.filter(target=ds)
            .filter(Q(status__in=('queued', 'running', 'preview', 'applying')) | Q(finished_at__gte=since))
            .select_related('user').first())


def _version_action(request, ds, action):
    """Upload a version file (→ preview), apply a previewed version with a note, or discard it."""
    try:
        if action == 'version':
            upload = request.FILES.get('file')
            if upload is not None:
                services.start_version(_actor(request), ds, upload)
            return
        job = DataImportJob.objects.filter(target=ds, pk=request.POST.get('job') or 0).first()
        if job is None:
            return
        if action == 'discard':
            services.discard_version(_actor(request), job)
        elif job.status == 'preview':
            services.apply_version(_actor(request), job, request.POST.get('note') or '')
    except services.DataRefused as exc:
        messages.error(request, exc.message)


def _deletable(ds):
    """Only a workspace upload is deleted here; a survey's layer is deleted in its survey."""
    return ds.kind == Dataset.KIND_LAYER and ds.layer_id is not None and ds.layer.survey_id is None


@login_required
def delete(request, dataset_id):
    """Every place that uses the dataset first, then the confirm (change data-links). Refused
    while a question is bound to its layer; links and site blocks let go of it otherwise."""
    from data.links import bound_questions
    org, membership, row = _dataset_row(request, dataset_id)
    ds = row.dataset
    if not (_can_edit(request.user, membership, row) and _deletable(ds)):
        raise Http404
    questions = bound_questions(ds.layer_id)
    if request.method == 'POST' and not questions:
        services.delete_dataset(_actor(request), ds)
        messages.success(request, _('Dataset deleted.'))
        return redirect('editor_data')
    return render(request, 'data/delete.html', {
        'org': org, 'ds': ds, 'used_by': used_by(ds), 'questions': questions,
        'refused': request.method == 'POST',
    })


def _save_dictionary(request, ds):
    """The table's rows as entries for `services.set_fields` (a row whose name changed under the
    form is left as stored)."""
    from data.fields import dictionary
    entries = []
    for i, f in enumerate(dictionary(ds)):
        if request.POST.get(f'name_{i}') != f['name']:
            continue
        entries.append({'name': f['name'], 'label': request.POST.get(f'label_{i}') or '',
                        'type': request.POST.get(f'type_{i}'),
                        'description': request.POST.get(f'description_{i}') or '',
                        'private': request.POST.get(f'private_{i}') == '1'})
    services.set_fields(_actor(request), ds, entries)


@login_required
def download(request, dataset_id):
    """A layer dataset as CSV or GeoJSON: public fields only, labels as column names / keys."""
    import csv
    import io
    import json
    from django.http import StreamingHttpResponse
    from django.utils.text import slugify
    from data.fields import labels
    _org, _membership, row = _dataset_row(request, dataset_id)
    ds = row.dataset
    if ds.kind != Dataset.KIND_LAYER:
        raise Http404
    fmt = request.GET.get('format', 'csv')
    if fmt not in ('csv', 'geojson'):
        raise Http404
    label_map = labels(ds.layer_id)
    if not ds.fields:   # an undocumented survey layer: its (public) property names, raw
        label_map = {n: n for n in (ds.layer.property_names or [])}
    columns, used = [], {'key', 'title', 'category', 'lon', 'lat', 'wkt'}
    for name, label in label_map.items():
        out = label if label not in used else f'{label} ({name})'
        used.add(out)
        columns.append((name, out))
    from survey.models import LayerObject
    objects = (LayerObject.objects.filter(layer_id=ds.layer_id).order_by('position', 'id')
               .values('key', 'title', 'category', 'properties', 'geometry'))
    filename = slugify(ds.name) or 'dataset'

    def csv_rows():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['key', 'title', 'category', 'lon', 'lat', 'wkt'] + [c for _n, c in columns])
        for o in objects.iterator(chunk_size=500):
            props = o['properties'] if isinstance(o['properties'], dict) else {}
            c = o['geometry'].centroid
            writer.writerow([o['key'], o['title'], o['category'], round(c.x, 7), round(c.y, 7), o['geometry'].wkt]
                            + [_csv_cell(props.get(n)) for n, _c in columns])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()

    def geojson_parts():
        yield '{"type":"FeatureCollection","features":['
        first = True
        for o in objects.iterator(chunk_size=500):
            props = o['properties'] if isinstance(o['properties'], dict) else {}
            feature = {'type': 'Feature', 'geometry': json.loads(o['geometry'].geojson),
                       'properties': {'key': o['key'], 'title': o['title'], 'category': o['category'],
                                      **{c: props.get(n) for n, c in columns}}}
            yield ('' if first else ',') + json.dumps(feature, ensure_ascii=False)
            first = False
        yield ']}'

    if fmt == 'csv':
        response = StreamingHttpResponse(csv_rows(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    else:
        response = StreamingHttpResponse(geojson_parts(), content_type='application/geo+json')
        response['Content-Disposition'] = f'attachment; filename="{filename}.geojson"'
    return response


def _csv_cell(value):
    """A property value as a CSV cell; a formula-looking text is apostrophe-guarded."""
    if value is None:
        return ''
    text = value if isinstance(value, str) else str(value)
    return "'" + text if text[:1] in ('=', '+', '-', '@') and not _is_number(text) else text


def _is_number(text):
    try:
        float(text)
        return True
    except ValueError:
        return False
