import json
import logging
import os
import re
from urllib.parse import urlencode

from django.conf import settings
from django.template.loader import render_to_string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db import models
from django.db.models import Count
from django.http import HttpResponse, Http404, JsonResponse
from django.urls import reverse, NoReverseMatch
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required

from . import other_option
from .models import (
    SurveyHeader, SurveySection, Question, SurveyCollaborator, Answer,
    Membership, SURVEY_ROLE_CHOICES, BASEMAP_CHOICES,
    INPUT_TYPE_CHOICES, SurveyMapLayer,
    CreatorPreferences,
    SURVEY_START_AI, SURVEY_START_CHOICES,
)
from . import map_start
from .layers import (
    normalize_style, legend_for, LAYER_ICONS,
    validate_layer_upload, LayerValidationError, layers_for, layer_owner, GEOMETRY_TEXT_FIELDS,
    objects_from_features, rebuild_layer, MAX_LAYER_BYTES, MAX_LAYERS_PER_SURVEY,
)
from . import product_events as pe
from .question_types import SHARED_MAP_SOURCE_TYPES, allowed_display_styles, normalise_choice_extras
from .cloning import clone_question, clone_section
from .groups import (
    group_from_request, max_order as group_max_order, shift_down as group_shift_down,
)
from .html_sanitize import coerce_creator_html
from .content_screening import pending_review_for
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
from .comments import open_counts as _thread_counts
from .permissions import (
    org_permission_required, survey_permission_required,
    get_effective_survey_role,
)
from .versioning import (
    check_draft_compatibility, is_live, live_editing_enabled, structural_edit_message,
)
from .audit import audit
from .services import common as svc_common
from .services import locks as svc_locks
from .services import publishing as svc_publishing
from .services import questions as svc_questions
from .services import sections as svc_sections
from .services import surveys as svc_surveys
from .services.context import Actor
from .services.errors import (
    AnswersAtRisk, Conflict, DeleteBlocked, IncompatibleDraft, ServiceError, StructureLocked,
    TransitionRefused, TranslationGaps, ValidationFailed,
)

logger = logging.getLogger(__name__)


# Moved to the service layer (change rest-api-v1); kept importable under the
# names the tests and sibling modules grew up with.
_guard_choice_codes = svc_questions.guard_choice_codes


def _locked_response(err):
    """The editor's answer to a lock raised by the service layer: the same
    403 text it has always returned."""
    return HttpResponse(err.message, status=403)


def _check_structural_edit_allowed(survey):
    """Return HttpResponse(403) if survey is read-only, else None.

    Structural edits (add/delete/reorder/paste) never apply to a live survey:
    with LIVE_SURVEY_EDITING they go to the unpublished changes instead, which
    the editor offers before the request is ever sent.
    """
    try:
        svc_locks.assert_structure_editable(survey)
    except ServiceError as err:
        return _locked_response(err)
    return None


def _edit_locks(survey):
    """(is_read_only, structure_locked) for an editor page of `survey`;
    the rule lives in services.locks.locks()."""
    return svc_locks.locks(survey)


def _lock_context(survey):
    is_read_only, structure_locked = _edit_locks(survey)
    return {'is_read_only': is_read_only, 'structure_locked': structure_locked}


def _check_content_edit_allowed(survey):
    """403 unless safe (non-structural) edits may be saved to `survey` now."""
    try:
        svc_locks.assert_content_editable(survey)
    except ServiceError as err:
        return _locked_response(err)
    return None


def _check_not_shadowed_by_draft(survey):
    """403 when the live survey's settings are about to be replaced anyway
    (services.locks.assert_settings_editable)."""
    try:
        svc_locks.assert_settings_editable(survey)
    except ServiceError as err:
        return _locked_response(err)
    return None


def _structural_refusal(request, reasons, render_modal=None):
    """The answer to a structural change attempted on a live survey."""
    message = structural_edit_message(reasons)
    if request.POST.get('autosave') or render_modal is None:
        return JsonResponse(
            {'ok': False, 'needs_unpublished_changes': True, 'errors': {'__all__': [message]}},
            status=422)
    return render_modal(message)


# Sent by the editor once the author has seen how many answers a delete costs.
DELETE_ACKNOWLEDGEMENT = 'confirm_delete_answers'


def _survey_is_unversioned(survey):
    """True when this survey has no archived versions to fall back on
    (services.common.survey_is_unversioned)."""
    return svc_common.survey_is_unversioned(survey)


def _answers_at_risk_response(err):
    return JsonResponse(
        {'answers_at_risk': err.count, 'explain_versioning': err.explain_versioning},
        status=409,
    )


def _refuse_if_answers_at_risk(request, survey, answer_count):
    """Return a 409 unless the author has acknowledged losing `answer_count` answers."""
    try:
        svc_common.guard_answer_loss(
            survey, answer_count, request.POST.get(DELETE_ACKNOWLEDGEMENT) == 'true')
    except AnswersAtRisk as err:
        return _answers_at_risk_response(err)
    return None


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
    'not_configured': "The Wizard isn't available right now — create an empty survey instead.",
    'provider_error': "The Wizard couldn't be reached. Try again, or create an empty survey.",
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
            survey.use_geolocation = request.POST.get('use_geolocation') == '1'
            # Default base map (all basemaps stay enabled via the model default)
            valid_basemaps = {slug for slug, _ in BASEMAP_CHOICES}
            chosen_basemap = request.POST.get('default_basemap')
            if chosen_basemap in valid_basemaps:
                survey.default_basemap = chosen_basemap
            # The hidden fields hold the picker's centre, which is the server's
            # suggestion unless the creator framed the map (`map_touched`), the
            # one case the always-filled lat/lng cannot tell apart on its own.
            posted = map_start.browser_position(request.POST)
            if posted:
                start = map_start.StartPosition(*posted, _posted_map_source(request))
            else:
                # A POST without the map fields (old scripts, the legacy test
                # shape): the chain decides, exactly as the blank endpoint does.
                start = map_start.suggest_start_position(request)
            return _finish_blank_survey(
                request, survey, start=start, surface=pe.SURFACE_CREATE_PAGE,
            )
    else:
        form = SurveyCreateForm()
    if settings.CREATE_STEER_AI and settings.MOBILE_EDITOR_NAV:
        # Single-field brief: the goal is the whole visible brief, so it takes
        # focus. Only when the wizard flag hides the name field — with the flat
        # layout the name input keeps first position and focus stays contested.
        brief_form.fields['goal'].widget.attrs['autofocus'] = True
    # Where the picker opens before anyone touches it: the chain, never a
    # fixed city. The AI path inherits it through the same hidden fields.
    start = map_start.suggest_start_position(request)
    return render(request, 'editor/survey_create.html', {
        'form': form,
        'brief_form': brief_form,
        'ai_available': ai_client.provider_configured(),
        'initial_start': start,
        'from_start_page': request.GET.get('from') == 'start',
    })


def _posted_map_source(request):
    """`map_source` for a create-page POST: who put the centre where it is."""
    if request.POST.get('map_touched') == '1':
        return pe.MAP_SOURCE_CREATOR
    source = request.POST.get('map_source', '')
    return source if source in map_start.SOURCES else map_start.SOURCE_BROWSER


def _finish_blank_survey(request, survey, *, start, surface):
    """Save an unsaved `SurveyHeader` as a new survey and open its editor.

    The one place that turns a header into a survey a creator can work on --
    the owner collaborator, the head section, `survey_created` -- shared by
    the create page's manual action and the one-click blank endpoint so the
    two cannot drift (change first-survey-onboarding, D4).
    """
    svc_surveys.create(Actor.from_request(request), survey, request.active_org, start=start, surface=surface)
    return redirect('editor_survey_detail', survey_uuid=survey.uuid)


def _creator_survey_language():
    """The survey language a blank survey starts in: the creator's interface
    language when the product can run a survey in it, else English."""
    code = (translation.get_language() or 'en').split('-')[0]
    return code if code in dict(settings.LANGUAGES) else 'en'


def _survey_start_labels():
    """Creator-facing names of the start defaults. The AI path is the "Survey
    wizard" on every creator surface (start page, Preferences); the model's
    choice labels stay as they are so the rename needs no migration."""
    labels = dict(SURVEY_START_CHOICES)
    labels[SURVEY_START_AI] = _('Survey wizard')
    return labels


def _set_survey_start_default(user, value):
    CreatorPreferences.objects.update_or_create(
        user=user, defaults={'survey_start_default': value},
    )


