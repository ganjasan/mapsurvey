"""A report's public page and the workspace's list of reports (change reports-object, #703)."""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from django.utils.translation import gettext as _

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
    from reports import gate
    gate.freeze_if_lapsed(report)       # no Reports feature: the page is its snapshot, never a 404
    from reports import usage
    usage.count(request, report, 'embed' if request.GET.get('embed') == '1' else 'view')
    lang = request.GET.get('lang') or 'en'
    return render(request, 'public_results.html', _framed_context(request, report, build_context(report, lang=lang)))


def _guard(request, slug):
    """The published report at `slug` for this visitor, or a response that says why not."""
    report = get_object_or_404(Report.objects.select_related('survey', 'organization'),
                               slug=slug, is_published=True)
    if report.visibility == 'workspace':
        if not request.user.is_authenticated:
            return None, redirect_to_login(request.get_full_path())
        from survey.permissions import get_org_membership
        if get_org_membership(request.user, report.organization) is None:
            raise Http404
    from reports import gate
    gate.freeze_if_lapsed(report)
    return report, None


def _framed_context(request, report, context):
    """Mark the response framable by the report's allowed hosts and tell the template whether it
    is shown inside someone's page (`?embed=1`), plus the oEmbed address of this page."""
    from urllib.parse import urlencode
    from django.urls import reverse
    from reports import embed
    from survey.embedding import public_base_url
    embed.mark(request, report)
    context['embed'] = request.GET.get('embed') == '1'
    if embed.embeddable(report):
        target = public_base_url(request) + request.path
        context['oembed_url'] = public_base_url(request) + reverse('oembed') + '?' + urlencode(
            {'url': target, 'format': 'json'})
    return context


def _block_payload(report, block_id, lang='en'):
    from reports.render import render_data
    payload = next((b for b in render_data(report, lang=lang)['blocks'] if b.get('id') == block_id), None)
    if payload is None:
        raise Http404
    return payload


def report_block(request, slug, block_id):
    """One block of a published report on a page of its own — what a single-block embed frames."""
    report, refusal = _guard(request, slug)
    if refusal is not None:
        return refusal
    lang = request.GET.get('lang') or 'en'
    context = build_context(report, lang=lang)
    payload = _block_payload(report, block_id, lang)
    from reports import usage
    usage.count(request, report, 'embed' if request.GET.get('embed') == '1' else 'view')
    context.update(rows=[[dict(payload, width='full')]], blocks=[payload], single=True,
                   blocks_json=__import__('json').dumps([payload], ensure_ascii=False),
                   intro_title=payload.get('title') or context['intro_title'])
    return render(request, 'public_results.html', _framed_context(request, report, context))


