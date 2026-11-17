"""The report editor (changes reports-object #703, reports-story #704).

A report is edited on its own at /editor/reports/<uuid>/…; a survey's Public results tab,
/editor/surveys/<uuid>/public-results/…, is the same editor reached through the survey (the
report is created lazily on the first visit). Every view below exists twice — `on_report(view)`
and `on_survey(view)` — and reads `request.report` / `request.survey`; URLs for the page come from
`_urls`, so a template never names a route. Every write goes through `reports.services`.
"""
from functools import wraps

import json

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from data.scope import SessionScope
from reports import services
from reports.models import Report, ReportBlock
from reports.sources import attach_questions
from reports.render import (
    TEXT_INPUT_TYPES,
    block_type_for_question as _block_type_for_question,
    report_for_survey as _report_for_survey,
    scaffold_report,
)
from survey import basemaps as basemap_registry
from survey.comments import open_counts as _thread_counts
from survey.models import Answer, Question, SurveyHeader
from survey.permissions import (
    _check_survey_role, get_effective_survey_role, survey_permission_required,
)
from survey.services.context import Actor


# logical name -> (route through a survey, route of the report itself)
ROUTES = {
    'config': ('editor_survey_public_results', 'editor_report'),
    'preview': ('editor_public_results_preview', 'editor_report_preview'),
    'save': ('editor_public_results_save', 'editor_report_save'),
    'add': ('editor_public_results_block_add', 'editor_report_block_add'),
    'block_edit': ('editor_public_results_block_edit', 'editor_report_block_edit'),
    'block_delete': ('editor_public_results_block_delete', 'editor_report_block_delete'),
    'reorder': ('editor_public_results_blocks_reorder', 'editor_report_blocks_reorder'),
    'set_published': ('editor_public_results_set_published', 'editor_report_set_published'),
    'freeze': ('editor_public_results_freeze', 'editor_report_freeze'),
    'unfreeze': ('editor_public_results_unfreeze', 'editor_report_unfreeze'),
    'checks': ('editor_public_results_checks', 'editor_report_checks'),
}


def _url(request, name, *args):
    """The URL of a logical route, through the survey or the report as this request came."""
    by_survey, by_report = ROUTES[name]
    if getattr(request, 'report_route', 'survey') == 'report':
        return reverse(by_report, args=[request.report.uuid, *args])
    return reverse(by_survey, args=[request.survey.uuid, *args])


def _urls(request):
    """Every URL the editor page needs. `block_edit` / `block_delete` end in `/0/…`: the page
    swaps the 0 for a block id."""
    urls = {name: _url(request, name) for name in ROUTES if name not in ('block_edit', 'block_delete')}
    urls['block_edit'] = _url(request, 'block_edit', 0)
    urls['block_delete'] = _url(request, 'block_delete', 0)
    return urls


def may_edit_report(request, report):
    """Editors of the report's workspace; a report with a home survey also needs the editor role
    on that survey (the rule its tab always had)."""
    from survey.permissions import get_org_membership
    if not request.user.is_authenticated:
        return False
    active_org = getattr(request, 'active_org', None)
    if active_org is None or report.organization_id != active_org.id:
        return False
    membership = get_org_membership(request.user, report.organization)
    if membership is None or membership.role not in ('owner', 'admin', 'editor'):
        return False
    if report.survey_id is None:
        return True
    return _check_survey_role(get_effective_survey_role(request.user, report.survey), 'editor')


def paywall(request, organization, surface='editor'):
    """The answer to a write the workspace's plan does not allow (change reports-pro, #709)."""
    from billing.gates import feature_required
    from reports.gate import FEATURE
    from survey import product_events as pe
    pe.emit(pe.REPORT_PAYWALL_SHOWN, request.user.pk, {'surface': surface})
    if _is_ajax(request):
        return JsonResponse({'ok': False, 'error': 'pro_required'}, status=403)
    return feature_required(request, organization, FEATURE)