@require_POST
@org_permission_required('editor')
def editor_survey_create_blank(request):
    """"Start from scratch" in one request: no create page, straight to the editor.

    POST, never GET -- a link a browser prefetches or a crawler follows must
    not create surveys. Name, languages and map are all editable in place in
    the editor, which is why the create page's form is not on this path.
    """
    language = _creator_survey_language()
    survey = SurveyHeader(
        name=_('Untitled survey'),
        available_languages=[language],
    )
    start = map_start.suggest_start_position(
        request, browser=map_start.browser_position(request.POST),
    )
    return _finish_blank_survey(
        request, survey, start=start, surface=pe.SURFACE_START_BLANK,
    )


@require_GET
@org_permission_required('editor')
def editor_survey_start(request):
    """The three ways to begin (changes first-survey-onboarding, start-cards-one-click).

    GET only: every card acts on one click by itself -- the blank card posts to
    `editor_survey_create_blank`, the AI card links to the create page. The
    remembered default is shown here but set on the Preferences page.
    """
    current = (CreatorPreferences.objects
               .filter(user=request.user)
               .values_list('survey_start_default', flat=True)
               .first()) or ''
    return render(request, 'editor/survey_start.html', {
        'ai_available': ai_client.provider_configured(),
        'welcome': request.GET.get('welcome') == '1',
        'current_default': current,
        'current_default_label': _survey_start_labels().get(current, ''),
    })


@login_required
def editor_account_preferences(request):
    """Settings that belong to the person, not the workspace (change start-cards-one-click).

    First and only setting so far: where "+ New Survey" leads
    (`CreatorPreferences.survey_start_default`). No org role is needed -- the
    choice is the creator's own, whatever their role in the active workspace.
    """
    if request.method == 'POST':
        value = request.POST.get('survey_start_default', '')
        if value not in dict(SURVEY_START_CHOICES):
            return HttpResponse(status=400)
        _set_survey_start_default(request.user, value)
        messages.success(request, _('Preferences saved.'))
        return redirect('editor_account_preferences')
    current = (CreatorPreferences.objects
               .filter(user=request.user)
               .values_list('survey_start_default', flat=True)
               .first()) or ''
    ai_available = ai_client.provider_configured()
    labels = _survey_start_labels()
    start_options = [{
        'value': value,
        'label': labels[value],
        'checked': value == current,
        # Shown, but not offered, when this server has no AI; a stored "ai"
        # stays checked and enabled so a save keeps it.
        'unavailable': value == SURVEY_START_AI and not ai_available,
    } for value, _label in SURVEY_START_CHOICES]
    return render(request, 'editor/account_preferences.html', {
        'start_options': start_options,
    })


