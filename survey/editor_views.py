import json
import logging
import os
import re

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.gis.geos import Point
from django.db import transaction
from django.db import models
from django.db.models import Q, Max, Count
from django.http import HttpResponse, Http404, JsonResponse
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.utils import timezone, translation
from django.views.decorators.http import require_POST

from .models import (
    SurveyHeader, SurveySession, SurveySection, SurveySectionTranslation,
    Question, QuestionTranslation, SurveyCollaborator, Answer,
    Membership, SURVEY_ROLE_CHOICES, BASEMAP_CHOICES,
    INPUT_TYPE_CHOICES, DISPLAY_STYLE_CHOICES, SurveyMapLayer,
)
from .layers import (
    validate_layer_upload, LayerValidationError,
    MAX_LAYER_BYTES, MAX_LAYERS_PER_SURVEY,
)
from . import product_events as pe
from .question_types import CHOICE_TYPES
from .cloning import clone_question, clone_section
from .html_sanitize import coerce_creator_html
from .translation_gaps import survey_translation_gaps
from .editor_forms import (
    SurveyHeaderForm, SurveyCreateForm, SurveyBriefForm, SurveySectionForm, QuestionForm,
    SUBQUESTION_DISALLOWED_INPUT_TYPES,
)
from .ai import client as ai_client
from .ai.generation import SurveyBrief, start_generation
from .ai.materialize import header_overrides_from_form
from .ai.tasks import generate_survey_draft_task
from .models import AIGenerationEvent
from .forms import SurveySectionAnswerForm
from .permissions import (
    org_permission_required, survey_permission_required,
    get_effective_survey_role,
)
from .versioning import (
    clone_survey_for_draft, check_draft_compatibility, publish_draft,
    IncompatibleDraftError, family_ids,
)
from .audit import audit
from .public_results import scaffold_page

logger = logging.getLogger(__name__)


def _guard_choice_codes(question, new_choices):
    """Prevent silently rebinding a historically answered choice code.

    Cross-version analytics merges choice answers by code, so a code that
    family answers used but that is absent from the question's current set
    must never be handed to a NEW choice — the old and new meanings would
    silently merge. Offending new entries get a fresh code above everything
    ever used in the lineage. Existing codes stay untouched (renaming an
    existing choice is a normal compatible edit).
    """
    if not isinstance(new_choices, list) or not question.code:
        return new_choices

    old_codes = {c.get('code') for c in (question.choices or []) if isinstance(c, dict)}

    answered = set()
    lineage_selected = (
        Answer.objects
        .filter(
            question__code=question.code,
            question__input_type=question.input_type,
            question__survey_section__survey_header_id__in=family_ids(
                question.survey_section.survey_header
            ),
        )
        .exclude(selected_choices__isnull=True)
        .values_list('selected_choices', flat=True)
    )
    for selected in lineage_selected:
        answered.update(selected or [])
    if not answered:
        return new_choices

    all_known = answered | old_codes | {
        c.get('code') for c in new_choices if isinstance(c, dict)
    }
    numeric = [c for c in all_known if isinstance(c, int)]
    next_code = (max(numeric) + 1) if numeric else 1

    for choice in new_choices:
        if not isinstance(choice, dict):
            continue
        code = choice.get('code')
        if code in answered and code not in old_codes:
            choice['code'] = next_code
            next_code += 1
    return new_choices


def _check_structural_edit_allowed(survey):
    """Return HttpResponse(403) if survey is read-only, else None."""
    if survey.status in ('published', 'closed'):
        return HttpResponse('Structural edits are not allowed on published or closed surveys', status=403)
    return None


# Sent by the editor once the author has seen how many answers a delete costs.
DELETE_ACKNOWLEDGEMENT = 'confirm_delete_answers'


def _survey_is_unversioned(survey):
    """True when this survey has no archived versions to fall back on.

    Publishing moves the previous structure and its sessions onto an archived
    header rather than deleting them, so a survey that has been published keeps
    its earlier answers. One that never has does not — there is nowhere for them
    to go.
    """
    if survey.is_draft_copy:
        return False
    return survey.version_number == 1 and not SurveyHeader.objects.filter(
        canonical_survey=survey, is_canonical=False,
    ).exists()


def _refuse_if_answers_at_risk(request, survey, answer_count):
    """Return a 409 unless the author has acknowledged losing `answer_count` answers.

    The count is computed in the same request that would perform the delete.
    Rendering it into the page earlier would let it go stale on a survey that is
    still collecting, and a warning that is sometimes wrong about the number
    teaches the author to disbelieve it.
    """
    if not answer_count:
        return None
    if request.POST.get(DELETE_ACKNOWLEDGEMENT) == 'true':
        return None
    return JsonResponse(
        {
            'answers_at_risk': answer_count,
            'explain_versioning': _survey_is_unversioned(survey),
        },
        status=409,
    )


def _can_read_survey(user, survey):
    """Return True if user has at least viewer role on the survey."""
    return get_effective_survey_role(user, survey) is not None


