"""Editor views for configuring a survey's public results page.

Lives under /editor/surveys/<uuid>/public-results/. All views require editor
rights on the survey (request.survey is set by the permission decorator).
The page is lazily created on first visit.
"""

import json
import uuid as uuid_module

from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils.text import slugify
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from .models import (
    PublicResultsPage, PublicResultsBlock, Question, Answer,
    PUBLIC_RESULTS_BLOCK_TYPE_CHOICES, BASEMAP_CHOICES,
)
from .permissions import survey_permission_required
from .public_results import freeze_page, unfreeze_page, bump_page_version

# Map a question input type to the block type it renders as on the page.
CHART_INPUT_TYPES = ('choice', 'multichoice', 'rating', 'number', 'range')
MAP_INPUT_TYPES = ('point', 'line', 'polygon')
TEXT_INPUT_TYPES = ('text', 'text_line')


def _block_type_for_question(question):
    if question.input_type in MAP_INPUT_TYPES:
        return 'map'
    if question.input_type in CHART_INPUT_TYPES:
        return 'chart'
    return None  # text/unknown — not publishable


def _is_ajax(request):
    """True for fetch/XHR autosave requests (vs a plain form submit)."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _unique_slug(survey):
    base = slugify(survey.name)[:48] or 'results'
    candidate = base
    if PublicResultsPage.objects.filter(slug=candidate).exists():
        candidate = '{}-{}'.format(base, uuid_module.uuid4().hex[:6])
    return candidate


def _get_or_create_page(survey):
    page = PublicResultsPage.objects.filter(survey=survey).first()
    if page is None:
        page = PublicResultsPage.objects.create(survey=survey, slug=_unique_slug(survey))
    return page


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
            'answer_count': Answer.objects.filter(question=q, survey_session__is_deleted=False).count(),
        })
    return rows


@survey_permission_required('editor')
def public_results_config(request, survey_uuid):
    """Main config page. ?block=<id> shows that block's config in the center."""
    survey = request.survey
    page = _get_or_create_page(survey)

    selected_block = None
    block_id = request.GET.get('block')
    if block_id:
        selected_block = PublicResultsBlock.objects.filter(page=page, id=block_id).first()

    canonical = survey.canonical_survey or survey
    context = {
        'survey': survey,
        'page': page,
        'blocks': page.blocks.all(),
        'question_rows': _survey_questions(survey),
        'selected_block': selected_block,
        'effective_role': request.effective_survey_role,
        'active_tab': 'public_results',
        'can_publish': survey.status != 'draft',
        'public_url': request.build_absolute_uri('/r/{}/'.format(page.slug)),
        'visibility_choices': PublicResultsPage._meta.get_field('visibility').choices,
        'chart_viz_options': ['auto', 'bar', 'pie', 'donut', 'table'],
        'map_viz_options': ['auto', 'heatmap'],
        'basemap_choices': BASEMAP_CHOICES,
    }
    from django.shortcuts import render
    return render(request, 'editor/public_results.html', context)


@survey_permission_required('editor')
@xframe_options_sameorigin
def public_results_preview(request, survey_uuid):
    """Render the public page inside the editor preview pane (iframe).

    Editor-only; renders regardless of publish state so the creator can see
    changes before publishing. Always noindex.
    """
    from django.shortcuts import render
    from .public_results import build_page_context

    survey = request.survey
    page = _get_or_create_page(survey)
    lang = request.GET.get('lang') or 'en'
    context = build_page_context(page, lang=lang)
    context['noindex'] = True
    context['preview'] = True
    return render(request, 'public_results.html', context)


@survey_permission_required('editor')
@require_POST
def public_results_save_settings(request, survey_uuid):
    """Persist page-level settings."""
    survey = request.survey
    page = _get_or_create_page(survey)

    # Draft surveys may configure but not publish their results page.
    wants_publish = request.POST.get('is_published') == 'on'
    if wants_publish and survey.status == 'draft':
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'error': 'publish_survey_first'}, status=400)
        from django.contrib import messages
        messages.error(request, 'Publish the survey before publishing its results.')
        return redirect('editor_survey_public_results', survey_uuid=survey_uuid)

    page.visibility = request.POST.get('visibility', page.visibility)
    page.is_published = wants_publish
    page.intro = {
        'title': {'en': request.POST.get('intro_title', '')},
        'body': {'en': request.POST.get('intro_body', '')},
    }
    page.show_response_count = request.POST.get('show_response_count') == 'on'
    page.show_participate_cta = request.POST.get('show_participate_cta') == 'on'
    page.feature_in_listing = request.POST.get('feature_in_listing') == 'on'
    try:
        page.k_anonymity_threshold = max(1, int(request.POST.get('k_anonymity_threshold', 3)))
    except (ValueError, TypeError):
        page.k_anonymity_threshold = 3

    slug_taken = False
    new_slug = slugify(request.POST.get('slug', '') or page.slug)
    if new_slug and new_slug != page.slug:
        if not PublicResultsPage.objects.filter(slug=new_slug).exclude(id=page.id).exists():
            page.slug = new_slug
        else:
            slug_taken = True
    page.save()
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'slug': page.slug, 'slug_taken': slug_taken})
    return redirect('editor_survey_public_results', survey_uuid=survey_uuid)