def _gated(request, organization):
    """None when this request may go on: a read always may, a write when the workspace has the
    Reports feature (or starts its trial with it). Otherwise the upgrade page."""
    from billing import trial
    from reports import gate
    if request.method != 'POST':
        return None
    if gate.use(organization, request.user):
        trial.flash_started(request, organization)
        return None
    return paywall(request, organization)


def on_survey(view):
    """The view reached through a survey's Public results tab."""
    @survey_permission_required('editor')
    @wraps(view)
    def wrapper(request, survey_uuid, *args, **kwargs):
        request.report_route = 'survey'
        request.report = None
        refusal = _gated(request, request.survey.organization)
        if refusal is not None:
            return refusal
        return view(request, *args, **kwargs)
    return wrapper


def on_report(view):
    """The view of a report addressed by its own uuid; 404 for anyone who may not edit it."""
    @wraps(view)
    def wrapper(request, report_uuid, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        report = get_object_or_404(Report.objects.select_related('survey', 'organization'), uuid=report_uuid)
        if not may_edit_report(request, report):
            raise Http404
        request.report_route = 'report'
        request.report = report
        request.survey = report.survey if report.survey_id else None
        request.effective_survey_role = (get_effective_survey_role(request.user, report.survey)
                                         if report.survey_id else 'editor')
        refusal = _gated(request, report.organization)
        if refusal is not None:
            return refusal
        return view(request, *args, **kwargs)
    return wrapper


def _page(request):
    """The report this request edits."""
    if getattr(request, 'report', None) is None:
        request.report = _report_for_survey(request.survey)
    return request.report


def _is_ajax(request):
    """True for fetch/XHR autosave requests (vs a plain form submit)."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _may_edit(request, survey):
    """True if the requester may see the editor preview of this survey.

    Mirrors what @survey_permission_required('editor') enforces: authenticated,
    survey in the active org, effective role at least 'editor'.
    """
    if not request.user.is_authenticated:
        return False
    active_org = getattr(request, 'active_org', None)
    if active_org is None or survey.organization_id != active_org.id:
        return False
    return _check_survey_role(get_effective_survey_role(request.user, survey), 'editor')


def _preview_denied(request, survey):
    """Response for a preview request from someone without editor rights.

    Forwards to the public page when the survey's report is published — this is the
    whole point of the view being decorator-free. `visibility` is not consulted here:
    an `unlisted` report is one the creator handed out by link, and `/r/<slug>/`
    serves it already (and guards a workspace-only one itself). Reads only; never
    creates a report row on a path a stranger can trigger.

    With no published report there is nowhere to send them, so the original
    denial stands.
    """
    if getattr(settings, 'PUBLIC_RESULTS_PREVIEW_FALLBACK', True):
        report = Report.objects.filter(
            survey=survey, is_published=True).only('slug').order_by('id').first()
        if report is not None:
            return redirect('public_results', slug=report.slug)

    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    raise Http404


def _survey_questions(survey):
    """Questions in the survey, flagged publishable (text types are not)."""
    questions = (
        Question.objects
        .filter(survey_section__survey_header=survey, parent_question_id__isnull=True)
        .select_related('survey_section')
        .order_by('survey_section__id', 'order_number')
    )
    rows = []
    for q in questions:
        rows.append({
            'question': q,
            'block_type': _block_type_for_question(q),
            'publishable': q.input_type not in TEXT_INPUT_TYPES,
            'input_type_display': q.get_input_type_display(),
            'answer_count': Answer.objects.filter(question=q).filter(
                SessionScope((), include_moderated=True).related_q('survey_session')).count(),
        })
    return rows


def _refused(request, refusal, status=400):
    """A service refusal as this screen always answered it."""
    if _is_ajax(request):
        return JsonResponse({'ok': False, 'error': refusal.code}, status=status)
    from django.contrib import messages
    messages.error(request, refusal.message)
    return redirect(_url(request, 'config'))


def _usage(report):
    from reports.usage import summary
    return summary(report)


def _may_write(organization):
    from reports import gate
    return gate.may_write(organization)


def _compare_surveys(request, survey):
    """The other surveys of the workspace a Compare block may name: the rounds before or after."""
    if survey is None:
        return []
    from data.datasets import visible_survey_ids
    from survey.models import SurveyHeader
    from survey.versioning import canonical_of
    home = canonical_of(survey)
    ids = visible_survey_ids(home.organization, request.user)
    return list(SurveyHeader.objects.filter(pk__in=ids, deleted_at__isnull=True).exclude(pk=home.pk)
                .order_by('-id')[:50])


def _crosstab_questions(survey):
    """The questions a cross-tab of the report's home survey may name."""
    if survey is None:
        return []
    from data.analysis import CROSSTAB_TYPES
    from data.questions import top_level_questions
    from survey.versioning import canonical_of
    return top_level_questions(canonical_of(survey), CROSSTAB_TYPES)


def _elsewhere(request, page, block):
    """What the editor needs to offer a report or a block outside the page (change reports-embed):
    the embed snippets, the allow-list as text, and a data block's CSV / PNG links."""
    from reports import embed
    from reports.pictures import PICTURE_BLOCK_TYPES
    from reports.tables import DATA_BLOCK_TYPES
    from survey.embedding import public_base_url
    base = public_base_url(request)
    out = {
        'embed_snippet': embed.snippet(base, page),
        'embed_hosts_text': '\n'.join(page.embed_allowed_hosts or []),
        'embeddable': embed.embeddable(page),
    }
    if block is not None and block.block_type in DATA_BLOCK_TYPES + ('quotes', 'image', 'text'):
        out['block_snippet'] = embed.snippet(base, page, block.id)
    if block is not None and block.block_type in DATA_BLOCK_TYPES:
        out['block_csv_url'] = reverse('editor_report_block_file', args=[page.uuid, block.id, 'csv'])
    if block is not None and block.block_type in PICTURE_BLOCK_TYPES:
        out['block_png_url'] = reverse('editor_report_block_file', args=[page.uuid, block.id, 'png'])
    return out


def _token_help():
    from reports.tokens import HELP
    return HELP


class _NoThreads(dict):
    """Comment counts of a report without a home survey: threads hang on a survey."""
    total = 0
    new_total = 0


def _config(request):
    """The editor page. ?block=<id> shows that block's settings in the centre."""
    survey = request.survey
    if request.report is not None:
        page = request.report
    elif survey.status != 'draft':
        # Covers surveys published outside the editor transition view (e.g.
        # Django admin): however the survey became published, the first look
        # at this tab shows the drafted blocks. No-op once scaffolded_at set.
        page = request.report = scaffold_report(survey)
    else:
        page = request.report = _report_for_survey(survey)

    selected_block = None
    block_id = request.GET.get('block')
    if block_id:
        selected_block = (ReportBlock.objects.filter(report=page, id=block_id)
                          .select_related('dataset__survey').first())

    # Geo popups expose the point's OWN attributes — i.e. the geo question's
    # (non-text) sub-questions — not unrelated top-level form questions.
    geo_subquestions = []
    if selected_block and selected_block.block_type == 'map' and selected_block.question_id:
        geo_subquestions = list(
            Question.objects
            .filter(parent_question_id=selected_block.question_id)
            .exclude(input_type__in=TEXT_INPUT_TYPES)
            .order_by('order_number')
        )

    from reports import story
    urls = _urls(request)
    blocks = attach_questions(page.blocks.select_related('dataset__survey'))
    for b in blocks:
        b.edit_href = '{}?block={}'.format(urls['config'], b.id)
        b.delete_url = _url(request, 'block_delete', b.id)
    context = {
        'survey': survey,
        'page': page,
        'report': page,
        'u': urls,
        'selected_edit_url': _url(request, 'block_edit', selected_block.id) if selected_block else '',
        'selected_lines': (story.lines_from_items(selected_block.block_type, selected_block.config)
                           if selected_block and selected_block.block_type in ('numbers', 'quotes') else ''),
        'export_url': reverse('editor_report_export', args=[page.uuid]),
        'pdf_url': reverse('editor_report_pdf', args=[page.uuid]),
        'crosstab_questions': _crosstab_questions(survey),
        'compare_surveys': _compare_surveys(request, survey),
        'reports_locked': not _may_write(page.organization),
        'usage': _usage(page),
        'tags_text': ', '.join(t.name for t in page.tags.all()),
        **_elsewhere(request, page, selected_block),
        'token_help': _token_help(),
        'reports_url': reverse('editor_reports'),
        'blocks': blocks,
        'thread_counts': _thread_counts(survey, request.user) if survey is not None else _NoThreads(),
        'question_rows': _survey_questions(survey) if survey is not None else [],
        'geo_subquestions': geo_subquestions,
        'selected_block': selected_block,
        'effective_role': request.effective_survey_role,
        'active_tab': 'public_results',
        'can_publish': survey is None or survey.status != 'draft',
        'public_url': request.build_absolute_uri('/r/{}/'.format(page.slug)),
        'visibility_choices': Report._meta.get_field('visibility').choices,
        'chart_viz_options': [
            ('auto', 'Auto (bar chart)'), ('bar', 'Bar chart'), ('pie', 'Pie'),
            ('donut', 'Donut'), ('table', 'Table'),
        ],
        # A spray cloud block has one rendering (density grid) and no popups.
        'selected_is_spray': bool(selected_block and selected_block.question_id
                                  and selected_block.question.input_type == 'spraycan'),
        'basemap_choices': basemap_registry.choices_for(page.organization),
    }
    from django.shortcuts import render
    return render(request, 'editor/public_results.html', context)


@xframe_options_sameorigin
def public_results_preview(request, survey_uuid):
    """Render the report's page inside the editor preview pane (iframe).

    Editor-only; renders regardless of publish state so the creator can see
    changes before publishing. Always noindex.

    This view deliberately does NOT use @survey_permission_required, because it
    is the one editor URL that escapes into the wild: creators share results by
    copying it out of the address bar instead of using `/r/<slug>/`. A visitor
    who follows such a link and has no editor rights is forwarded to the public
    page when one is published, rather than being bounced to login (anonymous)
    or 404 (signed in elsewhere) — see `_preview_denied`. The guards the
    decorator used to provide are reproduced here and must stay: trashed
    surveys are excluded, an unknown UUID is a 404, and the survey must belong
    to the requester's active org for the preview itself to render.
    """
    from django.shortcuts import render
    from reports.render import build_context

    survey = SurveyHeader.objects.filter(
        uuid=survey_uuid, deleted_at__isnull=True).first()
    if survey is None:
        raise Http404

    if not _may_edit(request, survey):
        return _preview_denied(request, survey)

    request.survey = survey
    page = _report_for_survey(survey)
    lang = request.GET.get('lang') or 'en'
    context = build_context(page, lang=lang)
    context['noindex'] = True
    context['preview'] = True
    return render(request, 'public_results.html', context)


@xframe_options_sameorigin
def report_preview(request, report_uuid):
    """A report's page inside its editor's preview pane, whatever its publication state."""
    from django.shortcuts import render
    from reports.render import build_context
    report = get_object_or_404(Report.objects.select_related('survey', 'organization'), uuid=report_uuid)
    if not may_edit_report(request, report):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        raise Http404
    context = build_context(report, lang=request.GET.get('lang') or 'en')
    context['noindex'] = True
    context['preview'] = True
    return render(request, 'public_results.html', context)


@require_POST
def _save_settings(request):
    """Persist report-level settings."""
    page = _page(request)
    post = request.POST
    # Publish state is owned by the explicit Publish/Unpublish action
    # (public_results_set_published). The settings form only touches it when the
    # field is present, so autosaving other fields never flips it off.
    is_published = (post.get('is_published') == 'on') if 'is_published' in post else None
    try:
        slug_taken = services.update_settings(
            Actor.from_request(request), page,
            is_published=is_published,
            visibility=post.get('visibility', page.visibility),
            intro_title=post.get('intro_title', ''), intro_body=post.get('intro_body', ''),
            intro_eyebrow=post.get('intro_eyebrow') if 'intro_eyebrow' in post else None,
            embed_hosts=post.get('embed_hosts') if 'embed_hosts' in post else None,
            tags=post.get('tags') if 'tags' in post else None,
            show_response_count=post.get('show_response_count') == 'on',
            show_participate_cta=post.get('show_participate_cta') == 'on',
            show_on_thanks=post.get('show_on_thanks') == 'on',
            feature_in_listing=post.get('feature_in_listing') == 'on',
            k=post.get('k_anonymity_threshold', 3), slug=post.get('slug', ''))
    except services.ReportRefused as refusal:
        return _refused(request, refusal)
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'slug': page.slug, 'slug_taken': slug_taken})
    return redirect(_url(request, 'config'))