def _is_ajax(request):
    """True for fetch/XHR autosave requests (vs a plain form submit)."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _get_sections_ordered(survey):
    """Return sections in linked-list order, each carrying .question_count."""
    sections = list(SurveySection.objects.filter(survey_header=survey))
    if not sections:
        return []

    counts = {
        row['survey_section']: row['n']
        for row in Question.objects.filter(survey_section__in=sections)
        .values('survey_section').annotate(n=Count('id'))
    }
    for s in sections:
        s.question_count = counts.get(s.id, 0)

    by_id = {s.id: s for s in sections}
    head = None
    for s in sections:
        if s.is_head:
            head = s
            break
    if head is None:
        return sections  # fallback: unordered

    ordered = []
    current = head
    visited = set()
    while current and current.id not in visited:
        ordered.append(current)
        visited.add(current.id)
        current = by_id.get(current.next_section_id)
    # Append any orphaned sections
    for s in sections:
        if s.id not in visited:
            ordered.append(s)
    return ordered


# ─── Survey creation ─────────────────────────────────────────────────────────

# Friendly, non-alarming copy per failure mode. The creator does not care
# which layer failed — they care whether to retry or to build it by hand.
GENERATION_ERROR_COPY = {
    'not_configured': "AI drafting isn't available right now — create an empty survey instead.",
    'provider_error': "Couldn't reach the AI service. Try again, or create an empty survey.",
    'invalid_draft': "The draft came back malformed. Try rephrasing your brief, or create an empty survey.",
    'error': "Something went wrong generating the draft. Try again, or create an empty survey.",
}


@org_permission_required('editor')
def editor_survey_create(request):
    brief_form = SurveyBriefForm()
    if request.method == 'POST':
        form = SurveyCreateForm(request.POST)
        if request.POST.get('action') == 'generate':
            return _start_survey_generation(request, form)
        # Re-render after an invalid manual POST keeps the typed brief visible
        # (initial=, not data=: binding would demand a goal the creator is
        # explicitly declining to use). The collapsed "Add details" disclosure
        # reads these values to decide whether to render open.
        brief_form = SurveyBriefForm(initial={
            'goal': request.POST.get('goal', ''),
            'audience': request.POST.get('audience', ''),
            'map_target': request.POST.get('map_target', ''),
            'use_case': request.POST.get('use_case') or 'urban_planning',
        })
        if form.is_valid():
            survey = form.save(commit=False)
            survey.organization = request.active_org
            survey.created_by = request.user
            # Map position from hidden fields
            map_lat = request.POST.get('map_lat')
            map_lng = request.POST.get('map_lng')
            map_zoom = request.POST.get('map_zoom')
            if map_lat and map_lng:
                survey.start_map_postion = Point(float(map_lng), float(map_lat))
            if map_zoom:
                survey.start_map_zoom = int(map_zoom)
            survey.use_geolocation = request.POST.get('use_geolocation') == '1'
            # Default base map (all basemaps stay enabled via the model default)
            valid_basemaps = {slug for slug, _ in BASEMAP_CHOICES}
            chosen_basemap = request.POST.get('default_basemap')
            if chosen_basemap in valid_basemaps:
                survey.default_basemap = chosen_basemap
            survey.save()
            # `creation_method` is what makes the AI generator measurable: every
            # historical survey is `manual` by definition, so this is the baseline
            # its variant gets compared against.
            pe.emit(pe.SURVEY_CREATED, request.user.pk, {
                'survey_id': str(survey.id),
                'creation_method': pe.CREATION_MANUAL,
            })
            # Create SurveyCollaborator owner entry
            SurveyCollaborator.objects.create(
                user=request.user,
                survey=survey,
                role='owner',
            )
            # Create default first section
            SurveySection.objects.create(
                survey_header=survey,
                name='section_1',
                title='Section 1',
                code='S1',
                is_head=True,
            )
            return redirect('editor_survey_detail', survey_uuid=survey.uuid)
    else:
        form = SurveyCreateForm()
    if settings.CREATE_STEER_AI and settings.MOBILE_EDITOR_NAV:
        # Single-field brief: the goal is the whole visible brief, so it takes
        # focus. Only when the wizard flag hides the name field — with the flat
        # layout the name input keeps first position and focus stays contested.
        brief_form.fields['goal'].widget.attrs['autofocus'] = True
    return render(request, 'editor/survey_create.html', {
        'form': form,
        'brief_form': brief_form,
        'ai_available': ai_client.provider_configured(),
    })


def _start_survey_generation(request, form):
    """Validate the brief, enqueue generation, and hand the page to the poller."""
    brief_form = SurveyBriefForm(request.POST)
    if not ai_client.provider_configured():
        return render(request, 'editor/partials/generation_invalid.html', {
            'message': GENERATION_ERROR_COPY['not_configured'],
        })
    if not form.is_valid() or not brief_form.is_valid():
        # A fragment, never the full page: this response is swapped into a
        # small div inside the form the creator is still looking at, so
        # re-rendering survey_create.html here would duplicate every id and
        # re-run the page's Leaflet setup against an initialised map.
        errors = []
        for field_form in (form, brief_form):
            for field_name, messages in field_form.errors.items():
                label = field_form.fields[field_name].label or field_name.replace('_', ' ')
                errors.extend('%s: %s' % (label, message) for message in messages)
        return render(request, 'editor/partials/generation_invalid.html', {
            'message': 'Check the form before generating a draft.',
            'errors': errors,
        })

    languages = form.cleaned_data.get('available_languages') or ['en']
    brief = SurveyBrief(
        name=form.cleaned_data['name'],
        goal=brief_form.cleaned_data['goal'],
        audience=brief_form.cleaned_data['audience'],
        map_target=brief_form.cleaned_data['map_target'],
        use_case=brief_form.cleaned_data['use_case'],
    )
    valid_basemaps = {slug for slug, _ in BASEMAP_CHOICES}
    chosen_basemap = request.POST.get('default_basemap')
    header_overrides = header_overrides_from_form(
        name=form.cleaned_data['name'],
        languages=languages,
        map_lat=request.POST.get('map_lat'),
        map_lng=request.POST.get('map_lng'),
        map_zoom=request.POST.get('map_zoom'),
        default_basemap=chosen_basemap if chosen_basemap in valid_basemaps else None,
    )

    event = start_generation(request.user, request.active_org, brief, languages)
    # Counts and categories only. The brief is the creator's project description,
    # often a client's; it already goes to one processor and PostHog is not going
    # to be a second one.
    pe.emit(pe.AI_DRAFT_REQUESTED, request.user.pk, {
        'language_count': len(languages),
        'has_use_case': bool(brief.use_case),
    })
    generate_survey_draft_task.delay(
        event.id, brief.as_dict(), languages, header_overrides,
    )
    return render(request, 'editor/partials/generation_status.html', {
        'event': event,
    })


def _int_param(raw):
    """A non-negative integer from a query string, or 0 for anything else.

    The value is a hint about what the browser already rendered, not a
    permission or an identifier, so a malformed one deserves a redundant
    fragment rather than a 400.
    """
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


@org_permission_required('editor')
def editor_generation_status(request, event_id):
    """Polled by the create page while a draft is being generated.

    Scoped to the requesting user's own events: the brief is their project
    description, and the event id is a guessable integer.
    """
    event = get_object_or_404(
        AIGenerationEvent, pk=event_id, user=request.user, organization=request.active_org,
    )
    # Hypothesis telemetry, free because it is server-side: each poll stamps
    # last_polled_at, so if the creator closes the tab the stamp freezes at
    # the moment they stopped waiting. Queryset .update() on purpose — the
    # worker writes this row concurrently and a load-modify-save here could
    # clobber a terminal outcome with a stale 'pending'.
    AIGenerationEvent.objects.filter(pk=event.pk).update(last_polled_at=timezone.now())
    if event.outcome == 'pending':
        # Deliberately empty unless there is news: the overlay is already on the
        # page and must not be re-rendered on every tick — swapping it restarted
        # its animations and made the screen flicker. 204 leaves the DOM
        # untouched, so it stays the answer whenever the draft has not moved.
        #
        # The client sends what it already has rather than the server tracking
        # it: this endpoint is hit every 2s for the length of the wait, and
        # per-poll state would mean a write on each one.
        sections = event.sections_drafted or 0
        questions = event.questions_drafted or 0
        known = (_int_param(request.GET.get('sections')),
                 _int_param(request.GET.get('questions')))
        # Questions gate this too, not just sections: a section only closes
        # after all of its questions, so waiting for one meant the counter was
        # blank for most of the generation — observed live on 2026-08-17, one
        # question drafted and nothing on screen. The first question is also
        # exactly the moment the creator most needs to hear "not stuck".
        if (sections, questions) > known and (sections or questions):
            return render(request, 'editor/partials/generation_progress.html', {
                'sections': sections,
                'questions': questions,
            })
        return HttpResponse(status=204)

    if event.outcome == 'success' and event.created_survey_id:
        # The redirect being issued means the creator was still on the page
        # when the draft finished — i.e. they waited. First stamp wins.
        first_redirect = AIGenerationEvent.objects.filter(
            pk=event.pk, redirected_at__isnull=True,
        ).update(redirected_at=timezone.now())
        # The conditional update's row count IS the transition test: a second
        # poll (or a re-opened tab) matches nothing and must not emit again.
        if first_redirect:
            pe.emit(pe.AI_DRAFT_OPENED, request.user.pk, {
                'survey_id': str(event.created_survey_id),
            })
        # HX-Redirect turns the polled fragment into a real navigation, so the
        # creator lands in the editor rather than seeing it swapped into a panel.
        response = HttpResponse(status=204)
        # `?draft=` is what tells the editor this arrival deserves the one-shot
        # feedback prompt. Only this redirect produces it, which is the
        # server-side half of "asked once per draft".
        response['HX-Redirect'] = '%s?draft=%d' % (
            reverse('editor_survey_detail',
                    kwargs={'survey_uuid': event.created_survey.uuid}),
            event.pk,
        )
        return response

    return render(request, 'editor/partials/generation_failed.html', {
        'event': event,
        'message': GENERATION_ERROR_COPY.get(event.outcome, GENERATION_ERROR_COPY['error']),
    })


# ─── Survey editor main page ─────────────────────────────────────────────────

@survey_permission_required('viewer')
def editor_survey_detail(request, survey_uuid):
    survey = request.survey
    sections = _get_sections_ordered(survey)

    settings_panel_active = (
        request.GET.get('panel') == 'settings'
        and request.effective_survey_role == 'owner'
    )
    thanks_panel_active = (
        request.GET.get('panel') == 'thanks'
        and request.effective_survey_role in ('editor', 'owner')
    )

    current_section = None
    if not settings_panel_active and not thanks_panel_active:
        current_section_id = request.GET.get('section')
        if current_section_id:
            current_section = SurveySection.objects.filter(
                id=current_section_id, survey_header=survey
            ).first()
        if not current_section and sections:
            current_section = sections[0]

    questions = []
    if current_section:
        questions = list(
            Question.objects.filter(
                survey_section=current_section,
                parent_question_id__isnull=True,
            ).order_by('order_number')
        )

    can_edit = request.effective_survey_role in ('editor', 'owner')
    is_read_only = survey.status in ('published', 'closed')
    is_owner = request.effective_survey_role == 'owner'

    # Versioning context
    draft_copy = survey.get_draft_copy() if not survey.is_draft_copy else None
    show_edit_published = (
        is_owner and survey.status in ('published', 'closed') and not survey.has_draft_copy()
    )
    show_draft_actions = is_owner and survey.is_draft_copy
    # An accidental publish is undoable while nothing has been collected. Offered
    # alongside the draft-copy route so the read-only notice always ends in an
    # action the author can take.
    show_back_to_draft = (
        is_owner and is_read_only and not survey.is_draft_copy and survey.has_never_collected()
    )

    # The one-shot AI-draft feedback prompt, keyed by the generation redirect's
    # ?draft=. An unvalidated id must not conjure UI: the event has to be the
    # requesting user's own AND the one that produced THIS survey — one indexed
    # lookup. Forged, foreign or mismatched ids fall through to None.
    feedback_trace_id = None
    draft_param = _int_param(request.GET.get('draft'))
    if draft_param:
        draft_event = AIGenerationEvent.objects.filter(
            pk=draft_param, user=request.user, created_survey=survey,
        ).only('id').first()
        if draft_event is not None:
            feedback_trace_id = pe.llm_trace_id(draft_event.pk)

    return render(request, 'editor/survey_detail.html', {
        'session_count': survey.surveysession_set.count(),
        'ai_feedback_trace_id': feedback_trace_id,
        'survey': survey,
        'sections': sections,
        'current_section': current_section,
        'settings_panel_active': settings_panel_active,
        'thanks_panel_active': thanks_panel_active,
        'questions': questions,
        'effective_role': request.effective_survey_role,
        'can_edit': can_edit and not is_read_only,
        'is_read_only': is_read_only,
        'is_owner': is_owner,
        'draft_copy': draft_copy,
        'show_edit_published': show_edit_published,
        'show_draft_actions': show_draft_actions,
        'show_back_to_draft': show_back_to_draft,
    })


# ─── Survey settings ─────────────────────────────────────────────────────────

@survey_permission_required('owner')
def editor_survey_settings(request, survey_uuid):
    survey = request.survey
    if request.method == 'POST':
        form = SurveyHeaderForm(request.POST, request.FILES, instance=survey)
        if form.is_valid():
            form.save()
            return redirect('editor_survey_settings', survey_uuid=survey.uuid)
    else:
        form = SurveyHeaderForm(instance=survey)
    return render(request, 'editor/survey_settings.html', {
        'survey': survey,
        'form': form,
        'effective_role': request.effective_survey_role,
        'basemap_choices': BASEMAP_CHOICES,
        'map_layers': _editor_layers(survey),
        'layers_enabled': settings.MAP_REFERENCE_LAYERS,
    })


@survey_permission_required('owner')
def editor_survey_settings_panel(request, survey_uuid):
    """Same settings as editor_survey_settings, rendered as an HTMX-swappable
    partial for the pinned "Survey settings" entry in the editor sidebar. The
    general fields autosave (mirrors public_results_editor.py's pattern); Map
    Position / Collaborators / Password keep their own dedicated controls.
    """
    survey = request.survey
    if request.method == 'POST':
        form = SurveyHeaderForm(request.POST, request.FILES, instance=survey)
        if form.is_valid():
            form.save()
            if _is_ajax(request):
                return JsonResponse({'ok': True})
            from django.urls import reverse
            return redirect('{}?panel=settings'.format(reverse('editor_survey_detail', args=[survey.uuid])))
        elif _is_ajax(request):
            return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    else:
        form = SurveyHeaderForm(instance=survey)
    return render(request, 'editor/partials/survey_settings_panel.html', {
        'survey': survey,
        'form': form,
        'effective_role': request.effective_survey_role,
        'basemap_choices': BASEMAP_CHOICES,
        'map_layers': _editor_layers(survey),
        'layers_enabled': settings.MAP_REFERENCE_LAYERS,
    })


@survey_permission_required('editor')
def editor_survey_thanks_panel(request, survey_uuid):
    """WYSIWYG editor for the survey's thanks page, as an HTMX-swappable partial
    for the pinned "Thanks page" entry (the last Build step). Per-language HTML
    is sanitized on save and stored in SurveyHeader.thanks_html; autosaves.
    """
    from .views import sanitize_thanks_html
    survey = request.survey
    langs = list(survey.available_languages) or ['en']
    results_page = getattr(survey, 'public_results_page', None)

    if request.method == 'POST':
        thanks = {}
        for lang in langs:
            cleaned = sanitize_thanks_html(request.POST.get('thanks_{}'.format(lang), ''))
            if cleaned:
                thanks[lang] = cleaned
        survey.thanks_html = thanks
        survey.save(update_fields=['thanks_html'])
        # The "See the results" toggle lives on the results page; save it here too.
        # A hidden marker tells us the checkbox was actually in the submitted form
        # (an unchecked box sends nothing), so a stale form can't clobber it.
        if results_page is not None and request.POST.get('has_results_toggle') == '1':
            results_page.show_on_thanks = request.POST.get('show_on_thanks') == 'on'
            results_page.save(update_fields=['show_on_thanks'])
        if _is_ajax(request):
            return JsonResponse({'ok': True})
        from django.urls import reverse
        return redirect('{}?panel=thanks'.format(reverse('editor_survey_detail', args=[survey.uuid])))

    existing = survey.thanks_html or {}
    if isinstance(existing, str):
        existing = {langs[0]: existing}
    thanks_by_lang = {lang: existing.get(lang, '') for lang in langs}
    return render(request, 'editor/partials/thanks_panel.html', {
        'survey': survey,
        'langs': langs,
        'thanks_by_lang': thanks_by_lang,
        'results_page': results_page,
        'effective_role': request.effective_survey_role,
    })


@survey_permission_required('viewer')
def editor_survey_thanks_preview(request, survey_uuid):
    """Editor-only render of the thanks page for the live-preview iframe.

    Renders the same public thanks template in the requested language, but
    gated on editor access (so draft/private surveys preview too) and with no
    session side effects (unlike the public survey_thanks view).
    """
    from .views import resolve_thanks_html
    survey = request.survey
    lang = request.GET.get('lang') or (survey.available_languages[0] if survey.available_languages else 'en')
    return render(request, 'survey_thanks.html', {
        'survey': survey,
        'thanks_html': resolve_thanks_html(survey.thanks_html, lang),
        'lang': lang,
    })


@survey_permission_required('editor')
@require_POST
def editor_survey_thanks_image(request, survey_uuid):
    """Upload an image for the thanks-page editor; returns its URL as JSON.

    Stored via the default storage (local media or S3) so the thanks HTML holds
    a plain URL instead of a bloated base64 data URI.
    """
    import os
    import uuid as _uuid
    from django.core.files.storage import default_storage
    f = request.FILES.get('image')
    if not f:
        return JsonResponse({'error': 'No file'}, status=400)
    if f.content_type not in ('image/png', 'image/jpeg', 'image/gif', 'image/webp'):
        return JsonResponse({'error': 'Unsupported image type'}, status=400)
    if f.size > 5 * 1024 * 1024:
        return JsonResponse({'error': 'Image too large (max 5 MB)'}, status=400)
    ext = (os.path.splitext(f.name)[1] or '.png')[:8]
    name = default_storage.save('thanks_images/{}{}'.format(_uuid.uuid4().hex, ext), f)
    return JsonResponse({'url': default_storage.url(name)})


# ─── Reference overlay layers ────────────────────────────────────────────────

def _editor_layers(survey):
    """Layers with their property names, for the settings card's field pickers."""
    if not settings.MAP_REFERENCE_LAYERS:
        return []
    return [
        {'layer': layer, 'properties': _layer_property_names(layer)}
        for layer in survey.map_layers.all()
    ]


def _layer_payload(layer, properties=None):
    data = {
        'id': layer.pk,
        'name': layer.name,
        'color': layer.color,
        'label_field': layer.label_field,
        'key_field': layer.key_field,
        'show_popups': layer.show_popups,
        'feature_count': layer.feature_count,
        'size_bytes': layer.size_bytes,
    }
    if properties is not None:
        data['properties'] = properties
    return data


def _layers_enabled_or_404():
    if not settings.MAP_REFERENCE_LAYERS:
        raise Http404


@survey_permission_required('owner')
@require_POST
def editor_survey_layer_create(request, survey_uuid):
    """Upload a GeoJSON reference layer.

    Validation lives in survey.layers so an interactive upload, a ZIP import and
    an AI-written draft cannot diverge on what a stored layer may contain.
    """
    _layers_enabled_or_404()
    survey = request.survey
    f = request.FILES.get('layer')
    if not f:
        return JsonResponse({'error': 'No file'}, status=400)
    if survey.map_layers.count() >= MAX_LAYERS_PER_SURVEY:
        return JsonResponse({'error': f'A survey can hold {MAX_LAYERS_PER_SURVEY} reference layers.'}, status=400)
    if f.size > MAX_LAYER_BYTES:
        return JsonResponse({'error': f'File is larger than {MAX_LAYER_BYTES // (1024 * 1024)} MB.'}, status=400)
    try:
        geojson_str, count, properties = validate_layer_upload(f.read())
    except LayerValidationError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    name = (os.path.splitext(f.name)[0] or 'Layer')[:100]
    position = (survey.map_layers.aggregate(m=models.Max('position'))['m'] or 0) + 1
    layer = SurveyMapLayer.objects.create(
        survey=survey, name=name, geojson=geojson_str,
        feature_count=count, size_bytes=len(geojson_str.encode('utf-8')),
        position=position,
    )
    return JsonResponse(_layer_payload(layer, properties), status=201)


@survey_permission_required('owner')
@require_POST
def editor_survey_layer_update(request, survey_uuid, layer_id):
    """Update a layer's presentation config (never its geometry)."""
    _layers_enabled_or_404()
    layer = get_object_or_404(SurveyMapLayer, pk=layer_id, survey=request.survey)

    name = (request.POST.get('name') or '').strip()
    if name:
        layer.name = name[:100]
    color = (request.POST.get('color') or '').strip()
    if color:
        if not re.match(r'^#[0-9a-fA-F]{6}$', color):
            return JsonResponse({'error': 'Color must be #RRGGBB.'}, status=400)
        layer.color = color

    # Field names are only meaningful if they exist in the file; an unknown one
    # would silently render no labels, so refuse it instead.
    known = _layer_property_names(layer)
    for field in ('label_field', 'key_field'):
        if field in request.POST:
            value = (request.POST.get(field) or '').strip()[:100]
            if value and value not in known:
                return JsonResponse({'error': f'"{value}" is not a property of this layer.'}, status=400)
            setattr(layer, field, value)

    if 'show_popups' in request.POST:
        layer.show_popups = request.POST.get('show_popups') in ('1', 'true', 'on')

    layer.save()
    return JsonResponse(_layer_payload(layer, known))


@survey_permission_required('owner')
@require_POST
def editor_survey_layer_delete(request, survey_uuid, layer_id):
    _layers_enabled_or_404()
    layer = get_object_or_404(SurveyMapLayer, pk=layer_id, survey=request.survey)
    layer.delete()
    return HttpResponse(status=204)


def _layer_property_names(layer):
    """Property names present in a stored layer, for the field pickers."""
    try:
        parsed = json.loads(layer.geojson)
    except ValueError:
        return []
    names = set()
    for feature in parsed.get('features') or []:
        props = feature.get('properties')
        if isinstance(props, dict):
            names.update(k for k in props if isinstance(k, str))
    return sorted(names)


# ─── Survey map position ─────────────────────────────────────────────────────

@survey_permission_required('owner')
@require_POST
def editor_survey_map_position(request, survey_uuid):
    survey = request.survey
    clear_position = request.POST.get('clear_position', '0') == '1'

    if clear_position:
        survey.start_map_postion = None
        survey.start_map_zoom = None
    else:
        lat = float(request.POST.get('lat', 52.52))
        lng = float(request.POST.get('lng', 13.405))
        zoom = int(request.POST.get('zoom', 12))
        survey.start_map_postion = Point(lng, lat)
        survey.start_map_zoom = zoom

    survey.use_geolocation = request.POST.get('use_geolocation', '0') == '1'
    survey.save(update_fields=['start_map_postion', 'start_map_zoom', 'use_geolocation'])
    return HttpResponse(status=204)


# ─── Section CRUD ─────────────────────────────────────────────────────────────

@survey_permission_required('editor')
@require_POST
def editor_section_create(request, survey_uuid):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    sections = _get_sections_ordered(survey)

    # Generate next section number (avoid name collisions)
    existing_names = set(s.name for s in sections)
    count = len(sections) + 1
    while f'section_{count}' in existing_names:
        count += 1
    section = SurveySection.objects.create(
        survey_header=survey,
        name=f'section_{count}',
        title=f'Section {count}',
        code=f'S{count}',
        is_head=(not sections),
    )

    # Append to linked list
    if sections:
        last = sections[-1]
        last.next_section = section
        last.save(update_fields=['next_section'])
        section.prev_section = last
        section.save(update_fields=['prev_section'])

    return render(request, 'editor/partials/section_list_item.html', {
        'section': section,
        'survey': survey,
        'is_current': False,
    })


@survey_permission_required('editor')
def editor_section_detail(request, survey_uuid, section_id):
    survey = request.survey
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)

    if request.method == 'POST':
        blocked = _check_structural_edit_allowed(survey)
        if blocked:
            return blocked
        form = SurveySectionForm(request.POST, instance=section)
        if form.is_valid():
            form.save()
            # Save translations
            _save_section_translations(request, section, survey)
            if request.headers.get('HX-Request'):
                return HttpResponse(status=204, headers={'HX-Trigger': 'sectionSaved'})
            return redirect('editor_survey_detail', survey_uuid=survey.uuid)
    else:
        form = SurveySectionForm(instance=section)

    translations = {t.language: t for t in section.translations.all()}
    questions = list(
        Question.objects.filter(
            survey_section=section,
            parent_question_id__isnull=True,
        ).order_by('order_number')
    )

    hidden_ids = set(i for i in (section.hidden_layers or []) if isinstance(i, int))
    return render(request, 'editor/partials/section_detail_form.html', {
        'survey': survey,
        'section': section,
        'form': form,
        'translations': translations,
        'questions': questions,
        'is_read_only': survey.status in ('published', 'closed'),
        'layers_enabled': settings.MAP_REFERENCE_LAYERS,
        'section_layers': [
            {'layer': layer, 'visible': layer.pk not in hidden_ids}
            for layer in survey.map_layers.all()
        ] if settings.MAP_REFERENCE_LAYERS else [],
    })