@login_required
def editor_account_mcp(request):
    """The agent-access teaser, now a redirect (change auth-core, #379).

    The page body -- tokens, connected apps, the MCP interest block with its
    "Tell me when it's ready" button -- lives on `editor_account_connections`
    (`api/views.py`). The URL and its name stay: `docs/mcp.md`, the help
    pages and old bookmarks point here.
    """
    return redirect('editor_account_connections')


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
        # Two shapes of the same errors: the flat list keeps the card readable
        # without JS, `field_errors` lets the page mark each offending input in
        # place (the card is then hidden client-side when nothing is left
        # unanchored — errors belong next to their source, not below the fold).
        errors = []
        field_errors = []
        unanchored_count = 0
        for field_form in (form, brief_form):
            for field_name, messages in field_form.errors.items():
                if field_name in field_form.fields:
                    label = field_form.fields[field_name].label or field_name.replace('_', ' ')
                    errors.extend('%s: %s' % (label, message) for message in messages)
                    field_errors.append({
                        'field_id': field_form[field_name].auto_id,
                        'messages': [str(message) for message in messages],
                    })
                else:
                    errors.extend(str(message) for message in messages)
                    unanchored_count += len(messages)
        return render(request, 'editor/partials/generation_invalid.html', {
            'message': 'Check the form before generating a draft.',
            'errors': errors,
            'field_errors': field_errors,
            'unanchored_count': unanchored_count,
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
    # Set by the create page only on the creator's own gestures — never by the
    # geolocation jump or the brief prefill — so the server can tell "framed
    # it" from "left the default", which the always-filled lat/lng cannot.
    map_locked = request.POST.get('map_touched') == '1'
    generate_survey_draft_task.delay(
        event.id, brief.as_dict(), languages, header_overrides,
        map_locked=map_locked, map_source=_posted_map_source(request),
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

def _draft_url_for(request, survey, draft, then=None, section_code=None):
    """The draft's Build URL, on the section that matches the one in hand.

    Sections are matched by code (clone_survey_for_draft keeps codes), so the
    creator lands where they were on the live survey.
    """
    params = {}
    panel = request.GET.get('panel')
    if panel in ('settings', 'thanks'):
        params['panel'] = panel
    code = section_code
    if code is None:
        section_id = _int_param(request.GET.get('section'))
        if section_id:
            code = (SurveySection.objects.filter(id=section_id, survey_header=survey)
                    .values_list('code', flat=True).first())
    if code:
        target = (SurveySection.objects.filter(survey_header=draft, code=code)
                  .values_list('id', flat=True).first())
        if target:
            params['section'] = target
    if then:
        params['then'] = then
    url = reverse('editor_survey_detail', kwargs={'survey_uuid': draft.uuid})
    return url + ('?' + urlencode(params) if params else '')


@survey_permission_required('viewer')
def editor_survey_detail(request, survey_uuid):
    survey = request.survey

    # One editing surface per survey (change edit-live-survey): while a live
    # survey has unpublished changes, Build opens them. `?live=1` still shows
    # the live survey itself, read-only.
    if (live_editing_enabled() and is_live(survey)
            and request.effective_survey_role in ('editor', 'owner')
            and request.GET.get('live') != '1'):
        draft = survey.get_draft_copy()
        if draft is not None:
            return redirect(_draft_url_for(request, survey, draft))

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
    is_read_only, structure_locked = _edit_locks(survey)
    is_live_survey = is_live(survey)
    if is_live_survey and not can_edit:
        # A viewer edits nothing: the live survey reads as read-only to them.
        is_read_only = True
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
        is_owner and is_live_survey and survey.has_never_collected()
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

    # Uncovered-option lint: options of a fanned-out controller that show no
    # section. Human-readable hints; the underlying data comes from the same
    # module the runtime fails open on.
    visibility_lint_hints = []
    if getattr(settings, 'CONDITIONAL_VISIBILITY', False):
        from .visibility import lint_rules
        lint = lint_rules(survey)
        controllers = {q.id: q for s in sections for q in s.questions()}
        for controller_id, missing in lint['uncovered'].items():
            controller = controllers.get(controller_id)
            if controller is None:
                continue
            names = ', '.join(f'“{controller.get_choice_name(c)}”' for c in missing)
            visibility_lint_hints.append(
                f'Answer{"s" if len(missing) > 1 else ""} {names} of '
                f'“{controller.name or controller.code}” do'
                f'{"" if len(missing) > 1 else "es"} not show any section.'
            )

    return render(request, 'editor/survey_detail.html', {
        'pending_review': pending_review_for(survey) if survey.status == 'published' else None,
        'thread_counts': _thread_counts(survey, request.user),
        'visibility_lint_hints': visibility_lint_hints,
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
        'structure_locked': structure_locked,
        'is_live_survey': is_live_survey,
        'live_editing': live_editing_enabled(),
        'then_action': request.GET.get('then', '') if survey.is_draft_copy else '',
        'is_owner': is_owner,
        'draft_copy': draft_copy,
        'show_edit_published': show_edit_published,
        'show_draft_actions': show_draft_actions,
        'show_back_to_draft': show_back_to_draft,
    })


# ─── Survey settings ─────────────────────────────────────────────────────────

def _rescreen_if_live(survey):
    """`redirect_url` and `thanks_html` stay editable on a published survey —
    the one way to put a lure on a live page after a clean publish."""
    svc_locks.rescreen_if_live(survey)


@survey_permission_required('owner')
def editor_survey_settings(request, survey_uuid):
    survey = request.survey
    if request.method == 'POST':
        blocked = _check_not_shadowed_by_draft(survey)
        if blocked:
            return blocked
        try:
            svc_surveys.update_settings(Actor.from_request(request), survey, request.POST, request.FILES)
        except ValidationFailed as err:
            form = err.form
        else:
            return redirect('editor_survey_settings', survey_uuid=survey.uuid)
    else:
        form = SurveyHeaderForm(instance=survey)
    return render(request, 'editor/survey_settings.html', {
        'survey': survey,
        'form': form,
        'effective_role': request.effective_survey_role,
        'basemap_choices': BASEMAP_CHOICES,
        'map_layers': _editor_layers(survey),
        'layer_icons': LAYER_ICONS,
        'layers_enabled': settings.MAP_REFERENCE_LAYERS,
    })


@require_POST
@survey_permission_required('owner')
def editor_survey_rename(request, survey_uuid):
    """Rename a survey from the editor header. Writes the name and nothing else.

    Owner-gated, matching ``editor_survey_settings`` — the header is a second
    door onto the same field, not a lower bar for reaching it. A draft copy has
    no name of its own to change; its header names the published survey.
    """
    survey = request.survey
    try:
        svc_surveys.rename(Actor.from_request(request), survey, request.POST)
    except Conflict:
        return JsonResponse(
            {'ok': False, 'errors': {'name': [str(_('A draft is renamed by renaming the published survey.'))]}},
            status=400,
        )
    except ValidationFailed as err:
        return JsonResponse({'ok': False, 'errors': err.form.errors}, status=400)
    return JsonResponse({'ok': True, 'name': survey.name})


@survey_permission_required('owner')
def editor_survey_settings_panel(request, survey_uuid):
    """Same settings as editor_survey_settings, rendered as an HTMX-swappable
    partial for the pinned "Survey settings" entry in the editor sidebar. The
    general fields autosave (mirrors public_results_editor.py's pattern); Map
    Position / Collaborators / Password keep their own dedicated controls.
    """
    survey = request.survey
    shadowed = _check_not_shadowed_by_draft(survey)
    if request.method == 'POST':
        if shadowed:
            return shadowed
        try:
            svc_surveys.update_settings(Actor.from_request(request), survey, request.POST, request.FILES)
        except ValidationFailed as err:
            form = err.form
            if _is_ajax(request):
                return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        else:
            if _is_ajax(request):
                return JsonResponse({'ok': True})
            from django.urls import reverse
            return redirect('{}?panel=settings'.format(reverse('editor_survey_detail', args=[survey.uuid])))
    else:
        form = SurveyHeaderForm(instance=survey)
    return render(request, 'editor/partials/survey_settings_panel.html', {
        'survey': survey,
        'form': form,
        'shadowed_by_draft': survey.get_draft_copy() if shadowed else None,
        'effective_role': request.effective_survey_role,
        'basemap_choices': BASEMAP_CHOICES,
        'map_layers': _editor_layers(survey),
        'layer_icons': LAYER_ICONS,
        'layers_enabled': settings.MAP_REFERENCE_LAYERS,
    })


@survey_permission_required('editor')
def editor_survey_thanks_panel(request, survey_uuid):
    """WYSIWYG editor for the survey's thanks page, as an HTMX-swappable partial
    for the pinned "Thanks page" entry (the last Build step). Per-language HTML
    is sanitized on save and stored in SurveyHeader.thanks_html; autosaves.
    """
    survey = request.survey
    langs = list(survey.available_languages) or ['en']
    results_page = getattr(survey, 'public_results_page', None)

    if request.method == 'POST':
        blocked = _check_not_shadowed_by_draft(survey)
        if blocked:
            return blocked
        # The "See the results" toggle lives on the results page; save it here
        # too. A hidden marker tells us the checkbox was actually in the
        # submitted form (an unchecked box sends nothing), so a stale form
        # can't clobber it.
        show = None
        if request.POST.get('has_results_toggle') == '1':
            show = request.POST.get('show_on_thanks') == 'on'
        svc_surveys.set_thanks(
            Actor.from_request(request), survey,
            {lang: request.POST.get('thanks_{}'.format(lang), '') for lang in langs},
            show_on_thanks=show)
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

def _source_layers_of(survey, question):
    """Names of the `question` layers reading this geo question — the form
    says so, since deleting the question is refused while they exist."""
    if not settings.MAP_REFERENCE_LAYERS or question.input_type not in SHARED_MAP_SOURCE_TYPES \
            or question.parent_question_id_id is not None:
        return []
    from .layers import question_layers_for
    return list(question_layers_for(survey, question.code).values_list('name', flat=True))


_geo_questions = svc_questions.geo_questions
_label_options = svc_questions.label_options


def _editor_layers(survey):
    """Layers with their property names, for the settings card's field pickers."""
    if not settings.MAP_REFERENCE_LAYERS:
        return []
    from .layers import source_question_for
    items = []
    for layer in layers_for(survey):
        item = {'layer': layer, 'properties': _layer_property_names(layer),
                'style': normalize_style(layer.style, layer.color),
                'geojson_url': reverse('survey_layer_geojson', kwargs={'survey_slug': str(survey.uuid), 'layer_id': layer.pk})}
        if layer.source == 'question':
            item['source_question'] = source_question_for(layer)
            item['used_by'] = list(layer.questions.values_list('name', flat=True))
        # Where the layer is on a map: the sections whose Objects questions
        # bind it (spec survey-editor "Layers are put on a map by adding a
        # question"). Draft copies and versions carry their own question rows;
        # the card lists the canonical survey's sections.
        item['shown_in'] = list(dict.fromkeys(
            layer.questions.filter(survey_section__survey_header=survey, parent_question_id__isnull=True)
            .order_by('survey_section__id')
            .values_list('survey_section__title', flat=True)))
        items.append(item)
    return items


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
        'source': layer.source,
        'source_question_code': layer.source_question_code,
        'show_tallies': layer.show_tallies,
        'show_comments': layer.show_comments,
        'approve_first': layer.approve_first,
        'style': normalize_style(layer.style, layer.color),
        'legend': legend_for(layer),
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
    if layer_owner(survey).map_layers.count() >= MAX_LAYERS_PER_SURVEY:
        return JsonResponse({'error': f'A survey can hold {MAX_LAYERS_PER_SURVEY} reference layers.'}, status=400)
    if f.size > MAX_LAYER_BYTES:
        return JsonResponse({'error': f'File is larger than {MAX_LAYER_BYTES // (1024 * 1024)} MB.'}, status=400)
    try:
        features, _properties, _dropped_z = validate_layer_upload(f.read())
    except LayerValidationError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    name = (os.path.splitext(f.name)[0] or 'Layer')[:100]
    owner = layer_owner(survey)
    position = (owner.map_layers.aggregate(m=models.Max('position'))['m'] or 0) + 1
    # The row is created before its objects exist, so anything that raises while
    # building them used to leave an empty layer behind, counting against
    # MAX_LAYERS_PER_SURVEY until the creator spotted it in the settings card and
    # deleted it by hand. One such orphan reached production before this was atomic.
    with transaction.atomic():
        # The layer is created on the OWNER (canonical) survey: a draft copy borrows
        # its layers rather than holding copies (see survey.layers.layer_owner).
        layer = SurveyMapLayer.objects.create(
            survey=owner, name=name, geojson='', position=position,
        )
        # The file becomes objects; the layer's geojson is derived from them.
        objects_from_features(layer, features, sanitize=coerce_creator_html)
        rebuild_layer(layer)
    return JsonResponse(_layer_payload(layer, layer.property_names), status=201)


@survey_permission_required('owner')
@require_POST
def editor_survey_layer_update(request, survey_uuid, layer_id):
    """Update a layer's presentation config (never its geometry)."""
    _layers_enabled_or_404()
    layer = get_object_or_404(SurveyMapLayer.objects.defer(*GEOMETRY_TEXT_FIELDS), pk=layer_id, survey=layer_owner(request.survey))
    style_error = _apply_style(request, layer)
    if style_error:
        return style_error
    if layer.source == 'question':
        return _update_question_layer(request, layer)

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


def _apply_style(request, layer):
    """`style` (JSON) on the layer update endpoint — normalised, never stored
    raw (spec layer-style). A `question` layer keeps the base only: its
    objects carry no properties to rule on. Returns an error response or None."""
    if 'style' not in request.POST:
        return None
    from .layers import normalize_style as _normalize
    try:
        raw = json.loads(request.POST.get('style') or '{}')
    except ValueError:
        return JsonResponse({'error': 'Style must be JSON.'}, status=400)
    try:
        color = (request.POST.get('color') or '').strip() or layer.color
        style = _normalize(raw, color if re.match(r'^#[0-9a-fA-F]{6}$', color) else layer.color)
    except LayerValidationError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    if layer.source == 'question':
        style['by'] = None
    layer.style = style
    return None


@survey_permission_required('owner')
def editor_survey_layer_style_summary(request, survey_uuid, layer_id):
    """Distinct values / numeric range of one object property — what the
    card's Auto-fill builds classes from (spec layer-style)."""
    _layers_enabled_or_404()
    layer = get_object_or_404(SurveyMapLayer.objects.defer(*GEOMETRY_TEXT_FIELDS), pk=layer_id, survey=layer_owner(request.survey))
    if layer.source == 'question':
        raise Http404
    from .layers import style_summary
    field = (request.GET.get('field') or '').strip()[:100]
    if not field:
        return JsonResponse({'error': 'field is required'}, status=400)
    return JsonResponse(style_summary(layer, field))


def _update_question_layer(request, layer):
    """The `question`-layer edit state on the settings card: name and color.
    Key field / popups have no meaning here."""
    name = (request.POST.get('name') or '').strip()
    if name:
        layer.name = name[:100]
    color = (request.POST.get('color') or '').strip()
    if color:
        if not re.match(r'^#[0-9a-fA-F]{6}$', color):
            return JsonResponse({'error': 'Color must be #RRGGBB.'}, status=400)
        layer.color = color
    # Label and the visibility switches are edited on the Objects-on-the-map
    # question bound to this layer — one door (owner decision 2026-09-05).
    layer.save()
    return JsonResponse(_layer_payload(layer, []))


@survey_permission_required('owner')
@require_POST
def editor_survey_layer_delete(request, survey_uuid, layer_id):
    _layers_enabled_or_404()
    layer = get_object_or_404(SurveyMapLayer.objects.defer(*GEOMETRY_TEXT_FIELDS), pk=layer_id, survey=layer_owner(request.survey))
    # Question.layer is PROTECT: answers about the layer's objects would be
    # orphaned. Say which question holds the binding instead of a 500.
    bound = list(layer.questions.values_list('name', flat=True))
    if bound:
        names = ', '.join(f'“{n}”' for n in bound if n) or 'a question'
        return JsonResponse({'error': f'This layer is used by {names}. Change that question\'s layer or delete it first.'}, status=400)
    layer.delete()
    return HttpResponse(status=204)


def _layer_property_names(layer):
    """Property names of a stored layer, for the field pickers. Stored on the
    layer by `rebuild_layer` (change layer-memory-diet): parsing the derived
    GeoJSON for this cost 55 MB per editor page render on a 10 MB layer."""
    return list(layer.property_names or [])


# ─── Survey map position ─────────────────────────────────────────────────────

@survey_permission_required('owner')
@require_POST
def editor_survey_map_position(request, survey_uuid):
    survey = request.survey
    blocked = _check_not_shadowed_by_draft(survey)
    if blocked:
        return blocked
    try:
        svc_surveys.set_map_position(
            Actor.from_request(request), survey,
            lat=request.POST.get('lat'), lng=request.POST.get('lng'), zoom=request.POST.get('zoom'),
            clear_position=request.POST.get('clear_position', '0') == '1',
            use_geolocation=request.POST.get('use_geolocation', '0') == '1')
    except ValidationFailed as err:
        return HttpResponse(err.message, status=400)
    return HttpResponse(status=204)


# ─── Section CRUD ─────────────────────────────────────────────────────────────

@survey_permission_required('editor')
@require_POST
def editor_section_create(request, survey_uuid):
    survey = request.survey
    try:
        section = svc_sections.create(Actor.from_request(request), survey)
    except ServiceError as err:
        return _locked_response(err)
    return render(request, 'editor/partials/section_list_item.html', {'thread_counts': _thread_counts(survey, request.user), 
        'section': section,
        'survey': survey,
        'is_current': False,
    })


def _parse_visibility_rule(request):
    """Read the Visibility block's POST fields (rules in
    services.common.parse_visibility).

    Returns (present, rule_or_None, error_or_None). ``present`` False = the
    block wasn't posted (kill switch off, stale form) — leave the stored rule
    untouched.
    """
    try:
        present, rule = svc_common.parse_visibility(
            request.POST.get('visibility_mode'),
            request.POST.get('visibility_question', ''),
            request.POST.get('visibility_match', 'any_of'),
            request.POST.getlist('visibility_choices'),
        )
    except ValidationFailed as err:
        return True, None, err.message
    return present, rule, None


def _visibility_block_context(survey, host_section, host_kind, host=None, parent=None):
    """Context for editor/partials/_visibility_block.html.

    ``host_kind='subquestion'``: the host lives in ``parent``'s pop-up and may
    depend on an earlier choice sibling only (spec conditional-visibility,
    sub-questions) — one group, "This pop-up", instead of the section groups.
    """
    if not getattr(settings, 'CONDITIONAL_VISIBILITY', False):
        return {'visibility_enabled': False}
    from .visibility import controller_options, popup_controller_options, rule_mode
    if host_kind == 'subquestion' or (host_kind == 'group' and parent is not None):
        from types import SimpleNamespace
        eligible = popup_controller_options(parent, host=host)
        groups = [(SimpleNamespace(title=_('This pop-up'), name=''), eligible)] if eligible else []
    else:
        groups = controller_options(
            survey, host_section, host_kind,
            host_question=host if host_kind in ('question', 'group') else None,
        )
    rule = getattr(host, 'visibility_rule', None) if host is not None else None
    rule = rule if isinstance(rule, dict) else None
    return {
        'visibility_enabled': True,
        'visibility_groups': groups,
        'visibility_rule': rule,
        'visibility_rule_codes': (rule or {}).get('choice_codes', []),
        'visibility_rule_question': (rule or {}).get('question_code'),
        'visibility_rule_match': rule_mode(rule) if rule else 'any_of',
        'visibility_popup': host_kind == 'subquestion' or (host_kind == 'group' and parent is not None),
    }


def _question_visibility_context(survey, question):
    """Visibility block context for an existing question — a top-level one
    against the section order, a sub-question against its pop-up."""
    if question.parent_question_id_id is not None:
        return _visibility_block_context(
            survey, question.survey_section, 'subquestion',
            host=question, parent=question.parent_question_id)
    return _visibility_block_context(survey, question.survey_section, 'question', host=question)


@survey_permission_required('editor')
def editor_section_detail(request, survey_uuid, section_id):
    survey = request.survey
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)

    _, structure_locked = _edit_locks(survey)
    if request.method == 'POST':
        blocked = _check_content_edit_allowed(survey)
        if blocked:
            return blocked
        vis_present, vis_rule, vis_error = _parse_visibility_rule(request)
        try:
            # A half-filled Visibility block never costs the creator the rest of
            # an autosave: the fields are saved, the rule is reported (422).
            svc_sections.update(
                Actor.from_request(request), section, request.POST,
                translations=svc_common.UNSET if vis_error else svc_common.translations_from_post(
                    request.POST, survey, svc_sections.TRANSLATION_FIELDS),
                visibility_rule=vis_rule if (vis_present and not vis_error) else svc_common.UNSET,
            )
        except ValidationFailed as err:
            return _render_section_detail(request, survey, section, err.form)
        except StructureLocked as err:
            if err.reasons:
                return _structural_refusal(request, err.reasons)
            return _locked_response(err)
        except ServiceError as err:
            return _locked_response(err)
        if vis_error:
            return JsonResponse({'ok': False, 'errors': {'visibility': [vis_error]}}, status=422)
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Trigger': 'sectionSaved'})
        return redirect('editor_survey_detail', survey_uuid=survey.uuid)
    else:
        form = SurveySectionForm(instance=section, lock_structure=structure_locked)
    return _render_section_detail(request, survey, section, form)


def _render_section_detail(request, survey, section, form=None):
    """The section panel (settings + question list) as editor_section_detail
    GET renders it. Group endpoints answer with it: a group change can move
    several rows at once, and re-rendering the list is what keeps the nested
    Sortable containers right (change question-groups)."""
    if form is None:
        form = SurveySectionForm(instance=section, lock_structure=_edit_locks(survey)[1])
    translations = {t.language: t for t in section.translations.all()}
    questions = list(
        Question.objects.filter(
            survey_section=section,
            parent_question_id__isnull=True,
        ).order_by('order_number')
    )

    return render(request, 'editor/partials/section_detail_form.html', {
        **_visibility_block_context(survey, section, 'section', host=section),
        'thread_counts': _thread_counts(survey, request.user),
        'survey': survey,
        'section': section,
        'form': form,
        'translations': translations,
        'questions': questions,
        **_lock_context(survey),
        'layers_enabled': settings.MAP_REFERENCE_LAYERS,
    })


def _translation_languages(survey):
    """Languages that carry translation rows (services.common.translation_languages)."""
    return svc_common.translation_languages(survey)


def _save_section_translations(request, section, survey):
    """Save section translations from POST data (non-primary languages only)."""
    svc_sections.save_translations_for(
        section, survey,
        svc_common.translations_from_post(request.POST, survey, svc_sections.TRANSLATION_FIELDS))


@survey_permission_required('editor')
@require_POST
def editor_section_delete(request, survey_uuid, section_id):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)
    try:
        svc_sections.delete(
            Actor.from_request(request), section,
            acknowledge_answer_loss=request.POST.get(DELETE_ACKNOWLEDGEMENT) == 'true')
    except AnswersAtRisk as err:
        return _answers_at_risk_response(err)
    except ServiceError as err:
        return _locked_response(err)
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
        except (json.JSONDecodeError, ValueError, AttributeError):
            return HttpResponse(status=400)

    try:
        svc_sections.reorder(Actor.from_request(request), survey, section_ids)
    except ValidationFailed:
        return HttpResponse(status=400)
    except ServiceError as err:
        return _locked_response(err)
    return HttpResponse(status=204)


# ─── Question CRUD ────────────────────────────────────────────────────────────

def _shared_map_layer_options(survey):
    """What the Objects-on-the-map layer picker offers (spec survey-editor
    "Objects on the map source picker"): the survey's layers, then the geo
    questions whose answers may become a layer — picking one of those creates
    the `question` layer on save. One geo question ⇒ one layer, so a question
    that already has its layer is listed under the layer, not twice."""
    if not settings.MAP_REFERENCE_LAYERS:
        return [], []
    from .layers import source_question_for, default_question_name
    layers, taken = [], set()
    for layer in layers_for(survey):
        entry = {'id': layer.pk, 'name': layer.name, 'source': layer.source, 'code': layer.source_question_code,
                 'label_field': layer.label_field, 'approve_first': layer.approve_first, 'labels': [],
                 'default_name': default_question_name(layer)}
        if layer.source == 'question':
            entry['labels'] = _label_options(source_question_for(layer))
            taken.add(layer.source_question_code)
        layers.append(entry)
    sources = [{'code': q.code, 'name': q.name, 'labels': _label_options(q)}
               for q in _geo_questions(survey) if q.code not in taken]
    return layers, sources


QUICK_LABELS = (('thumbs', '👍/👎'), ('rating', 'Rating'), ('comment', 'Comment'))


def _render_question_modal(request, context):
    """Render the question modal so HTMX always swaps it into the modal body.

    The <form> inside the modal targets the question LIST for its success
    response (a list item), so a validation re-render of the modal returned
    as a plain 200 would be appended to / swapped over that list — the modal
    stays open with the error out of sight and every retry adds a copy
    (PostHog replay 01a051a7, openspec: fix-question-modal-error-retarget).
    HX-Retarget/HX-Reswap point the swap back at #questionModalBody.
    """
    context = {**context, 'QUICK_LABELS': QUICK_LABELS}
    survey = context.get('survey')
    if survey is not None:
        # The in-modal sub-question list renders the same disabled state as
        # the section list does on published/closed surveys.
        for key, value in _lock_context(survey).items():
            context.setdefault(key, value)
        context.setdefault('thread_counts', _thread_counts(survey, request.user))
        if 'layer_options' not in context:
            context['layer_options'], context['answer_sources'] = _shared_map_layer_options(survey)
    # A create opened from "+ Add question" inside a group keeps the group on
    # every post the modal makes (change question-groups).
    if 'into_group' not in context and not context.get('question') and context.get('section') is not None:
        context['into_group'] = group_from_request(request, context['section'], context.get('parent'))
    response = render(request, 'editor/partials/question_form_modal.html', context)
    if request.headers.get('HX-Request'):
        response['HX-Retarget'] = '#questionModalBody'
        response['HX-Reswap'] = 'innerHTML'
    return response


def _section_list_row_oob(request, question, survey, mode):
    """The question's section-list row as an out-of-band swap: `append` adds
    it to the list (a row that does not exist yet), `replace` re-renders the
    existing top-level row in place — `[data-top-level]` keeps the selector
    off the modal's own sub-question rows, which carry the same
    data-question-id."""
    item = render(request, 'editor/partials/question_list_item.html', {'thread_counts': _thread_counts(survey, request.user), 
        'question': question, 'survey': survey,
        **_lock_context(survey),
    }).content.decode()
    if mode == 'append':
        return '<div hx-swap-oob="beforeend:#questions-list">%s</div>' % item
    # outerHTML replaces the wrapper too, so the row must BE the oob element.
    # [data-top-level], not `>`: a row inside a group sits one list deeper.
    return item.replace('<li class="question-item"',
                        '<li hx-swap-oob="outerHTML:#questions-list li[data-top-level][data-question-id=\'%d\']" class="question-item"' % question.pk, 1)


def _edit_modal_response(request, question, oob_list_item=False, trigger=None):
    """The question's edit modal, as `editor_question_edit` GET renders it.

    `oob_list_item` carries the question's section-list row out of band:
    `'append'` (or True) for a row that does not exist yet — a draft created
    from the type picker, spec survey-editor "Question rows are created on
    type pick" — and `'replace'` to re-render the existing row, e.g. after a
    sub-question was added from inside the modal; `trigger` sets HX-Trigger
    without the modal-closing `questionSaved`."""
    survey = request.survey
    is_subquestion = question.parent_question_id_id is not None
    form = QuestionForm(instance=question, is_subquestion=is_subquestion, section=question.survey_section,
                        lock_structure=_edit_locks(survey)[1])
    response = _render_question_modal(request, {
        **_question_visibility_context(survey, question),
        'source_layers': _source_layers_of(survey, question),
        'form': form,
        'survey': survey,
        'section': question.survey_section,
        'question': question,
    })
    if oob_list_item:
        mode = 'replace' if oob_list_item == 'replace' else 'append'
        response.content = response.content + _section_list_row_oob(request, question, survey, mode).encode()
    if trigger:
        response['HX-Trigger'] = trigger
    return response


def _visibility_input(request):
    """The Visibility block's raw values, for the service to parse at the
    point the editor always judged them."""
    return {
        'mode': request.POST.get('visibility_mode'),
        'question_code': request.POST.get('visibility_question', ''),
        'match': request.POST.get('visibility_match', 'any_of'),
        'choice_codes': request.POST.getlist('visibility_choices'),
    }


def _question_translations(request, survey):
    return svc_common.translations_from_post(request.POST, survey, svc_questions.TRANSLATION_FIELDS)


@survey_permission_required('editor')
def editor_question_create(request, survey_uuid, section_id):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)

    if request.method == 'POST' and request.POST.get('draft') == '1':
        # Type picked in the "New question" modal: the row exists from this
        # moment (spec survey-editor "Question rows are created on type pick"),
        # and the modal re-renders in edit mode — autosave, sub-questions,
        # everything an existing question has. An unnamed draft is deleted
        # when the modal closes (survey_detail.html).
        into_group = group_from_request(request, section)
        try:
            question = svc_questions.create_draft(
                Actor.from_request(request), section, request.POST.get('input_type', ''),
                name=request.POST.get('name', ''), subtext=request.POST.get('subtext', ''),
                group=into_group)
        except ValidationFailed:
            return JsonResponse({'error': 'Unknown question type.'}, status=400)
        except ServiceError as err:
            return _locked_response(err)
        if into_group is not None:
            # The row lives inside the group's list: re-render the list instead
            # of appending the row at the end of the section.
            return _edit_modal_response(request, question, trigger='questionUpdated, groupsChanged')
        return _edit_modal_response(request, question, oob_list_item=True, trigger='questionUpdated')

    if request.method == 'POST':
        into_group = group_from_request(request, section)
        try:
            question = svc_questions.create(
                Actor.from_request(request), section, request.POST, request.FILES,
                group=into_group, translations=_question_translations(request, survey),
                visibility_input=_visibility_input(request))
        except ValidationFailed as err:
            if getattr(err, 'stage', None) == svc_questions.Stage.CHOICES:
                return HttpResponse(err.message, status=400)
            form = err.form
            if getattr(err, 'stage', None) != svc_questions.Stage.FORM:
                form.add_error(None, err.message)
            return _render_question_modal(request, {
                **_visibility_block_context(survey, section, 'question'),
                'form': form,
                'survey': survey,
                'section': section,
            })
        except ServiceError as err:
            return _locked_response(err)
        if into_group is not None:
            response = _render_section_detail(request, survey, section)
            response['HX-Retarget'] = '#section-content'
            response['HX-Reswap'] = 'innerHTML'
            response['HX-Trigger'] = 'questionSaved'
            return response
        response = render(request, 'editor/partials/question_list_item.html', {'thread_counts': _thread_counts(survey, request.user),
            'question': question,
            'survey': survey,
            **_lock_context(survey),
        })
        response['HX-Trigger'] = 'questionSaved'
        return response
    else:
        form = QuestionForm(section=section)
    return _render_question_modal(request, {
        **_visibility_block_context(survey, section, 'question'),
        'form': form,
        'survey': survey,
        'section': section,
    })