def report_block_csv(request, slug, block_id):
    """The numbers of one block of a published report as CSV — masked as the page is."""
    from django.http import HttpResponse
    from reports.tables import block_csv
    report, refusal = _guard(request, slug)
    if refusal is not None:
        return refusal
    table = block_csv(_block_payload(report, block_id))
    if table is None:
        raise Http404
    response = HttpResponse(table[1], content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{table[0]}"'
    return response


@login_required
def report_block_file(request, report_uuid, block_id, kind):
    """An editor's download of one block, published or not: `csv` or `png`."""
    from django.http import HttpResponse
    from reports.pictures import block_png
    from reports.render import ReportService
    from reports.sources import attach_questions
    from reports.tables import block_csv, file_stem
    report = _editable_report(request, report_uuid)
    blocks = attach_questions(report.blocks.filter(pk=block_id).select_related('dataset__survey', 'view__dataset__survey'))
    if not blocks:
        raise Http404
    payload = ReportService(report)._build_block(blocks[0])
    if payload is None:
        raise Http404
    if kind == 'csv':
        table = block_csv(payload)
        if table is None:
            raise Http404
        response = HttpResponse(table[1], content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{table[0]}"'
        return response
    picture = block_png(payload, report.survey if report.survey_id else None)
    if picture is None:
        raise Http404
    response = HttpResponse(picture, content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="{file_stem(payload)}.png"'
    return response


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
                   .prefetch_related('tags').order_by('-updated_at', '-id')):
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
    tag = request.GET.get('tag') or ''
    all_tags = sorted({t.slug: t for r in reports for t in r.tags.all()}.values(), key=lambda t: t.name.lower())
    if tag:
        reports = [r for r in reports if any(t.slug == tag for t in r.tags.all())]
    counts = dict(Report.objects.filter(pk__in=[r.pk for r in reports])
                  .annotate(n=Count('blocks')).values_list('pk', 'n'))
    rows = [{'report': r, 'blocks': counts.get(r.pk, 0),
             'public_url': request.build_absolute_uri('/r/{}/'.format(r.slug))} for r in reports]
    return render(request, 'reports/list.html', {'org': org, 'rows': rows, 'can_edit': _can_edit(request.user, org),
                                                 'reports_locked': not _may_write(org),
                                                 'tag': tag, 'tag_filters': all_tags})


# ── The report as a file, and deleting one (change reports-story, #704) ──────

def _may_write(org):
    from reports import gate
    return gate.may_write(org)


def _can_edit(user, org):
    from survey.permissions import get_org_membership
    membership = get_org_membership(user, org)
    return membership is not None and membership.role in ('owner', 'admin', 'editor')


def _editable_report(request, report_uuid):
    from reports.editor_views import may_edit_report
    report = get_object_or_404(Report.objects.select_related('survey', 'organization'), uuid=report_uuid)
    if not may_edit_report(request, report):
        raise Http404
    return report


@login_required
def report_start(request):
    """Ways to start a report (change reports-start, #705): a draft made from a survey by rules in
    one of four arrangements, a blank report, or a copy of an earlier one. One click on a card
    does it — every card is the submit button of its own form."""
    from django.contrib import messages
    from data.datasets import visible_survey_ids
    from reports import drafting, services
    from survey import product_events as pe
    from survey.models import SurveyHeader
    from survey.services.context import Actor
    org = getattr(request, 'active_org', None)
    if org is None or not _can_edit(request.user, org):
        raise Http404
    surface = request.GET.get('from') or request.POST.get('from') or 'reports'
    if surface not in ('reports', 'responses', 'data', 'survey'):
        surface = 'reports'
    surveys = list(SurveyHeader.objects.filter(id__in=visible_survey_ids(org, request.user))
                   .exclude(status='draft').order_by('-id'))
    chosen = next((s for s in surveys if str(s.uuid) == (request.GET.get('survey') or request.POST.get('survey'))), None)

    if request.method == 'POST':
        from reports import gate
        from reports.editor_views import paywall
        if not gate.use(org, request.user):
            return paywall(request, org, 'start')
        actor = Actor.from_request(request)
        kind = request.POST.get('kind')
        template = ''
        if kind == 'draft' and chosen is not None:
            template = request.POST.get('template') if request.POST.get('template') in drafting.TEMPLATES else 'summary'
            report = drafting.build_draft(actor, chosen, template)
        elif kind == 'copy':
            source = next((r for r in visible_reports(org, request.user)
                           if str(r.uuid) == request.POST.get('report')), None)
            if source is None:
                raise Http404
            report = drafting.copy_report(actor, source)
        elif kind == 'blank':
            report = services.create_report(actor, org, title=str(_('Untitled report')), visibility='workspace')
        else:
            messages.error(request, _('Choose a survey to draft a report from.'))
            return redirect('editor_report_start')
        pe.emit(pe.REPORT_CREATED, request.user.pk,
                {'report_id': str(report.pk), 'surface': surface, 'start': kind, 'template': template})
        return redirect('editor_report', report_uuid=report.uuid)

    pe.emit(pe.REPORT_ENTRY_SEEN, request.user.pk, {'surface': surface})
    return render(request, 'reports/start.html', {
        'org': org, 'surveys': surveys, 'chosen': chosen or (surveys[0] if surveys else None),
        'templates': [(key, value['label'], value['what']) for key, value in drafting.TEMPLATES.items()],
        'earlier': visible_reports(org, request.user)[:30], 'surface': surface,
        'reports_locked': not _may_write(org),
    })


# ── The PDF (change reports-pdf, #707): asked for here, rendered on the worker ──

def _pdf_response(job, report, user_id, surface):
    from django.http import FileResponse
    from survey import product_events as pe
    pe.emit(pe.REPORT_PDF_DOWNLOADED, user_id, {'report_id': str(report.pk), 'surface': surface})
    if job.kind == 'zip':
        response = FileResponse(job.file.open('rb'), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{report.slug}-charts-and-maps.zip"'
        return response
    response = FileResponse(job.file.open('rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{report.slug}.pdf"'
    return response


@login_required
def report_pdf(request, report_uuid):
    """POST asks for a PDF and answers with the job to poll; GET ?job=<id> answers its state, and
    GET ?job=<id>&download=1 serves the file once it is done."""
    from django.http import JsonResponse
    from reports import services
    from survey.services.context import Actor
    report = _editable_report(request, report_uuid)
    if request.method == 'POST':
        job = services.request_pdf(Actor.from_request(request), report, base_url=request.build_absolute_uri('/')[:-1],
                                   kind=request.POST.get('kind') or 'pdf')
    else:
        job = get_object_or_404(report.pdfs, pk=request.GET.get('job') or 0)
        if request.GET.get('download') and job.status == 'done' and job.file:
            return _pdf_response(job, report, request.user.pk, 'editor')
    url = '{}?job={}&download=1'.format(request.path, job.pk) if job.status == 'done' else ''
    return JsonResponse({'job': job.pk, 'status': job.status, 'url': url,
                         'error': bool(job.error)}, status=200 if request.method == 'GET' else 202)


def report_page_pdf(request, slug):
    """The stored PDF of a published, FROZEN report, for anyone who may open its page."""
    from reports import services
    report = get_object_or_404(Report.objects.select_related('survey', 'organization'), slug=slug, is_published=True)
    if report.visibility == 'workspace':
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        from survey.permissions import get_org_membership
        if get_org_membership(request.user, report.organization) is None:
            raise Http404
    job = services.ready_pdf(report)
    if job is None or not job.file:
        raise Http404
    from reports import usage
    usage.count(request, report, 'pdf')
    return _pdf_response(job, report, request.user.pk if request.user.is_authenticated else None, 'page')


@login_required
def report_export(request, report_uuid):
    """The report as a ZIP: its settings, blocks and pictures (`reports.files`)."""
    from django.http import HttpResponse
    from reports.files import export_report
    name, data = export_report(_editable_report(request, report_uuid))
    response = HttpResponse(data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{name}"'
    return response


@login_required
def report_import(request):
    """A report file into the active workspace: unpublished, workspace-only, opened in the editor."""
    from django.contrib import messages
    from reports.files import ReportFileRefused, import_report
    from survey.services.context import Actor
    org = getattr(request, 'active_org', None)
    if org is None or not _can_edit(request.user, org):
        raise Http404
    upload = request.FILES.get('file') if request.method == 'POST' else None
    if upload is None:
        return redirect('editor_reports')
    from reports import gate
    from reports.editor_views import paywall
    if not gate.use(org, request.user):
        return paywall(request, org, 'import')
    try:
        report, notes = import_report(Actor.from_request(request), org, upload)
    except ReportFileRefused as refusal:
        messages.error(request, refusal.message)
        return redirect('editor_reports')
    for note in notes[:8]:
        messages.warning(request, note)
    messages.success(request, _('Report imported. It is not published; only this workspace sees it.'))
    return redirect('editor_report', report_uuid=report.uuid)


@login_required
def report_delete(request, report_uuid):
    """What goes with the report first, then the confirm. A survey's home report (the one its
    Public results tab opens) is recreated empty the next time that tab opens."""
    from django.contrib import messages
    from reports import services
    from survey.services.context import Actor
    report = _editable_report(request, report_uuid)
    if request.method == 'POST':
        title = report.title
        services.delete_report(Actor.from_request(request), report)
        messages.success(request, _('“%(name)s” deleted.') % {'name': title})
        return redirect('editor_reports')
    return render(request, 'reports/delete.html', {'org': report.organization, 'report': report,
                                                   'blocks': report.blocks.count()})
