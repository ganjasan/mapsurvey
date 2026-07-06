import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.gis.geos import Point
from django.db import transaction
from django.db.models import Q, Max
from django.http import HttpResponse, JsonResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.utils import translation
from django.views.decorators.http import require_POST

from .models import (
    SurveyHeader, SurveySession, SurveySection, SurveySectionTranslation,
    Question, QuestionTranslation, SurveyCollaborator,
    Membership, SURVEY_ROLE_CHOICES, BASEMAP_CHOICES,
)
from .cloning import clone_question, clone_section
from .editor_forms import (
    SurveyHeaderForm, SurveyCreateForm, SurveySectionForm, QuestionForm,
    SUBQUESTION_DISALLOWED_INPUT_TYPES,
)
from .forms import SurveySectionAnswerForm
from .permissions import (
    org_permission_required, survey_permission_required,
    get_effective_survey_role,
)
from .versioning import clone_survey_for_draft, check_draft_compatibility, publish_draft, IncompatibleDraftError
from .audit import audit


def _check_structural_edit_allowed(survey):
    """Return HttpResponse(403) if survey is read-only, else None."""
    if survey.status in ('published', 'closed'):
        return HttpResponse('Structural edits are not allowed on published or closed surveys', status=403)
    return None


def _can_read_survey(user, survey):
    """Return True if user has at least viewer role on the survey."""
    return get_effective_survey_role(user, survey) is not None


def _is_ajax(request):
    """True for fetch/XHR autosave requests (vs a plain form submit)."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _get_sections_ordered(survey):
    """Return sections in linked-list order."""
    sections = list(SurveySection.objects.filter(survey_header=survey))
    if not sections:
        return []

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

@org_permission_required('editor')
def editor_survey_create(request):
    if request.method == 'POST':
        form = SurveyCreateForm(request.POST)
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
    return render(request, 'editor/survey_create.html', {
        'form': form,
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
        is_owner and survey.status == 'published' and not survey.has_draft_copy()
    )
    show_draft_actions = is_owner and survey.is_draft_copy

    return render(request, 'editor/survey_detail.html', {
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

    if request.method == 'POST':
        thanks = {}
        for lang in langs:
            cleaned = sanitize_thanks_html(request.POST.get('thanks_{}'.format(lang), ''))
            if cleaned:
                thanks[lang] = cleaned
        survey.thanks_html = thanks
        survey.save(update_fields=['thanks_html'])
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
        'effective_role': request.effective_survey_role,
    })


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

    return render(request, 'editor/partials/section_detail_form.html', {
        'survey': survey,
        'section': section,
        'form': form,
        'translations': translations,
        'questions': questions,
        'is_read_only': survey.status in ('published', 'closed'),
    })


def _save_section_translations(request, section, survey):
    """Save section translations from POST data."""
    for lang in (survey.available_languages or []):
        title = request.POST.get(f'translation_{lang}_title', '').strip()
        subheading = request.POST.get(f'translation_{lang}_subheading', '').strip()
        if title or subheading:
            SurveySectionTranslation.objects.update_or_create(
                section=section, language=lang,
                defaults={'title': title or None, 'subheading': subheading or None},
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
        form = QuestionForm(request.POST, request.FILES)
        if form.is_valid():
            question = form.save(commit=False)
            question.survey_section = section
            # Auto-assign next order number
            max_order = Question.objects.filter(
                survey_section=section, parent_question_id__isnull=True
            ).aggregate(Max('order_number'))['order_number__max']
            question.order_number = (max_order or 0) + 1
            # Handle choices
            choices_json = request.POST.get('choices_json', '').strip()
            if choices_json:
                question.choices = json.loads(choices_json)
            question.save()
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
        form = QuestionForm()
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
        form = QuestionForm(request.POST, request.FILES, instance=question, is_subquestion=is_subquestion)
        if form.is_valid():
            q = form.save(commit=False)
            choices_json = request.POST.get('choices_json', '').strip()
            if choices_json:
                q.choices = json.loads(choices_json)
            elif q.input_type not in ('choice', 'multichoice', 'range', 'rating'):
                q.choices = None
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
        return render(request, 'editor/partials/question_form_modal.html', {
            'form': form,
            'survey': survey,
            'section': question.survey_section,
            'question': question,
        })
    else:
        form = QuestionForm(instance=question, is_subquestion=is_subquestion)
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

    lang = request.GET.get('lang')
    if lang and survey.available_languages and lang not in survey.available_languages:
        lang = None
    if not lang and survey.available_languages:
        lang = survey.available_languages[0]

    # Build a form for the whole section, then keep only this question's field
    form = SurveySectionAnswerForm(
        initial={}, section=question.survey_section, question=None,
        survey_session_id=None, language=lang,
    )
    for key in list(form.fields.keys()):
        if key != question.code:
            del form.fields[key]

    # Unsaved picker state from the question modal ("Display as" live preview)
    style_override = request.GET.get('display_style')
    if style_override in ('default', 'scale_strip', 'list_pips'):
        field = form.fields.get(question.code)
        if field is not None:
            field.widget.display_style = (
                style_override
                if style_override in ('scale_strip', 'list_pips')
                else survey.get_default_rating_display_style()
            )

    if lang:
        translation.activate(lang)

    response = render(request, 'editor/partials/question_preview_frame.html', {
        'form': form,
        'question': question,
    })

    if lang:
        translation.deactivate()

    return response


@survey_permission_required('editor')
@require_POST
def editor_question_delete(request, survey_uuid, question_id):
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    question = get_object_or_404(Question, id=question_id, survey_section__survey_header=survey)
    question.delete()
    return HttpResponse('')


def _save_question_translations(request, question, survey):
    """Save question translations from POST data."""
    for lang in (survey.available_languages or []):
        name = request.POST.get(f'translation_{lang}_name', '').strip()
        subtext = request.POST.get(f'translation_{lang}_subtext', '').strip()
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
            if choices_json:
                question.choices = json.loads(choices_json)
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

    if survey.status != 'published':
        return HttpResponse('Only published surveys can have draft copies', status=400)

    if survey.has_draft_copy():
        return HttpResponse('A draft already exists for this survey', status=409)

    draft = clone_survey_for_draft(survey)
    return redirect('editor_survey_detail', survey_uuid=draft.uuid)


@survey_permission_required('owner')
@require_POST
def editor_publish_draft(request, survey_uuid):
    """Publish a draft copy as a new version of the canonical survey."""
    survey = request.survey

    if not survey.is_draft_copy:
        return HttpResponse('This survey is not a draft copy', status=400)

    force = request.POST.get('force') == 'true'

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
