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