@survey_permission_required('editor')
def editor_question_edit(request, survey_uuid, question_id):
    survey = request.survey
    is_read_only, structure_locked = _edit_locks(survey)
    if request.method == 'POST':
        blocked = _check_content_edit_allowed(survey)
    else:
        # Reading the form is harmless; it renders disabled when nothing may change.
        blocked = None if (live_editing_enabled() or not is_read_only) else _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    question = get_object_or_404(Question, id=question_id, survey_section__survey_header=survey)
    is_subquestion = question.parent_question_id_id is not None

    if request.method == 'POST':
        def render_modal(form):
            return _render_question_modal(request, {
                **_question_visibility_context(survey, question),
                'form': form,
                'survey': survey,
                'section': question.survey_section,
                'question': question,
            })

        autosave = bool(request.POST.get('autosave'))
        try:
            q = svc_questions.update(
                Actor.from_request(request), question, request.POST, request.FILES,
                translations=_question_translations(request, survey),
                visibility_input=_visibility_input(request))
        except StructureLocked as err:
            form = getattr(err, 'form', None)
            if not err.reasons or form is None:
                return _locked_response(err)

            def refusal_modal(message):
                form.add_error(None, message)
                return render_modal(form)
            return _structural_refusal(request, err.reasons, refusal_modal)
        except ValidationFailed as err:
            stage = getattr(err, 'stage', None)
            if stage == svc_questions.Stage.CHOICES:
                return HttpResponse(err.message, status=400)
            if stage == svc_questions.Stage.FORM:
                if autosave:
                    # Autosave must never replace the form the creator is typing
                    # in — report the errors and let the client show the
                    # indicator instead (openspec: editor-autosave).
                    return JsonResponse({'ok': False, 'errors': err.form.errors}, status=422)
                return render_modal(err.form)
            if stage == svc_questions.Stage.VISIBILITY and autosave:
                return JsonResponse({'ok': False, 'errors': {'visibility': [err.message]}}, status=422)
            err.form.add_error(None, err.message)
            if stage == svc_questions.Stage.SETTINGS:
                return _render_question_modal(request, {
                    'form': err.form,
                    'survey': survey,
                    'section': question.survey_section,
                    'question': question,
                })
            return render_modal(err.form)
        except ServiceError as err:
            return _locked_response(err)
        # A sub-question lives inside its parent's section-list row: answer
        # with the parent's row (the form targets it), never a top-level item
        # for the child.
        response = render(request, 'editor/partials/question_list_item.html', {'thread_counts': _thread_counts(survey, request.user),
            'question': q.parent_question_id or q,
            'survey': survey,
            **_lock_context(survey),
        })
        response['HX-Trigger'] = 'questionSaved'
        return response
    else:
        form = QuestionForm(instance=question, is_subquestion=is_subquestion, section=question.survey_section,
                            lock_structure=structure_locked)
    return _render_question_modal(request, {
        'live_answer_count': (
            Answer.objects.filter(question=question).count() if structure_locked and not is_read_only else 0),
        # Sub-questions live inside a geo popup and never carry rules of their own.
        **_question_visibility_context(survey, question),
        'source_layers': _source_layers_of(survey, question),
        'form': form,
        'survey': survey,
        'section': question.survey_section,
        'question': question,
        'return_to_parent': is_subquestion and request.GET.get('return') == 'modal',
    })


