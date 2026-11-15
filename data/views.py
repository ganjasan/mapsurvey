"""The Data catalogue (change data-catalogue, #667)."""
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

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
    counts_kind = {k: 0 for k in FILTER_KINDS}
    counts_privacy = {p: 0 for p in FILTER_PRIVACY}
    for row in rows:
        counts_kind[row.dataset.kind] += 1
        counts_privacy[row.dataset.privacy_class] += 1
    shown = [r for r in rows
             if (not kind or r.dataset.kind == kind)
             and (not privacy or r.dataset.privacy_class == privacy)
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
        'kind': kind, 'privacy': privacy, 'q': query,
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
    return list(DataImportJob.objects.filter(organization=org, user=user)
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
    ext = os.path.splitext(upload.name)[1].lower()
    if ext not in UPLOAD_EXTENSIONS:
        messages.error(request, _('Upload a GeoPackage (.gpkg), a zipped shapefile (.zip), KML, GeoJSON or a CSV with coordinate columns.'))
        return redirect('editor_data')
    from data.tasks import limits_for, run_data_import
    max_bytes, _features = limits_for(org)
    if upload.size > max_bytes:
        messages.error(request, _('The file is larger than %(mb)s MB, the limit for this workspace.')
                       % {'mb': max_bytes // (1024 * 1024)})
        return redirect('editor_data')
    job = DataImportJob.objects.create(organization=org, user=request.user, file=upload,
                                       original_name=os.path.basename(upload.name)[:255])
    try:
        run_data_import.delay(job.pk)
    except Exception:  # noqa: BLE001 — no broker: run it here rather than leave the card stuck
        run_data_import(job.pk)
    return redirect('editor_data')


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
    get_object_or_404(Dataset, pk=dataset_id, organization=org)
    row = next((r for r in catalogue_rows(org, request.user) if r.dataset.pk == dataset_id), None)
    if row is None:
        raise Http404
    return org, membership, row


def _can_edit(user, membership, row):
    if membership.role not in ('owner', 'admin', 'editor'):
        return False
    if row.survey is None:
        return True   # a workspace upload: every editor of the workspace
    from survey.permissions import SURVEY_ROLE_RANK, get_effective_survey_role
    role = get_effective_survey_role(user, row.survey)
    return SURVEY_ROLE_RANK.get(role, -1) >= SURVEY_ROLE_RANK['editor']


def _details_form(data=None, instance=None):
    from django import forms

    class DatasetDetailsForm(forms.ModelForm):
        class Meta:
            model = Dataset
            fields = ['name', 'description', 'theme', 'maintainer', 'update_frequency', 'licence']
            widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    form = DatasetDetailsForm(data, instance=instance)
    for name in ('theme', 'update_frequency', 'licence'):
        form.fields[name].required = False
    return form


@login_required
def dataset(request, dataset_id):
    from data.fields import FIELD_TYPES, dictionary
    org, membership, row = _dataset_row(request, dataset_id)
    ds = row.dataset
    can_edit = _can_edit(request.user, membership, row)
    form = _details_form(instance=ds)
    if request.method == 'POST':
        if not can_edit:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden()
        action = request.POST.get('action')
        if action == 'details':
            form = _details_form(request.POST, instance=ds)
            if form.is_valid():
                form.save()
                messages.success(request, _('Details saved.'))
                return redirect('editor_data_dataset', dataset_id=ds.pk)
        elif action == 'fields' and ds.kind == Dataset.KIND_LAYER:
            _save_dictionary(request, ds)
            messages.success(request, _('Field dictionary saved.'))
            return redirect('editor_data_dataset', dataset_id=ds.pk)
        elif action == 'privacy' and ds.kind == Dataset.KIND_LAYER:
            value = request.POST.get('privacy_class')
            if value == Dataset.PRIVACY_PRIVATE and ds.links.exists():
                # A private dataset cannot sit in a public surface (change data-links).
                messages.error(request, _('Linked datasets stay public. Unlink it from every survey and site below first.'))
            elif value in (Dataset.PRIVACY_PUBLIC, Dataset.PRIVACY_PRIVATE):
                Dataset.objects.filter(pk=ds.pk).update(privacy_class=value)
            return redirect('editor_data_dataset', dataset_id=ds.pk)
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
        'can_delete': can_edit and _deletable(ds),
    })


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
        from django.db import transaction
        from survey.models import SiteBlock, SurveyMapLayer
        with transaction.atomic():
            for link in ds.links.filter(site_block__isnull=False).select_related('site_block'):
                block = link.site_block
                block.data = {**(block.data or {}), 'dataset': None}
                block.save(update_fields=['data'])
            SurveyMapLayer.objects.filter(pk=ds.layer_id).delete()   # cascades the dataset and its links
        messages.success(request, _('Dataset deleted.'))
        return redirect('editor_data')
    return render(request, 'data/delete.html', {
        'org': org, 'ds': ds, 'used_by': used_by(ds), 'questions': questions,
        'refused': request.method == 'POST',
    })


def _save_dictionary(request, ds):
    """Store labels, types, descriptions and private flags for the names the dictionary knows;
    rebuild the layer's derived GeoJSON when the private set changed, so every surface reading
    it follows at once."""
    from data.fields import FIELD_TYPES, dictionary, hidden_names
    before = hidden_names(ds.layer_id)
    entries = []
    for i, f in enumerate(dictionary(ds)):
        if request.POST.get(f'name_{i}') != f['name']:
            entries.append(f)   # the page changed under the form: keep what is stored
            continue
        ftype = request.POST.get(f'type_{i}')
        entries.append({
            'name': f['name'],
            'label': (request.POST.get(f'label_{i}') or '').strip()[:200] or f['name'],
            'type': ftype if ftype in FIELD_TYPES else f.get('type', 'text'),
            'description': (request.POST.get(f'description_{i}') or '').strip()[:500],
            'private': request.POST.get(f'private_{i}') == '1',
        })
    Dataset.objects.filter(pk=ds.pk).update(fields=entries, updated_at=timezone.now())
    after = frozenset(f['name'] for f in entries if f['private'])
    if after != before and ds.layer_id:
        from survey.layers import rebuild_layer
        from survey.models import SurveyMapLayer
        rebuild_layer(SurveyMapLayer.objects.get(pk=ds.layer_id))


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