@require_POST
def _block_add(request):
    """Add a block: a story block (heading, text, image, key numbers, quotes) stands alone; a
    chart or a map needs a question of the report's home survey."""
    survey = request.survey
    page = _page(request)
    block_type = request.POST.get('block_type')
    actor = Actor.from_request(request)
    try:
        if block_type in ('heading', 'text', 'numbers', 'quotes'):
            block = services.add_story_block(actor, page, block_type)
        elif block_type == 'image':
            block = services.add_image_block(actor, page, request.FILES.get('image'))
        elif block_type in ('crosstab', 'engagement') and survey is not None:
            block = services.add_view_block(actor, page, block_type, survey,
                                            rows=request.POST.get('rows', ''), columns=request.POST.get('columns', ''))
        elif block_type == 'compare' and survey is not None:
            from data.questions import question_of
            from survey.models import SurveyHeader
            from survey.versioning import canonical_of
            other = SurveyHeader.objects.filter(uuid=request.POST.get('other') or None,
                                                organization_id=page.organization_id,
                                                deleted_at__isnull=True).first() if request.POST.get('other') else None
            question = question_of(canonical_of(survey), request.POST.get('compare_question', ''))
            if question is None:
                return HttpResponse('Unknown question.', status=400)
            block = services.add_compare_block(actor, page, question, other)
        elif block_type == 'question' and survey is not None:
            question = get_object_or_404(
                Question.objects.select_related('survey_section__survey_header'),
                id=request.POST.get('question_id'), survey_section__survey_header=survey)
            block = services.add_question_block(actor, page, question)
        else:
            return HttpResponse('Unknown block type.', status=400)
    except services.ReportRefused as refusal:
        return HttpResponse(refusal.message, status=400)

    # Land the editor in the new block's config — the live preview scrolls to it.
    return redirect('{}?block={}'.format(_url(request, 'config'), block.id))