@survey_permission_required('editor')
@require_POST
def public_results_block_add(request, survey_uuid):
    """Add a block. block_type text/image are standalone; chart/map need a question."""
    survey = request.survey
    page = _get_or_create_page(survey)
    block_type = request.POST.get('block_type')

    next_order = page.blocks.count()

    if block_type == 'text':
        PublicResultsBlock.objects.create(page=page, block_type=block_type, order=next_order)
    elif block_type == 'image':
        image = request.FILES.get('image')
        if not image:
            return HttpResponse('An image file is required.', status=400)
        PublicResultsBlock.objects.create(page=page, block_type=block_type, image=image, order=next_order)
    elif block_type == 'question':
        question = get_object_or_404(
            Question, id=request.POST.get('question_id'),
            survey_section__survey_header=survey,
        )
        resolved = _block_type_for_question(question)
        if resolved is None:
            # Text questions are never publishable.
            return HttpResponse('Question type is not available for publication.', status=400)
        PublicResultsBlock.objects.create(
            page=page, block_type=resolved, question=question, order=next_order,
        )
    else:
        return HttpResponse('Unknown block type.', status=400)

    bump_page_version(page)
    return redirect('editor_survey_public_results', survey_uuid=survey_uuid)


@survey_permission_required('editor')
@require_POST
def public_results_block_edit(request, survey_uuid, block_id):
    """Update a block's visualization, title, content, geo fields, visibility."""
    survey = request.survey
    page = _get_or_create_page(survey)
    block = get_object_or_404(PublicResultsBlock, id=block_id, page=page)

    block.viz = request.POST.get('viz', block.viz)
    block.is_hidden = request.POST.get('is_hidden') == 'on'
    if 'custom_title' in request.POST:
        block.custom_title = {'en': request.POST.get('custom_title', '')}
    if block.block_type == 'text':
        block.content = {'en': request.POST.get('content', '')}
    if block.block_type == 'image':
        block.content = {'en': request.POST.get('content', '')}
        if request.FILES.get('image'):
            block.image = request.FILES['image']
    if block.block_type == 'map':
        block.geo_label_fields = request.POST.getlist('geo_label_fields')
        valid_basemaps = {slug for slug, _ in BASEMAP_CHOICES}
        posted_basemap = request.POST.get('basemap')
        if posted_basemap in valid_basemaps:
            block.basemap = posted_basemap
    block.save()
    bump_page_version(page)
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'block_id': block.id})
    from django.urls import reverse
    url = reverse('editor_survey_public_results', kwargs={'survey_uuid': survey_uuid})
    return redirect('{}?block={}'.format(url, block.id))


@survey_permission_required('editor')
@require_POST
def public_results_block_delete(request, survey_uuid, block_id):
    survey = request.survey
    page = _get_or_create_page(survey)
    block = get_object_or_404(PublicResultsBlock, id=block_id, page=page)
    block.delete()
    bump_page_version(page)
    if request.headers.get('HX-Request'):
        return HttpResponse('')
    return redirect('editor_survey_public_results', survey_uuid=survey_uuid)


@survey_permission_required('editor')
@require_POST
def public_results_blocks_reorder(request, survey_uuid):
    """Persist block order from a JSON list of block ids."""
    survey = request.survey
    page = _get_or_create_page(survey)
    try:
        order = json.loads(request.body.decode() or '{}').get('order', [])
    except (ValueError, AttributeError):
        return JsonResponse({'ok': False}, status=400)
    id_to_block = {b.id: b for b in page.blocks.all()}
    for index, bid in enumerate(order):
        block = id_to_block.get(int(bid))
        if block:
            block.order = index
            block.save(update_fields=['order'])
    bump_page_version(page)
    return JsonResponse({'ok': True})


@survey_permission_required('editor')
@require_POST
def public_results_freeze(request, survey_uuid):
    survey = request.survey
    page = _get_or_create_page(survey)
    freeze_page(page)
    return redirect('editor_survey_public_results', survey_uuid=survey_uuid)


@survey_permission_required('editor')
@require_POST
def public_results_unfreeze(request, survey_uuid):
    survey = request.survey
    page = _get_or_create_page(survey)
    unfreeze_page(page)
    return redirect('editor_survey_public_results', survey_uuid=survey_uuid)