def _translation_languages(survey):
    """Languages that carry translation rows: everything after the primary.

    The first entry of available_languages is the survey's primary language;
    its content lives in base model fields only. Iterating this instead of the
    full list is also what makes stale translation_<primary>_* POST keys
    (old open forms) a no-op instead of a resurrected duplicate row.
    """
    return (survey.available_languages or [])[1:]


def _save_section_translations(request, section, survey):
    """Save section translations from POST data (non-primary languages only)."""
    for lang in _translation_languages(survey):
        title = request.POST.get(f'translation_{lang}_title', '').strip()
        subheading = coerce_creator_html(
            request.POST.get(f'translation_{lang}_subheading', '')).strip()
        next_label = request.POST.get(f'translation_{lang}_next_label', '').strip()[:30]
        if title or subheading or next_label:
            SurveySectionTranslation.objects.update_or_create(
                section=section, language=lang,
                defaults={'title': title or None, 'subheading': subheading or None,
                          'next_label': next_label or None},
            )
        else:
            SurveySectionTranslation.objects.filter(section=section, language=lang).delete()


@survey_permission_required('editor')
@require_POST
def editor_section_delete(request, survey_uuid, section_id):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)

    # Before the re-linking below, which must not run on a refused delete.
    refusal = _refuse_if_answers_at_risk(request, survey, section.answer_count())
    if refusal:
        return refusal

    prev_sec = section.prev_section
    next_sec = section.next_section

    # Re-link neighbors
    if prev_sec:
        prev_sec.next_section = next_sec
        prev_sec.save(update_fields=['next_section'])
    if next_sec:
        next_sec.prev_section = prev_sec
        next_sec.save(update_fields=['prev_section'])
        # If deleted section was head, promote next
        if section.is_head:
            next_sec.is_head = True
            next_sec.save(update_fields=['is_head'])

    section.delete()
    response = HttpResponse('')
    response['HX-Trigger-After-Swap'] = 'sectionDeleted'
    return response