@require_POST
def _block_edit(request, block_id):
    """Update a block's visualization, title, content, items, width, geo fields, visibility."""
    from reports import story
    page = _page(request)
    block = get_object_or_404(ReportBlock, id=block_id, report=page)
    post = request.POST
    is_text_like = (block.block_type in ('text', 'image', 'heading', 'numbers', 'quotes')
                    or (block.block_type == 'map' and 'content' in post))
    items = None
    if block.block_type in ('numbers', 'quotes') and 'items' in post:
        items = story.items_from_lines(block.block_type, post.get('items', ''))['items']
    services.update_block(
        Actor.from_request(request), block,
        viz=post.get('viz', block.viz),
        is_hidden=post.get('is_hidden') == 'on',
        custom_title=post.get('custom_title', '') if 'custom_title' in post else None,
        content=post.get('content', '') if is_text_like else None,
        image=request.FILES.get('image'),
        geo_label_fields=post.getlist('geo_label_fields') if block.block_type == 'map' else None,
        width=post.get('width') if 'width' in post else None,
        items=items,
        # The switch posts a hidden marker beside the checkbox, so an autosave that lacks the
        # box means "off" and a form without the field leaves the choice alone.
        show_marks=(post.get('show_marks') == 'on') if 'show_marks_present' in post else None,
        basemap=post.get('basemap'),
        valid_basemaps={slug for slug, _label in basemap_registry.choices_for(page.organization)})
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'block_id': block.id})
    return redirect('{}?block={}'.format(_url(request, 'config'), block.id))