@survey_permission_required('viewer')
@xframe_options_sameorigin
def editor_question_preview(request, survey_uuid, question_id):
    survey = request.survey
    question = get_object_or_404(Question, id=question_id, survey_section__survey_header=survey)
    # The pane is a standalone frame: draw the layer's objects server-side
    # (layers.preview_panel) instead of the shell the map would fill.
    question.preview_panel = True

    lang = _preview_language(request, survey)

    # Unsaved picker state from the question modal ("Display as" live preview).
    # Applied to the in-memory instance before the field is built, so for
    # `range` the override also decides the field type, not just the widget.
    style_override = request.GET.get('display_style')
    if style_override in allowed_display_styles(question.input_type):
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
    if display_style not in allowed_display_styles(input_type):
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
            choices = other_option.clamp_single_other(normalise_choice_extras(cleaned)) or None

    # Objects on the map: the draft's layer comes from the modal's picker and
    # must be one of this survey's (canonical owner's) layers.
    draft_layer = None
    if input_type == 'layer_objects':
        raw_layer = request.POST.get('layer', '').strip()
        if raw_layer.isdigit():
            draft_layer = layers_for(survey).filter(pk=int(raw_layer)).first()
        elif raw_layer.startswith('answers:'):
            # "Respondents' marks on <geo question>": the layer is created on
            # save (_resolve_layer_choice); until then preview a transient one
            # so the pane shows the shared-map block, not "not bound yet".
            code = raw_layer[len('answers:'):]
            source = next((q for q in _geo_questions(survey) if q.code == code), None)
            if source is not None:
                owner = layer_owner(survey)
                draft_layer = (owner.map_layers.defer(*GEOMETRY_TEXT_FIELDS).filter(source='question', source_question_code=code).first()
                               or SurveyMapLayer(survey=owner, name=f'Marks: {source.name}'[:100], color='#f97316',
                                                 source='question', source_question_code=code))
    try:
        min_objects = max(0, int(request.POST.get('min_objects') or 0))
    except ValueError:
        min_objects = 0
    objects_search = request.POST.get('objects_search') if request.POST.get('objects_search') in ('auto', 'on', 'off') else 'auto'

    question = Question(
        survey_section=section,
        input_type=input_type,
        name=request.POST.get('name', '').strip(),
        # Put through the same allow-list a save would, so the preview shows what
        # the question will actually become rather than the raw draft.
        subtext=coerce_creator_html(request.POST.get('subtext', '')),
        choices=choices if input_type != 'thumbs' else None,
        color=request.POST.get('color', '').strip() or '#000000',
        icon_class=request.POST.get('icon_class', '').strip(),
        spray_brush=request.POST.get('spray_brush') if request.POST.get('spray_brush') in ('small', 'medium', 'large') else 'medium',
        tap_to_place=input_type == 'point' and bool(request.POST.get('tap_to_place')),
        display_style=display_style,
        required=False,
        layer=draft_layer,
        min_objects=min_objects,
        objects_search=objects_search,
        panel_mode=request.POST.get('panel_mode') if request.POST.get('panel_mode') in ('list', 'legend') else 'list',
    )
    # The draft is unsaved, so it cannot see the sub-questions the real
    # question already has; the pane should still show "collects" correctly.
    if input_type == 'layer_objects':
        question.preview_panel = True
    qid = request.POST.get('question_id', '')
    if input_type == 'layer_objects' and qid.isdigit():
        question.preview_collects = Question.objects.filter(
            parent_question_id_id=int(qid), parent_question_id__survey_section__survey_header=survey).exists()
    if input_type == 'thumbs':
        question.choices = question.thumbs_choices()

    lang = _preview_language(request, survey)
    form = SurveySectionAnswerForm.single_question_form(question, lang)

    return _render_preview_frame(request, form, question, lang,
                                 is_type_example=request.POST.get('example') == '1')