# ─── Section reordering ───────────────────────────────────────────────────────

@survey_permission_required('editor')
@require_POST
def editor_sections_reorder(request, survey_uuid):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    section_ids = request.POST.getlist('section_ids[]')

    if not section_ids:
        try:
            body = json.loads(request.body)
            section_ids = body.get('section_ids', [])
        except (json.JSONDecodeError, ValueError):
            return HttpResponse(status=400)

    section_ids = [int(sid) for sid in section_ids]
    sections = {s.id: s for s in SurveySection.objects.filter(survey_header=survey)}

    with transaction.atomic():
        for i, sid in enumerate(section_ids):
            s = sections.get(sid)
            if not s:
                continue
            s.is_head = (i == 0)
            s.prev_section = sections.get(section_ids[i - 1]) if i > 0 else None
            s.next_section = sections.get(section_ids[i + 1]) if i < len(section_ids) - 1 else None
            s.save(update_fields=['is_head', 'prev_section', 'next_section'])

    return HttpResponse(status=204)


# ─── Question CRUD ────────────────────────────────────────────────────────────

@survey_permission_required('editor')
def editor_question_create(request, survey_uuid, section_id):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)

    if request.method == 'POST':
        form = QuestionForm(request.POST, request.FILES, section=section)
        if form.is_valid():
            question = form.save(commit=False)
            question.survey_section = section
            # Auto-assign next order number
            max_order = Question.objects.filter(
                survey_section=section, parent_question_id__isnull=True
            ).aggregate(Max('order_number'))['order_number__max']
            question.order_number = (max_order or 0) + 1
            # Handle choices. Non-choice types must never keep a choices
            # list (the widget still posts choices_json across a type switch);
            # stale choices used to reroute answer storage — see CHOICE_TYPES.
            choices_json = request.POST.get('choices_json', '').strip()
            if question.input_type not in CHOICE_TYPES:
                question.choices = None
            elif choices_json:
                question.choices = _guard_choice_codes(question, json.loads(choices_json))
            question.save()
            # Funnel stage, so it fires only for a survey's *first* question --
            # emitting per question would make the step count questions rather
            # than creators who got past the empty editor.
            if not Question.objects.filter(
                survey_section__survey_header=survey,
            ).exclude(pk=question.pk).exists():
                pe.emit(pe.SURVEY_QUESTION_ADDED, request.user.pk,
                        {'survey_id': str(survey.id)})
            _save_question_translations(request, question, survey)
            response = render(request, 'editor/partials/question_list_item.html', {
                'question': question,
                'survey': survey,
                'is_read_only': survey.status in ('published', 'closed'),
            })
            response['HX-Trigger'] = 'questionSaved'
            return response
        # Form invalid — re-render modal with errors
        return render(request, 'editor/partials/question_form_modal.html', {
            'form': form,
            'survey': survey,
            'section': section,
        })
    else:
        form = QuestionForm(section=section)
    return render(request, 'editor/partials/question_form_modal.html', {
        'form': form,
        'survey': survey,
        'section': section,
    })