@require_POST
def _block_delete(request, block_id):
    page = _page(request)
    block = get_object_or_404(ReportBlock, id=block_id, report=page)
    services.delete_block(Actor.from_request(request), block)
    if request.headers.get('HX-Request'):
        return HttpResponse('')
    return redirect(_url(request, 'config'))


@require_POST
def _blocks_reorder(request):
    """Persist block order from a JSON list of block ids."""
    page = _page(request)
    try:
        order = json.loads(request.body.decode() or '{}').get('order', [])
    except (ValueError, AttributeError):
        return JsonResponse({'ok': False}, status=400)
    services.reorder_blocks(Actor.from_request(request), page, order)
    return JsonResponse({'ok': True})


@require_POST
def _set_published(request):
    """Explicit publish / unpublish action for the report.

    `publish=1` makes the report live at /r/<slug>/; `publish=0` takes it down.
    A draft survey cannot publish its report.
    """
    page = _page(request)
    publish = request.POST.get('publish') in ('1', 'true', 'on')
    try:
        services.set_published(Actor.from_request(request), page, publish,
                               ack=request.POST.get('ack') in ('1', 'true', 'on'),
                               visibility=request.POST.get('visibility'), mode=request.POST.get('mode'))
    except services.ReportRefused as refusal:
        return _refused(request, refusal)
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'is_published': page.is_published})
    return redirect(_url(request, 'config'))