_shared_map_source_layers = svc_questions._shared_map_source_layers
_delete_question_with_layers = svc_questions.delete_with_layers


def _question_delete_blocker(survey, question):
    """409 when the question may not be deleted at all, else None
    (services.questions.delete_blocker)."""
    blocked = svc_questions.delete_blocker(survey, question)
    return JsonResponse({'blocked': blocked}, status=409) if blocked else None


@survey_permission_required('editor')
@require_POST
def editor_question_delete(request, survey_uuid, question_id):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    question = get_object_or_404(Question, id=question_id, survey_section__survey_header=survey)
    parent = question.parent_question_id
    try:
        # `if_empty`: the modal's close handler discards an unnamed draft — but
        # only an EMPTY one (change fix-draft-question-body-loss).
        deleted = svc_questions.delete(
            Actor.from_request(request), question,
            acknowledge_answer_loss=request.POST.get(DELETE_ACKNOWLEDGEMENT) == 'true',
            if_empty=request.POST.get('if_empty') == '1')
    except DeleteBlocked as err:
        return JsonResponse(err.body, status=409)
    except AnswersAtRisk as err:
        return _answers_at_risk_response(err)
    except ServiceError as err:
        return _locked_response(err)
    if not deleted:
        return HttpResponse(status=204)
    # Empty body removes the list row; the trigger is what refreshes the
    # preview — the page does not get a swap event for an empty response. A
    # sub-question deleted inside the parent's modal also re-renders the
    # parent's row in the section list, which otherwise keeps showing it.
    body = _section_list_row_oob(request, parent, survey, 'replace') if parent is not None else ''
    response = HttpResponse(body)
    response['HX-Trigger'] = 'questionUpdated'
    return response