@survey_permission_required('editor')
def editor_question_edit(request, survey_uuid, question_id):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    question = get_object_or_404(Question, id=question_id, survey_section__survey_header=survey)
    is_subquestion = question.parent_question_id_id is not None

    if request.method == 'POST':
        form = QuestionForm(request.POST, request.FILES, instance=question, is_subquestion=is_subquestion, section=question.survey_section)
        if form.is_valid():
            q = form.save(commit=False)
            choices_json = request.POST.get('choices_json', '').strip()
            if q.input_type not in CHOICE_TYPES:
                # The choices widget keeps choices_json populated across a type
                # switch, so the type decides — not the posted field.
                q.choices = None
            elif choices_json:
                q.choices = _guard_choice_codes(question, json.loads(choices_json))
            # Validation settings per question type
            vs = {}
            if q.input_type in ('number', 'range'):
                for key in ('min_value', 'max_value', 'outlier_sigma'):
                    val = request.POST.get(f'vs_{key}', '').strip()
                    if val:
                        try: vs[key] = float(val)
                        except ValueError: pass
            elif q.input_type in ('text', 'text_line'):
                val = request.POST.get('vs_min_length', '').strip()
                if val:
                    try: vs['min_length'] = int(val)
                    except ValueError: pass
            elif q.input_type == 'polygon':
                val = request.POST.get('vs_area_outlier_factor', '').strip()
                if val:
                    try: vs['area_outlier_factor'] = float(val)
                    except ValueError: pass
            # Feature-count limits apply to every geo type (polygon keeps its
            # area factor above as well, hence a separate `if`, not `elif`)
            if q.input_type in ('point', 'line', 'polygon'):
                for key, floor in (('min_features', 0), ('max_features', 1)):
                    val = request.POST.get(f'vs_{key}', '').strip()
                    if val:
                        try:
                            parsed = int(val)
                        except ValueError:
                            continue
                        if parsed >= floor:
                            vs[key] = parsed
                if 'min_features' in vs and 'max_features' in vs and vs['max_features'] < vs['min_features']:
                    form.add_error(None, 'Max places must be greater than or equal to min places.')
                    return render(request, 'editor/partials/question_form_modal.html', {
                        'form': form,
                        'survey': survey,
                        'section': question.survey_section,
                        'question': question,
                    })
            q.validation_settings = vs
            q.save()
            _save_question_translations(request, q, survey)
            response = render(request, 'editor/partials/question_list_item.html', {
                'question': q,
                'survey': survey,
                'is_read_only': survey.status in ('published', 'closed'),
            })
            response['HX-Trigger'] = 'questionSaved'
            return response
        if request.POST.get('autosave'):
            # Autosave must never replace the form the creator is typing in —
            # report the errors and let the client show the indicator instead
            # (openspec: mobile-adaptive-refactor, editor-autosave).
            return JsonResponse({'ok': False, 'errors': form.errors}, status=422)
        return render(request, 'editor/partials/question_form_modal.html', {
            'form': form,
            'survey': survey,
            'section': question.survey_section,
            'question': question,
        })
    else:
        form = QuestionForm(instance=question, is_subquestion=is_subquestion, section=question.survey_section)
    return render(request, 'editor/partials/question_form_modal.html', {
        'form': form,
        'survey': survey,
        'section': question.survey_section,
        'question': question,
    })


@survey_permission_required('viewer')
@xframe_options_sameorigin
def editor_question_preview(request, survey_uuid, question_id):
    survey = request.survey
    question = get_object_or_404(Question, id=question_id, survey_section__survey_header=survey)

    lang = _preview_language(request, survey)

    # Unsaved picker state from the question modal ("Display as" live preview).
    # Applied to the in-memory instance before the field is built, so for
    # `range` the override also decides the field type, not just the widget.
    style_override = request.GET.get('display_style')
    if style_override in ('default', 'scale_strip', 'list_pips'):
        question.display_style = style_override

    form = SurveySectionAnswerForm.single_question_form(question, lang)

    return _render_preview_frame(request, form, question, lang)


def _preview_language(request, survey):
    lang = request.GET.get('lang')
    if lang and survey.available_languages and lang not in survey.available_languages:
        lang = None
    if not lang and survey.available_languages:
        lang = survey.available_languages[0]
    return lang


def _render_preview_frame(request, form, question, lang, is_type_example=False):
    if lang:
        translation.activate(lang)
    response = render(request, 'editor/partials/question_preview_frame.html', {
        'form': form,
        'question': question,
        'is_type_example': is_type_example,
    })
    if lang:
        translation.deactivate()
    return response


@survey_permission_required('viewer')
@require_POST
@xframe_options_sameorigin
def editor_question_preview_live(request, survey_uuid, section_id):
    """Respondent-side render of the question modal's current, unsaved state.

    The modal posts its live values; an in-memory Question is built and pushed
    through the same form machinery respondents hit. Nothing is ever saved —
    this is how the dialog can show a real preview of a question that does not
    exist yet.
    """
    survey = request.survey
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)

    input_type = request.POST.get('input_type', '')
    if input_type not in {value for value, _ in INPUT_TYPE_CHOICES}:
        return HttpResponse('unknown input type', status=400)

    display_style = request.POST.get('display_style', 'default')
    allowed_styles = (
        {'default', 'dropdown'} if input_type == 'choice'
        else {value for value, _ in DISPLAY_STYLE_CHOICES}
    )
    if display_style not in allowed_styles:
        display_style = 'default'

    # A draft's choices arrive as the modal's serialized JSON. Malformed or
    # odd-shaped payloads degrade to "no choices" — every choice-consuming
    # type already has a fallback render for that — rather than erroring the
    # preview pane.
    choices = None
    raw_choices = request.POST.get('choices_json', '').strip()
    if raw_choices:
        try:
            parsed = json.loads(raw_choices)
        except ValueError:
            parsed = None
        if isinstance(parsed, list):
            cleaned = [
                c for c in parsed
                if isinstance(c, dict)
                and isinstance(c.get('code'), (int, float))
                and not isinstance(c.get('code'), bool)
                and 'name' in c
            ]
            choices = cleaned or None

    question = Question(
        survey_section=section,
        input_type=input_type,
        name=request.POST.get('name', '').strip(),
        # Put through the same allow-list a save would, so the preview shows what
        # the question will actually become rather than the raw draft.
        subtext=coerce_creator_html(request.POST.get('subtext', '')),
        choices=choices,
        color=request.POST.get('color', '').strip() or '#000000',
        icon_class=request.POST.get('icon_class', '').strip(),
        display_style=display_style,
        required=False,
    )

    lang = _preview_language(request, survey)
    form = SurveySectionAnswerForm.single_question_form(question, lang)

    return _render_preview_frame(request, form, question, lang,
                                 is_type_example=request.POST.get('example') == '1')


