"""A report's public page and the workspace's list of reports (change reports-object, #703)."""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from reports.models import Report
from reports.render import build_context


def report_page(request, slug):
    """Public, read-only report at /r/<slug>/.

    404 unless the report exists and is published. Renders live aggregates or a frozen snapshot.
    Unlisted reports are reachable here but emit noindex and stay out of listings and the sitemap.
    A workspace-only report opens for signed-in members of its workspace alone: an anonymous
    visitor is sent to sign in, anyone else gets the 404 of an unknown address.
    """
    report = get_object_or_404(Report.objects.select_related('survey', 'organization'),
                               slug=slug, is_published=True)
    if report.visibility == 'workspace':
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        from survey.permissions import get_org_membership
        if get_org_membership(request.user, report.organization) is None:
            raise Http404
    lang = request.GET.get('lang') or 'en'
    return render(request, 'public_results.html', build_context(report, lang=lang))


def visible_reports(org, user):
    """The workspace's reports the member may see: those of surveys they have a role on, and
    reports without a home survey."""
    from data.datasets import visible_survey_ids
    from survey.models import SurveyHeader
    visible = visible_survey_ids(org, user)
    # A report keeps the header its tab was opened on; a draft copy or a version answers with
    # its canonical survey.
    family = {}
    for hid, canonical_id, published_id in (SurveyHeader.objects.filter(organization=org)
                                            .values_list('id', 'canonical_survey_id', 'published_version_id')):
        family[hid] = canonical_id or published_id or hid
    rows = []
    for report in (Report.objects.filter(organization=org).select_related('survey')
                   .order_by('-updated_at', '-id')):
        if report.survey_id is None or family.get(report.survey_id) in visible:
            rows.append(report)
    return rows


@login_required
def report_list(request):
    org = getattr(request, 'active_org', None)
    if org is None:
        return redirect('editor')
    from survey.permissions import get_org_membership
    if get_org_membership(request.user, org) is None:
        return redirect('editor')
    from django.db.models import Count
    reports = visible_reports(org, request.user)
    counts = dict(Report.objects.filter(pk__in=[r.pk for r in reports])
                  .annotate(n=Count('blocks')).values_list('pk', 'n'))
    rows = [{'report': r, 'blocks': counts.get(r.pk, 0),
             'public_url': request.build_absolute_uri('/r/{}/'.format(r.slug))} for r in reports]
    return render(request, 'reports/list.html', {'org': org, 'rows': rows})