def _save_question_translations(request, question, survey):
    """Save question translations from POST data (non-primary languages only)."""
    svc_questions.save_translations_for(question, survey, _question_translations(request, survey))


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

    try:
        svc_questions.reorder_flat(Actor.from_request(request), survey, question_ids)
    except ValidationFailed:
        return HttpResponse(status=400)
    except ServiceError as err:
        return _locked_response(err)
    return HttpResponse(status=204)


# ─── Sub-question CRUD ────────────────────────────────────────────────────────



QUICK_SUBQUESTIONS = {
    'thumbs': {'name': 'Do you like it?', 'input_type': 'thumbs', 'choices_json': '',
               'share_with_respondents': 'on'},
    'rating': {'name': 'How would you rate it?', 'input_type': 'rating',
               'choices_json': json.dumps([{'code': i, 'name': str(i)} for i in range(1, 6)])},
    'comment': {'name': 'Anything to add?', 'input_type': 'text', 'choices_json': ''},
}
for _preset in QUICK_SUBQUESTIONS.values():
    _preset.setdefault('subtext', '')
    _preset.setdefault('display_style', 'default')
    _preset.setdefault('color', '#000000')


@survey_permission_required('editor')
def editor_question_share(request, survey_uuid, question_id):
    """The "Others see" switch on a sub-question row: other respondents see
    this sub-question's answers on the object (👍/👎 counts, comments)."""
    survey = request.survey
    blocked = _check_content_edit_allowed(survey)
    if blocked:
        return blocked
    if request.method != 'POST':
        return HttpResponse(status=405)
    question = get_object_or_404(Question, id=question_id, survey_section__survey_header=survey,
                                 parent_question_id__input_type='layer_objects')
    try:
        svc_questions.set_share(Actor.from_request(request), question,
                                request.POST.get('share') in ('1', 'true', 'on'))
    except ValidationFailed as err:
        return JsonResponse({'error': err.message}, status=400)
    except ServiceError as err:
        return _locked_response(err)
    response = HttpResponse(status=204)
    response['HX-Trigger'] = 'questionUpdated'
    return response


@survey_permission_required('editor')
def editor_subquestion_create(request, survey_uuid, parent_id):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    parent = get_object_or_404(Question, id=parent_id, survey_section__survey_header=survey)

    if request.method == 'POST':
        data = request.POST
        quick = request.POST.get('quick')
        if quick in QUICK_SUBQUESTIONS:
            # One-tap chips in the Objects form (mockups/journey.md): a preset
            # sub-question the creator can rename afterwards.
            data = request.POST.copy()
            data.update(QUICK_SUBQUESTIONS[quick])
            data['return_to_parent'] = '1'
        try:
            svc_questions.create(
                Actor.from_request(request), parent.survey_section, data, request.FILES,
                parent=parent, group=group_from_request(request, parent.survey_section, parent),
                translations=_question_translations(request, survey),
                visibility_input=_visibility_input(request))
        except ValidationFailed as err:
            stage = getattr(err, 'stage', None)
            if stage == svc_questions.Stage.CHOICES:
                return HttpResponse(err.message, status=400)
            if stage != svc_questions.Stage.FORM:
                err.form.add_error(None, err.message)
            form = err.form
        except ServiceError as err:
            return _locked_response(err)
        else:
            if data.get('return_to_parent') == '1':
                # Opened from the parent's modal: back to it, and the parent's
                # row in the section list re-rendered with the new child.
                return _edit_modal_response(request, parent, oob_list_item='replace', trigger='questionUpdated')
            # Return the parent question item (includes sub-questions)
            response = render(request, 'editor/partials/question_list_item.html', {'thread_counts': _thread_counts(survey, request.user), 
                'question': parent,
                'survey': survey,
                **_lock_context(survey),
            })
            response['HX-Trigger'] = 'questionSaved'
            return response
    else:
        form = QuestionForm(is_subquestion=True)
    return _render_question_modal(request, {
        **_visibility_block_context(survey, parent.survey_section, 'subquestion', parent=parent),
        'form': form,
        'survey': survey,
        'section': parent.survey_section,
        'parent': parent,
        'return_to_parent': request.GET.get('return') == 'modal',
    })


# ─── Duplicate / Copy-Paste (Issue #16) ──────────────────────────────────────