@survey_permission_required('editor')
@require_POST
def editor_question_delete(request, survey_uuid, question_id):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    question = get_object_or_404(Question, id=question_id, survey_section__survey_header=survey)

    refusal = _refuse_if_answers_at_risk(request, survey, question.answer_count())
    if refusal:
        return refusal

    question.delete()
    return HttpResponse('')


def _save_question_translations(request, question, survey):
    """Save question translations from POST data (non-primary languages only)."""
    for lang in _translation_languages(survey):
        name = request.POST.get(f'translation_{lang}_name', '').strip()
        # Same allow-list the base language goes through in QuestionForm; a
        # translated subtext is rendered |safe just the same.
        subtext = coerce_creator_html(
            request.POST.get(f'translation_{lang}_subtext', '')).strip()
        if name or subtext:
            QuestionTranslation.objects.update_or_create(
                question=question, language=lang,
                defaults={'name': name or None, 'subtext': subtext or None},
            )
        else:
            QuestionTranslation.objects.filter(question=question, language=lang).delete()


# ─── Question reordering ─────────────────────────────────────────────────────

@survey_permission_required('editor')
@require_POST
def editor_questions_reorder(request, survey_uuid):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    question_ids = request.POST.getlist('question_ids[]')

    if not question_ids:
        try:
            body = json.loads(request.body)
            question_ids = body.get('question_ids', [])
        except (json.JSONDecodeError, ValueError):
            return HttpResponse(status=400)

    with transaction.atomic():
        for i, qid in enumerate(question_ids):
            Question.objects.filter(
                id=int(qid), survey_section__survey_header=survey
            ).update(order_number=i)

    return HttpResponse(status=204)


# ─── Sub-question CRUD ────────────────────────────────────────────────────────

@survey_permission_required('editor')
def editor_subquestion_create(request, survey_uuid, parent_id):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    parent = get_object_or_404(Question, id=parent_id, survey_section__survey_header=survey)

    if request.method == 'POST':
        form = QuestionForm(request.POST, request.FILES, is_subquestion=True)
        if form.is_valid():
            question = form.save(commit=False)
            question.survey_section = parent.survey_section
            question.parent_question_id = parent
            max_order = Question.objects.filter(
                parent_question_id=parent
            ).aggregate(Max('order_number'))['order_number__max']
            question.order_number = (max_order or 0) + 1
            choices_json = request.POST.get('choices_json', '').strip()
            if question.input_type not in CHOICE_TYPES:
                question.choices = None
            elif choices_json:
                question.choices = _guard_choice_codes(question, json.loads(choices_json))
            question.save()
            _save_question_translations(request, question, survey)
            # Return the parent question item (includes sub-questions)
            response = render(request, 'editor/partials/question_list_item.html', {
                'question': parent,
                'survey': survey,
                'is_read_only': survey.status in ('published', 'closed'),
            })
            response['HX-Trigger'] = 'questionSaved'
            return response
    else:
        form = QuestionForm(is_subquestion=True)
    return render(request, 'editor/partials/question_form_modal.html', {
        'form': form,
        'survey': survey,
        'section': parent.survey_section,
        'parent': parent,
    })


# ─── Duplicate / Copy-Paste (Issue #16) ──────────────────────────────────────


def _shift_order_numbers_down(survey_section, parent, after_order):
    """Increment order_number by 1 for all questions strictly after ``after_order``
    in the given (section, parent) bucket — single bulk UPDATE, atomic at SQL level."""
    from django.db.models import F
    qs = Question.objects.filter(survey_section=survey_section, order_number__gt=after_order)
    if parent is None:
        qs = qs.filter(parent_question_id__isnull=True)
    else:
        qs = qs.filter(parent_question_id=parent)
    qs.update(order_number=F('order_number') + 1)


@survey_permission_required('editor')
@require_POST
def editor_question_duplicate(request, survey_uuid, question_id):
    """Duplicate a question in place: clone with a new code and ' (copy)' suffix,
    insert immediately after the source (sibling). Top-level or sub-question."""
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    source = get_object_or_404(Question, id=question_id, survey_section__survey_header=survey)
    parent = source.parent_question_id  # FK; None for top-level

    with transaction.atomic():
        _shift_order_numbers_down(source.survey_section, parent, source.order_number)
        new_question = clone_question(
            source,
            target_section=source.survey_section,
            parent=parent,
            regenerate_code=True,
            name_suffix=' (copy)',
            copy_sub_questions=True,
        )
        new_question.order_number = source.order_number + 1
        new_question.save(update_fields=['order_number'])

    response = render(request, 'editor/partials/question_list_item.html', {
        'question': new_question,
        'survey': survey,
        'is_read_only': survey.status in ('published', 'closed'),
    })
    response['HX-Trigger'] = 'questionSaved'
    return response


@survey_permission_required('editor')
@require_POST
def editor_section_duplicate(request, survey_uuid, section_id):
    """Duplicate a section in place: clone all questions/translations, splice
    immediately after the source in the linked list, append ' (copy)' to title."""
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    source = get_object_or_404(SurveySection, id=section_id, survey_header=survey)

    with transaction.atomic():
        new_section = clone_section(
            source,
            target_survey=survey,
            insert_after=source,
            name_suffix=' (copy)',
        )

    response = render(request, 'editor/partials/section_list_item.html', {
        'section': new_section,
        'survey': survey,
        'is_current': False,
    })
    response['HX-Trigger'] = 'sectionSaved'
    return response


def _paste_payload(request):
    """Read paste-endpoint payload from JSON body OR form-encoded POST.

    Accepts both because:
    - Pure HTMX buttons send form-urlencoded (default).
    - JS-driven calls (Clipboard.pasteQuestion) send JSON for stricter typing.
    Returns a dict, never None — missing keys are checked by the caller.
    """
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body or b'{}')
        except (json.JSONDecodeError, ValueError):
            return {}
    return {k: v for k, v in request.POST.items()}


@survey_permission_required('editor')
@require_POST
def editor_question_paste(request, survey_uuid, section_id):
    """Paste a question from the clipboard into the given section.

    Body JSON: {source_survey_uuid, source_question_id, parent_question_id?}.
    - parent_question_id absent / null → paste as top-level. If the source is a
      sub-question it is PROMOTED (parent_question_id=None on the clone).
    - parent_question_id set → paste as sub-question of that geo parent. The
      source's input_type must NOT be geo (per issue #17 rule); otherwise 400.
      The source's own sub-questions are NOT cloned (Q8).
    """
    target_survey = request.survey
    blocked = _check_structural_edit_allowed(target_survey)
    if blocked:
        return blocked
    target_section = get_object_or_404(
        SurveySection, id=section_id, survey_header=target_survey
    )

    payload = _paste_payload(request)
    source_survey_uuid = payload.get('source_survey_uuid')
    source_question_id = payload.get('source_question_id')
    parent_question_id = payload.get('parent_question_id')
    if not source_survey_uuid or not source_question_id:
        return HttpResponse('Missing source_survey_uuid or source_question_id', status=400)
    try:
        source_question_id = int(source_question_id)
    except (TypeError, ValueError):
        return HttpResponse('Invalid source_question_id', status=400)
    if parent_question_id in (None, '', 'null'):
        parent_question_id = None
    else:
        try:
            parent_question_id = int(parent_question_id)
        except (TypeError, ValueError):
            return HttpResponse('Invalid parent_question_id', status=400)

    source_survey = get_object_or_404(SurveyHeader, uuid=source_survey_uuid)
    if not _can_read_survey(request.user, source_survey):
        return HttpResponse('Source survey not accessible', status=404)

    source = get_object_or_404(
        Question, id=source_question_id, survey_section__survey_header=source_survey
    )

    target_parent = None
    if parent_question_id is not None:
        target_parent = get_object_or_404(
            Question, id=parent_question_id, survey_section=target_section
        )
        if source.input_type in SUBQUESTION_DISALLOWED_INPUT_TYPES:
            return JsonResponse(
                {'error': 'Sub-question cannot be a geo-type question'},
                status=400,
            )

    with transaction.atomic():
        max_order = Question.objects.filter(
            survey_section=target_section,
            parent_question_id=target_parent,
        ).aggregate(Max('order_number'))['order_number__max']
        new_question = clone_question(
            source,
            target_section=target_section,
            parent=target_parent,
            regenerate_code=True,
            name_suffix=None,
            copy_sub_questions=(target_parent is None),
        )
        new_question.order_number = (max_order or 0) + 1
        new_question.save(update_fields=['order_number'])

    response = render(request, 'editor/partials/question_list_item.html', {
        'question': target_parent if target_parent is not None else new_question,
        'survey': target_survey,
        'is_read_only': target_survey.status in ('published', 'closed'),
    })
    response['HX-Trigger'] = 'questionSaved'
    return response


