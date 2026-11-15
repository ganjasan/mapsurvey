"""The Data catalogue (change data-catalogue, #667)."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from data.datasets import catalogue_rows
from data.models import Dataset

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
        'rows': shown,
        'total': len(rows),
        'kind': kind, 'privacy': privacy, 'q': query,
        'kind_filters': [(k, label, counts_kind[k]) for k, label in Dataset.KIND_CHOICES],
        'privacy_filters': [(p, label, counts_privacy[p]) for p, label in Dataset.PRIVACY_CHOICES],
    })
