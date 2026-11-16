"""Editor views for configuring a survey's report (its public results page).

Lives under /editor/surveys/<uuid>/public-results/. All views require editor
rights on the survey (request.survey is set by the permission decorator).
The report is lazily created on first visit. Every write goes through
`reports.services`; the story editor (#704) replaces these screens.
"""

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


def _refused(request, survey_uuid, refusal, status=400):
    """A service refusal as this screen always answered it."""
    if _is_ajax(request):
        return JsonResponse({'ok': False, 'error': refusal.code}, status=status)
    from django.contrib import messages
    messages.error(request, refusal.message)
    return redirect('editor_survey_public_results', survey_uuid=survey_uuid)


@survey_permission_required('editor')
def public_results_config(request, survey_uuid):
    """Main config page. ?block=<id> shows that block's config in the center."""
    survey = request.survey
    if survey.status != 'draft':
        # Covers surveys published outside the editor transition view (e.g.
        # Django admin): however the survey became published, the first look
        # at this tab shows the drafted blocks. No-op once scaffolded_at set.
        page = scaffold_report(survey)
    else:
        page = _report_for_survey(survey)

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

    context = {
        'survey': survey,
        'page': page,
        'blocks': attach_questions(page.blocks.select_related('dataset__survey')),
        'thread_counts': _thread_counts(survey, request.user),
        'question_rows': _survey_questions(survey),
        'geo_subquestions': geo_subquestions,
        'selected_block': selected_block,
        'effective_role': request.effective_survey_role,
        'active_tab': 'public_results',
        'can_publish': survey.status != 'draft',
        'public_url': request.build_absolute_uri('/r/{}/'.format(page.slug)),
        'visibility_choices': Report._meta.get_field('visibility').choices,
        'chart_viz_options': [
            ('auto', 'Auto (bar chart)'), ('bar', 'Bar chart'), ('pie', 'Pie'),
            ('donut', 'Donut'), ('table', 'Table'),
        ],
        # A spray cloud block has one rendering (density grid) and no popups.
        'selected_is_spray': bool(selected_block and selected_block.question_id
                                  and selected_block.question.input_type == 'spraycan'),
        'basemap_choices': basemap_registry.choices_for(survey.organization),
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


@survey_permission_required('editor')
@require_POST
def public_results_save_settings(request, survey_uuid):
    """Persist report-level settings."""
    page = _report_for_survey(request.survey)
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
            show_response_count=post.get('show_response_count') == 'on',
            show_participate_cta=post.get('show_participate_cta') == 'on',
            show_on_thanks=post.get('show_on_thanks') == 'on',
            feature_in_listing=post.get('feature_in_listing') == 'on',
            k=post.get('k_anonymity_threshold', 3), slug=post.get('slug', ''))
    except services.ReportRefused as refusal:
        return _refused(request, survey_uuid, refusal)
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'slug': page.slug, 'slug_taken': slug_taken})
    return redirect('editor_survey_public_results', survey_uuid=survey_uuid)


@survey_permission_required('editor')
@require_POST
def public_results_block_add(request, survey_uuid):
    """Add a block. block_type text/image are standalone; chart/map need a question."""
    survey = request.survey
    page = _report_for_survey(survey)
    block_type = request.POST.get('block_type')
    actor = Actor.from_request(request)
    try:
        if block_type == 'text':
            block = services.add_text_block(actor, page)
        elif block_type == 'image':
            block = services.add_image_block(actor, page, request.FILES.get('image'))
        elif block_type == 'question':
            question = get_object_or_404(
                Question.objects.select_related('survey_section__survey_header'),
                id=request.POST.get('question_id'), survey_section__survey_header=survey)
            block = services.add_question_block(actor, page, question)
        else:
            return HttpResponse('Unknown block type.', status=400)
    except services.ReportRefused as refusal:
        return HttpResponse(refusal.message, status=400)

    # Land the editor in the new block's config — the live preview scrolls to it.
    url = reverse('editor_survey_public_results', kwargs={'survey_uuid': survey_uuid})
    return redirect('{}?block={}'.format(url, block.id))


@survey_permission_required('editor')
@require_POST
def public_results_block_edit(request, survey_uuid, block_id):
    """Update a block's visualization, title, content, geo fields, visibility."""
    page = _report_for_survey(request.survey)
    block = get_object_or_404(ReportBlock, id=block_id, report=page)
    post = request.POST
    is_text_like = block.block_type in ('text', 'image')
    services.update_block(
        Actor.from_request(request), block,
        viz=post.get('viz', block.viz),
        is_hidden=post.get('is_hidden') == 'on',
        custom_title=post.get('custom_title', '') if 'custom_title' in post else None,
        content=post.get('content', '') if is_text_like else None,
        image=request.FILES.get('image'),
        geo_label_fields=post.getlist('geo_label_fields') if block.block_type == 'map' else None,
        basemap=post.get('basemap'),
        valid_basemaps={slug for slug, _label in basemap_registry.choices_for(page.organization)})
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'block_id': block.id})
    url = reverse('editor_survey_public_results', kwargs={'survey_uuid': survey_uuid})
    return redirect('{}?block={}'.format(url, block.id))


@survey_permission_required('editor')
@require_POST
def public_results_block_delete(request, survey_uuid, block_id):
    page = _report_for_survey(request.survey)
    block = get_object_or_404(ReportBlock, id=block_id, report=page)
    services.delete_block(Actor.from_request(request), block)
    if request.headers.get('HX-Request'):
        return HttpResponse('')
    return redirect('editor_survey_public_results', survey_uuid=survey_uuid)


@survey_permission_required('editor')
@require_POST
def public_results_blocks_reorder(request, survey_uuid):
    """Persist block order from a JSON list of block ids."""
    page = _report_for_survey(request.survey)
    try:
        order = json.loads(request.body.decode() or '{}').get('order', [])
    except (ValueError, AttributeError):
        return JsonResponse({'ok': False}, status=400)
    services.reorder_blocks(Actor.from_request(request), page, order)
    return JsonResponse({'ok': True})


@survey_permission_required('editor')
@require_POST
def public_results_set_published(request, survey_uuid):
    """Explicit publish / unpublish action for the survey's report.

    `publish=1` makes the report live at /r/<slug>/; `publish=0` takes it down.
    A draft survey cannot publish its report.
    """
    page = _report_for_survey(request.survey)
    publish = request.POST.get('publish') in ('1', 'true', 'on')
    try:
        services.set_published(Actor.from_request(request), page, publish)
    except services.ReportRefused as refusal:
        return _refused(request, survey_uuid, refusal)
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'is_published': page.is_published})
    return redirect('editor_survey_public_results', survey_uuid=survey_uuid)


@survey_permission_required('editor')
@require_POST
def public_results_freeze(request, survey_uuid):
    services.freeze(Actor.from_request(request), _report_for_survey(request.survey))
    return redirect('editor_survey_public_results', survey_uuid=survey_uuid)


@survey_permission_required('editor')
@require_POST
def public_results_unfreeze(request, survey_uuid):
    services.unfreeze(Actor.from_request(request), _report_for_survey(request.survey))
    return redirect('editor_survey_public_results', survey_uuid=survey_uuid)