@survey_permission_required('editor')
@require_POST
def editor_section_paste(request, survey_uuid):
    """Paste a section from the clipboard into the target survey at the tail.

    Body JSON: {source_survey_uuid, source_section_id}.
    """
    target_survey = request.survey
    blocked = _check_structural_edit_allowed(target_survey)
    if blocked:
        return blocked

    payload = _paste_payload(request)
    source_survey_uuid = payload.get('source_survey_uuid')
    source_section_id = payload.get('source_section_id')
    if not source_survey_uuid or not source_section_id:
        return HttpResponse('Missing source_survey_uuid or source_section_id', status=400)
    try:
        source_section_id = int(source_section_id)
    except (TypeError, ValueError):
        return HttpResponse('Invalid source_section_id', status=400)

    source_survey = get_object_or_404(SurveyHeader, uuid=source_survey_uuid)
    if not _can_read_survey(request.user, source_survey):
        return HttpResponse('Source survey not accessible', status=404)
    source = get_object_or_404(
        SurveySection, id=source_section_id, survey_header=source_survey
    )

    with transaction.atomic():
        new_section = clone_section(
            source,
            target_survey=target_survey,
            insert_after=None,
            name_suffix=None,
        )

    response = render(request, 'editor/partials/section_list_item.html', {
        'section': new_section,
        'survey': target_survey,
        'is_current': False,
    })
    response['HX-Trigger'] = 'sectionSaved'
    return response


# ─── Section map position picker ─────────────────────────────────────────────

@survey_permission_required('editor')
def editor_section_map_picker(request, survey_uuid, section_id):
    survey = request.survey
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)

    if request.method == 'POST':
        blocked = _check_structural_edit_allowed(survey)
        if blocked:
            return blocked
        use_geolocation = request.POST.get('use_geolocation', '0') == '1'
        clear_position = request.POST.get('clear_position', '0') == '1'
        override_basemap = request.POST.get('override_basemap', '') or None

        if clear_position:
            section.start_map_postion = None
            section.start_map_zoom = None
        else:
            lat = float(request.POST.get('lat', 52.52))
            lng = float(request.POST.get('lng', 13.405))
            zoom = int(request.POST.get('zoom', 12))
            section.start_map_postion = Point(lng, lat)
            section.start_map_zoom = zoom

        section.use_geolocation = use_geolocation
        section.override_basemap = override_basemap
        section.save(update_fields=['start_map_postion', 'start_map_zoom', 'use_geolocation', 'override_basemap'])
        return HttpResponse(status=204, headers={'HX-Trigger': 'mapPositionSaved'})

    return render(request, 'editor/partials/section_map_picker.html', {
        'survey': survey,
        'section': section,
        'basemap_choices': BASEMAP_CHOICES,
    })


# ─── Live preview ─────────────────────────────────────────────────────────────

@survey_permission_required('viewer')
@xframe_options_sameorigin
def editor_section_preview(request, survey_uuid, section_name):
    # Local import: views imports editor_forms, so a module-level import here
    # would close the circle (the two thanks-page helpers above do the same).
    from .views import _build_map_layers_metadata

    survey = request.survey
    section = get_object_or_404(SurveySection, survey_header=survey, name=section_name)

    selected_language = request.GET.get('lang')
    if selected_language and survey.available_languages and selected_language not in survey.available_languages:
        selected_language = None
    if not selected_language and survey.available_languages:
        selected_language = survey.available_languages[0]

    form = SurveySectionAnswerForm(
        initial={}, section=section, question=None,
        survey_session_id=None, language=selected_language,
    )

    subquestions_forms = {}
    for question in section.questions():
        subquestions_forms[question.code] = SurveySectionAnswerForm(
            initial={}, section=section, question=question,
            survey_session_id=None, language=selected_language,
        ).as_p()

    section_title = section.get_translated_title(selected_language)
    section_subheading = section.get_translated_subheading(selected_language)

    # Compute progress 1..N walking the linked list — same shape as
    # views.survey_section so the preview iframe reflects real section count.
    section_current = 1
    walker = section
    while walker.prev_section:
        walker = walker.prev_section
        section_current += 1
    section_total = section_current
    walker = section
    while walker.next_section:
        walker = walker.next_section
        section_total += 1

    if selected_language:
        translation.activate(selected_language)

    response = render(request, 'survey_section.html', {
        'form': form,
        'subquestions_forms': subquestions_forms,
        'survey': survey,
        'section': section,
        'section_title': section_title,
        'section_subheading': section_subheading,
        'selected_language': selected_language,
        'existing_geo_answers': {},
        'section_current': section_current,
        'section_total': section_total,
        'preview': True,
        'initial_map_lat': section.start_map_postion.y if section.start_map_postion else (survey.start_map_postion.y if survey.start_map_postion else 52.52),
        'initial_map_lng': section.start_map_postion.x if section.start_map_postion else (survey.start_map_postion.x if survey.start_map_postion else 13.405),
        'initial_map_zoom': section.start_map_zoom if section.start_map_zoom is not None else (survey.start_map_zoom if survey.start_map_zoom is not None else 12),
        'initial_use_geolocation': survey.use_geolocation,
        # Same helper the respondent view uses: two views render this shell from
        # two hand-built contexts, and a layer list built twice would drift.
        'map_layers': _build_map_layers_metadata(survey),
        'hidden_layers_json': json.dumps(
            [i for i in (section.hidden_layers or []) if isinstance(i, int)]
        ),
    })

    if selected_language:
        translation.deactivate()

    return response


# ─── Collaborator management ────────────────────────────────────────────────

@survey_permission_required('owner')
def editor_survey_collaborators(request, survey_uuid):
    """List collaborators for a survey (HTMX partial)."""
    survey = request.survey
    collaborators = SurveyCollaborator.objects.filter(survey=survey).select_related('user')
    # Org members who are not already collaborators (for the add form)
    existing_user_ids = collaborators.values_list('user_id', flat=True)
    available_members = Membership.objects.filter(
        organization=survey.organization,
    ).exclude(user_id__in=existing_user_ids).select_related('user')

    return render(request, 'editor/partials/collaborator_list.html', {
        'survey': survey,
        'collaborators': collaborators,
        'available_members': available_members,
        'survey_role_choices': [r[0] for r in SURVEY_ROLE_CHOICES],
    })


@survey_permission_required('owner')
@require_POST
def editor_collaborator_add(request, survey_uuid):
    """Add a collaborator to the survey."""
    survey = request.survey
    user_id = request.POST.get('user_id')
    role = request.POST.get('role', 'viewer')

    if role not in ('owner', 'editor', 'viewer'):
        return HttpResponse(status=400)

    # Verify user is a member of the org
    membership = Membership.objects.filter(
        organization=survey.organization, user_id=user_id,
    ).first()
    if not membership:
        return HttpResponse(status=400)

    SurveyCollaborator.objects.get_or_create(
        user_id=user_id, survey=survey,
        defaults={'role': role},
    )

    return _render_collaborator_list(request, survey)


@survey_permission_required('owner')
@require_POST
def editor_collaborator_change_role(request, survey_uuid, collaborator_id):
    """Change a collaborator's role."""
    survey = request.survey
    collab = get_object_or_404(SurveyCollaborator, id=collaborator_id, survey=survey)
    new_role = request.POST.get('role')

    if new_role not in ('owner', 'editor', 'viewer'):
        return HttpResponse(status=400)

    collab.role = new_role
    collab.save(update_fields=['role'])

    return _render_collaborator_list(request, survey)


@survey_permission_required('owner')
@require_POST
def editor_collaborator_remove(request, survey_uuid, collaborator_id):
    """Remove a collaborator. Cannot remove the last survey owner."""
    survey = request.survey
    collab = get_object_or_404(SurveyCollaborator, id=collaborator_id, survey=survey)

    # Prevent removing the last owner
    if collab.role == 'owner':
        owner_count = SurveyCollaborator.objects.filter(survey=survey, role='owner').count()
        if owner_count <= 1:
            return HttpResponse('Cannot remove the last survey owner', status=400)

    collab.delete()
    return _render_collaborator_list(request, survey)