@require_POST
def _freeze(request):
    services.freeze(Actor.from_request(request), _page(request))
    return redirect(_url(request, 'config'))


@require_POST
def _unfreeze(request):
    services.unfreeze(Actor.from_request(request), _page(request))
    return redirect(_url(request, 'config'))


def _checks(request):
    """The "Before you publish" list of the publish dialog (change reports-review): what names or
    places people first, then what looks unfinished, each with its one-click way to fix it."""
    from django.shortcuts import render
    from reports.checks import run
    page = _page(request)
    checks = run(page)
    config = _url(request, 'config')
    for item in checks.privacy + checks.other:
        item.open_url = '{}?block={}'.format(config, item.block_id) if item.block_id else config
        item.delete_url = _url(request, 'block_delete', item.block_id) if item.fix == 'delete' else ''
    return render(request, 'editor/partials/pr_checks.html', {
        'page': page, 'checks': checks, 'u': _urls(request),
        'can_publish': request.survey is None or request.survey.status != 'draft',
        'visibility_choices': Report._meta.get_field('visibility').choices,
        'public_url': request.build_absolute_uri('/r/{}/'.format(page.slug)),
    })


# Each view twice: through the survey's tab, and by the report's own address.
public_results_checks, report_checks = on_survey(_checks), on_report(_checks)
public_results_config, report_config = on_survey(_config), on_report(_config)
public_results_save_settings, report_save_settings = on_survey(_save_settings), on_report(_save_settings)
public_results_block_add, report_block_add = on_survey(_block_add), on_report(_block_add)
public_results_block_edit, report_block_edit = on_survey(_block_edit), on_report(_block_edit)
public_results_block_delete, report_block_delete = on_survey(_block_delete), on_report(_block_delete)
public_results_blocks_reorder, report_blocks_reorder = on_survey(_blocks_reorder), on_report(_blocks_reorder)
public_results_set_published, report_set_published = on_survey(_set_published), on_report(_set_published)
public_results_freeze, report_freeze = on_survey(_freeze), on_report(_freeze)
public_results_unfreeze, report_unfreeze = on_survey(_unfreeze), on_report(_unfreeze)


@require_POST
def report_create(request):
    """A blank report of the active workspace, opened in its editor ("New report")."""
    from survey.permissions import get_org_membership
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    org = getattr(request, 'active_org', None)
    membership = get_org_membership(request.user, org) if org is not None else None
    if membership is None or membership.role not in ('owner', 'admin', 'editor'):
        raise Http404
    from reports import gate
    if not gate.use(org, request.user):
        return paywall(request, org, 'start')
    title = (request.POST.get('title') or '').strip()[:200] or 'Untitled report'
    report = services.create_report(Actor.from_request(request), org, title=title, visibility='workspace')
    return redirect('editor_report', report_uuid=report.uuid)