def _shift_order_numbers_down(survey_section, parent, after_order):
    """Increment order_number by 1 for all questions — and groups, which share the
    sequence (change question-groups) — strictly after ``after_order`` in the given
    (section, parent) bucket."""
    group_shift_down(survey_section, parent, after_order)


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
        # A copy of a grouped question stays in the group, right after its source.
        new_question.group_id = source.group_id
        new_question.save(update_fields=['order_number', 'group'])

    response = render(request, 'editor/partials/question_list_item.html', {'thread_counts': _thread_counts(survey, request.user), 
        'question': new_question,
        'survey': survey,
        **_lock_context(survey),
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

    response = render(request, 'editor/partials/section_list_item.html', {'thread_counts': _thread_counts(survey, request.user), 
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
        # A pasted question lands last and ungrouped (change question-groups).
        max_order = group_max_order(target_section, target_parent)
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

    response = render(request, 'editor/partials/question_list_item.html', {'thread_counts': _thread_counts(target_survey, request.user), 
        'question': target_parent if target_parent is not None else new_question,
        'survey': target_survey,
        **_lock_context(target_survey),
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

    response = render(request, 'editor/partials/section_list_item.html', {'thread_counts': _thread_counts(target_survey, request.user), 
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
        blocked = _check_content_edit_allowed(survey)
        if blocked:
            return blocked
        try:
            svc_sections.set_map(
                Actor.from_request(request), section,
                lat=request.POST.get('lat'), lng=request.POST.get('lng'), zoom=request.POST.get('zoom'),
                clear_position=request.POST.get('clear_position', '0') == '1',
                use_geolocation=request.POST.get('use_geolocation', '0') == '1',
                override_basemap=request.POST.get('override_basemap', '') or None,
            )
        except ValidationFailed as err:
            return HttpResponse(err.message, status=400)
        except ServiceError as err:
            return _locked_response(err)
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
    from .layers import section_layer_ids

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

    from .visibility import popup_rules_for_client, section_rules_for_client
    subquestions_forms = {}
    popup_rules = {}
    for question in section.questions():
        # The same card partial the respondent pop-up renders (#320): the
        # pop-up rules toggle `.question-card`s, which as_p() never produced.
        subquestions_forms[question.code] = render_to_string(
            'partials/question_fields.html',
            {'form': SurveySectionAnswerForm(
                initial={}, section=section, question=question,
                survey_session_id=None, language=selected_language,
            )})
        popup_rules.update(popup_rules_for_client(question))

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
        'visible_layers_json': json.dumps(section_layer_ids(section)),
        # Same-section rules so the preview plays both branches live, exactly
        # like the respondent page (conditional_visibility.js reads this).
        'visibility_rules_json': json.dumps(section_rules_for_client(section)),
        'popup_visibility_rules_json': json.dumps(popup_rules),
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
    try:
        svc_publishing.transition(
            Actor.from_request(request), survey, new_status,
            acknowledge_translation_gaps=request.POST.get('ack_translation_gaps') == 'true',
            clear_test_data=request.POST.get('clear_test_data') == 'true')
    except TransitionRefused as err:
        return HttpResponse(err.message, status=400)
    except TranslationGaps as err:
        # Non-blocking warning: the client confirms and retries with the flag.
        return JsonResponse({'translation_gaps': err.gaps}, status=409)

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

@survey_permission_required('editor')
@require_POST
def editor_create_draft(request, survey_uuid):
    """Create a draft copy of a published survey for editing.

    Editors as well as owners: with live editing, this is what "Start
    unpublished changes" does, and an editor who may add a question to a draft
    survey must be able to add one to a live survey's changes. Publishing and
    discarding them stay with the owner.
    """
    survey = request.survey

    # Closed as well as published: a closed survey is read-only for the same
    # reason and needs the same way out. Nothing downstream reads the canonical's
    # status — clone_survey_for_draft copies structure, and publish_draft archives
    # the previous version and leaves the status alone, so a closed survey stays
    # closed after its draft is published.
    # `then` names the structural action that asked for the unpublished changes
    # (the gate in survey_detail.html); the draft page replays the simple ones.
    then = request.POST.get('then', '')
    if then not in GATE_ACTIONS:
        then = ''
    try:
        draft = svc_publishing.create_draft(Actor.from_request(request), survey, then=then)
    except TransitionRefused as err:
        return HttpResponse(err.message, status=400)
    except Conflict as err:
        return HttpResponse(err.message, status=409)
    return redirect(_draft_url_for(
        request, survey, draft, then=then or None,
        section_code=request.POST.get('section_code') or None))


# Structural actions the editor gates behind "unpublished changes". The first
# two are replayed on the draft page; the rest land the creator on the same
# section, where the control now works.
GATE_ACTIONS = (
    'add_question', 'add_section', 'add_subquestion', 'add_group', 'delete', 'duplicate',
    'copy', 'paste', 'reorder', 'type', 'visibility', 'edit',
)


@survey_permission_required('owner')
@require_POST
def editor_restore_version(request, survey_uuid):
    """Restore an archived version's questionnaire as a new draft copy.

    Append-only rollback: the draft clones the archived structure; publishing
    it creates a NEW version — no history is rewritten, no session moves.
    """
    survey = request.survey

    try:
        draft = svc_publishing.restore_version(
            Actor.from_request(request), survey, request.POST.get('version', ''))
    except TransitionRefused as err:
        return HttpResponse(err.message, status=400)
    except Conflict as err:
        return HttpResponse(err.message, status=409)
    if draft is None:
        raise Http404
    return redirect('editor_survey_detail', survey_uuid=draft.uuid)


@survey_permission_required('owner')
@require_POST
def editor_publish_draft(request, survey_uuid):
    """Publish a draft copy as a new version of the canonical survey."""
    survey = request.survey

    if not survey.is_draft_copy:
        return HttpResponse('This survey is not a draft copy', status=400)
    try:
        published = svc_publishing.publish_draft(
            Actor.from_request(request), survey,
            force=request.POST.get('force') == 'true',
            acknowledge_translation_gaps=request.POST.get('ack_translation_gaps') == 'true')
    except TranslationGaps as err:
        return JsonResponse({'translation_gaps': err.gaps}, status=409)
    except IncompatibleDraft as err:
        return JsonResponse({'issues': err.issues}, status=409)
    canonical = published.survey
    return redirect('editor_survey_detail', survey_uuid=canonical.uuid)


@survey_permission_required('owner')
@require_POST
def editor_discard_draft(request, survey_uuid):
    """Discard a draft copy without affecting the canonical survey."""
    survey = request.survey

    if not survey.is_draft_copy:
        return HttpResponse('This survey is not a draft copy', status=400)
    canonical = svc_publishing.discard_draft(Actor.from_request(request), survey)
    return redirect('editor_survey_detail', survey_uuid=canonical.uuid)


@survey_permission_required('editor')
def editor_check_compatibility(request, survey_uuid):
    """Check backward compatibility of a draft against its canonical survey."""
    survey = request.survey

    if not survey.is_draft_copy:
        return JsonResponse({'error': 'Not a draft copy'}, status=400)

    issues = check_draft_compatibility(survey, survey.published_version)
    return JsonResponse({'issues': issues})


@require_POST
@login_required
def set_creator_language(request):
    """Switch the creator's interface language and remember it.

    Writes both the stored preference (survives a new device) and Django's
    language cookie (what `LocaleMiddleware` actually reads — it runs before
    `request.user` exists, so the preference alone cannot reach it in time).

    Only affects creator surfaces. Respondent pages activate the SURVEY's
    language inside the view, after all middleware, so a creator's choice can
    never re-language someone else's survey.
    """
    language = request.POST.get('language', '')
    if language not in dict(settings.LANGUAGES):
        # Unknown or unsupported: fall back rather than error, and do not store
        # a value that would later resolve to a half-translated interface.
        return redirect(request.POST.get('next') or 'editor')

    CreatorPreferences.objects.update_or_create(
        user=request.user, defaults={'ui_language': language},
    )
    # Person property, so activation can be split by interface language in
    # PostHog -- the one number the localisation release still lacked.
    pe.set_person_properties(request.user.pk, {'ui_language': language})
    translation.activate(language)

    # Only same-origin paths, so the switcher cannot be turned into an open
    # redirect by a crafted `next`.
    target = request.POST.get('next') or reverse('editor')
    if not target.startswith('/') or target.startswith('//'):
        target = reverse('editor')

    response = redirect(target)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME, language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )
    return response


# ── In-app changelog (change in-app-changelog, issue #227) ──────────────────

def _changelog_prefs(user):
    prefs, _created = CreatorPreferences.objects.get_or_create(user=user)
    return prefs


def _mark_changelog_seen(prefs):
    """Move the watermark to the newest entry. Idempotent; a no-op with no entries."""
    from . import changelog
    newest = changelog.latest()
    if newest is None or prefs.changelog_seen == newest.id:
        return None
    prefs.changelog_seen = newest.id
    prefs.save(update_fields=['changelog_seen', 'updated_at'])
    return newest


@login_required
def whats_new_page(request):
    """Every entry, newest first; then the watermark moves.

    A GET with a write, deliberately: the deep link from the card and the menu
    item must count as "seen" without a round trip. The highlight is computed
    BEFORE the watermark moves so this render shows what was new; a reload
    shows nothing highlighted. The write is idempotent and only ever marks the
    requester's own changelog read, so a forged GET gains nothing.
    """
    from . import changelog
    prefs = _changelog_prefs(request.user)
    unseen_ids = {e.id for e in changelog.unseen(prefs.changelog_seen)}
    entries = changelog.entries()
    newest = _mark_changelog_seen(prefs)
    if newest is not None:
        pe.emit(pe.CHANGELOG_PAGE_VIEWED, request.user.pk, {'entry_id': newest.id})
    rows = []
    for entry in entries:
        link = ''
        if entry.link:
            try:
                link = reverse(entry.link)
            except NoReverseMatch:
                # An entry pointing at a URL name that was renamed since: the page
                # still renders, just without the "Open" link.
                link = ''
        rows.append({'entry': entry, 'is_new': entry.id in unseen_ids, 'link': link})
    return render(request, 'editor/whats_new.html', {
        'rows': rows,
        'new_count': len(unseen_ids),
        'cards_enabled': prefs.changelog_cards,
    })


@require_POST
@login_required
def whats_new_seen(request):
    """The card's "Got it" / ×: everything seen, one event saying how."""
    from . import changelog
    how = request.POST.get('how', '')
    if how not in ('got_it', 'close'):
        return HttpResponse(status=400)
    prefs = _changelog_prefs(request.user)
    newest = changelog.latest()
    _mark_changelog_seen(prefs)
    if newest is not None:
        pe.emit(pe.CHANGELOG_CARD_DISMISSED, request.user.pk,
                {'entry_id': newest.id, 'how': how})
    return HttpResponse(status=204)


@require_POST
@login_required
def whats_new_cards(request):
    """The "Tell me about updates" switch. Off also marks everything seen: the
    creator muting the card has looked at what it says."""
    from . import changelog
    enabled = request.POST.get('enabled', '')
    if enabled not in ('0', '1'):
        return HttpResponse(status=400)
    prefs = _changelog_prefs(request.user)
    prefs.changelog_cards = enabled == '1'
    prefs.save(update_fields=['changelog_cards', 'updated_at'])
    if enabled == '0':
        newest = changelog.latest()
        _mark_changelog_seen(prefs)
        if newest is not None:
            pe.emit(pe.CHANGELOG_CARD_DISMISSED, request.user.pk,
                    {'entry_id': newest.id, 'how': 'muted'})
    return HttpResponse(status=204)