def _render_collaborator_list(request, survey):
    """Helper to re-render the collaborator list partial."""
    collaborators = SurveyCollaborator.objects.filter(survey=survey).select_related('user')
    existing_user_ids = collaborators.values_list('user_id', flat=True)
    available_members = Membership.objects.filter(
        organization=survey.organization,
    ).exclude(user_id__in=existing_user_ids).select_related('user')

    return render(request, 'editor/partials/collaborator_list.html', {
        'survey': survey,
        'collaborators': collaborators,
        'available_members': available_members,
        'survey_role_choices': [r[0] for r in SURVEY_ROLE_CHOICES],
    })


# ─── Lifecycle transitions ──────────────────────────────────────────────────

@survey_permission_required('owner')
@require_POST
def editor_survey_transition(request, survey_uuid):
    """Transition survey to a new lifecycle status."""
    survey = request.survey
    new_status = request.POST.get('status', '')

    can, error = survey.can_transition_to(new_status)
    if not can:
        return HttpResponse(error, status=400)

    # Non-blocking translation-gap warning: publishing with holes is allowed,
    # but never silently — the respondent-side fallback would mask them. The
    # client confirms and retries with the acknowledgement flag.
    if new_status == 'published' and request.POST.get('ack_translation_gaps') != 'true':
        gaps = survey_translation_gaps(survey)
        if gaps:
            return JsonResponse({'translation_gaps': gaps}, status=409)

    # Test data cleanup on testing → published
    if survey.status == 'testing' and new_status == 'published':
        if request.POST.get('clear_test_data') == 'true':
            deleted_count, _ignored = SurveySession.objects.filter(survey=survey).delete()
            audit(request, 'clear_test_data', survey, deleted_sessions=deleted_count)

    audit(request, 'status_transition', survey, old_status=survey.status, new_status=new_status)
    survey.status = new_status

    # Sync is_archived flag
    if new_status == 'archived':
        survey.is_archived = True

    survey.save(update_fields=['status', 'is_archived'])

    # The real publish moment. Historical rows use survey creation as a proxy
    # (no transition timestamp existed before this), so from here the series
    # stops being approximate -- hence `timestamp_source` on every event, so a
    # "time to publish" insight can drop the reconstructed half rather than
    # average two different things.
    if new_status == 'published':
        pe.emit(pe.SURVEY_PUBLISHED, survey.created_by_id, {
            'survey_id': str(survey.id),
            'creation_method': pe.creation_method_for(survey.id),
        })
        # A failed scaffold must never block the publish itself — worst case
        # is today's behavior (no draft), and the config tab retries later.
        try:
            scaffold_page(survey)
        except Exception:
            logger.exception('public results scaffold failed for survey %s', survey.id)

    if request.headers.get('HX-Request'):
        return HttpResponse(status=204, headers={'HX-Trigger': 'statusChanged'})
    return redirect('editor_survey_detail', survey_uuid=survey.uuid)


@survey_permission_required('owner')
@require_POST
def editor_survey_visibility(request, survey_uuid):
    """Toggle public-gallery visibility from the publishing widget.

    Presentation-only helper: writes the single `visibility` field
    (public ↔ private). `demo` is left untouched if posted.
    """
    survey = request.survey
    value = request.POST.get('visibility')
    if value not in ('public', 'private', 'demo'):
        return HttpResponse('Invalid visibility', status=400)
    survey.visibility = value
    survey.save(update_fields=['visibility'])
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'visibility': survey.visibility})
    return redirect('editor_survey_detail', survey_uuid=survey.uuid)


@survey_permission_required('owner')
@require_POST
def editor_survey_password(request, survey_uuid):
    """Manage survey password and test token."""
    survey = request.survey
    action = request.POST.get('action', '')

    if action == 'set':
        password = request.POST.get('password', '')
        if len(password) < 4:
            return HttpResponse('Password must be at least 4 characters', status=400)
        survey.set_password(password)
        survey.save(update_fields=['password_hash'])
        audit(request, 'password_set', survey)

    elif action == 'remove':
        survey.clear_password()
        survey.save(update_fields=['password_hash'])
        audit(request, 'password_remove', survey)

    elif action == 'regenerate_token':
        survey.regenerate_test_token()
        survey.save(update_fields=['test_token'])
        audit(request, 'token_regenerate', survey)

    else:
        return HttpResponse('Invalid action', status=400)

    if request.headers.get('HX-Request'):
        return render(request, 'editor/partials/survey_password_modal.html', {
            'survey': survey,
        })
    return redirect('editor_survey_detail', survey_uuid=survey.uuid)


# ─── Versioning endpoints ──────────────────────────────────────────────────

@survey_permission_required('owner')
@require_POST
def editor_create_draft(request, survey_uuid):
    """Create a draft copy of a published survey for editing."""
    survey = request.survey

    # Closed as well as published: a closed survey is read-only for the same
    # reason and needs the same way out. Nothing downstream reads the canonical's
    # status — clone_survey_for_draft copies structure, and publish_draft archives
    # the previous version and leaves the status alone, so a closed survey stays
    # closed after its draft is published.
    if survey.status not in ('published', 'closed'):
        return HttpResponse('Only published or closed surveys can have draft copies', status=400)

    if survey.has_draft_copy():
        return HttpResponse('A draft already exists for this survey', status=409)

    draft = clone_survey_for_draft(survey)
    return redirect('editor_survey_detail', survey_uuid=draft.uuid)


@survey_permission_required('owner')
@require_POST
def editor_restore_version(request, survey_uuid):
    """Restore an archived version's questionnaire as a new draft copy.

    Append-only rollback: the draft clones the archived structure; publishing
    it creates a NEW version — no history is rewritten, no session moves.
    """
    survey = request.survey

    if survey.status != 'published':
        return HttpResponse('Only published surveys can restore a version', status=400)

    if survey.has_draft_copy():
        return HttpResponse('A draft already exists for this survey', status=409)

    version_param = request.POST.get('version', '')
    try:
        version_num = int(str(version_param).lstrip('v'))
    except (TypeError, ValueError):
        return HttpResponse('Invalid version', status=400)

    archived = get_object_or_404(
        SurveyHeader,
        canonical_survey=survey,
        is_canonical=False,
        version_number=version_num,
    )

    draft = clone_survey_for_draft(survey, structure_source=archived)
    return redirect('editor_survey_detail', survey_uuid=draft.uuid)


@survey_permission_required('owner')
@require_POST
def editor_publish_draft(request, survey_uuid):
    """Publish a draft copy as a new version of the canonical survey."""
    survey = request.survey

    if not survey.is_draft_copy:
        return HttpResponse('This survey is not a draft copy', status=400)

    force = request.POST.get('force') == 'true'

    # Same non-blocking translation-gap warning as the draft→published
    # transition: this path replaces the live version's content.
    if request.POST.get('ack_translation_gaps') != 'true':
        gaps = survey_translation_gaps(survey)
        if gaps:
            return JsonResponse({'translation_gaps': gaps}, status=409)

    try:
        canonical = publish_draft(survey, force=force)
    except IncompatibleDraftError as e:
        return JsonResponse({'issues': e.issues}, status=409)

    audit(request, 'draft_publish', canonical, draft_uuid=str(survey.uuid), version=canonical.version_number)
    return redirect('editor_survey_detail', survey_uuid=canonical.uuid)


@survey_permission_required('owner')
@require_POST
def editor_discard_draft(request, survey_uuid):
    """Discard a draft copy without affecting the canonical survey."""
    survey = request.survey

    if not survey.is_draft_copy:
        return HttpResponse('This survey is not a draft copy', status=400)

    canonical = survey.published_version
    audit(request, 'draft_discard', canonical, draft_uuid=str(survey.uuid))
    with transaction.atomic():
        # SurveySession.survey is PROTECT, so previewing a draft even once used
        # to make it undiscardable (ProtectedError → 500). publish_draft drops
        # the same test sessions; discard has no reason to keep them either.
        SurveySession.objects.filter(survey=survey).delete()
        survey.delete()
    return redirect('editor_survey_detail', survey_uuid=canonical.uuid)


@survey_permission_required('editor')
def editor_check_compatibility(request, survey_uuid):
    """Check backward compatibility of a draft against its canonical survey."""
    survey = request.survey

    if not survey.is_draft_copy:
        return JsonResponse({'error': 'Not a draft copy'}, status=400)

    issues = check_draft_compatibility(survey, survey.published_version)
    return JsonResponse({'issues': issues})
