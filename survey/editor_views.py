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
    Membership, SURVEY_ROLE_CHOICES,
)
from .editor_forms import SurveyHeaderForm, SurveySectionForm, QuestionForm
from .forms import SurveySectionAnswerForm
from .permissions import (
    org_permission_required, survey_permission_required,
    get_effective_survey_role,
)
from .versioning import clone_survey_for_draft, check_draft_compatibility, publish_draft, IncompatibleDraftError


def _check_structural_edit_allowed(survey):
    """Return HttpResponse(403) if survey is read-only, else None."""
    if survey.status in ('published', 'closed'):
        return HttpResponse('Structural edits are not allowed on published or closed surveys', status=403)
    return None


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
        form = SurveyHeaderForm(request.POST)
        if form.is_valid():
            survey = form.save(commit=False)
            survey.organization = request.active_org
            survey.created_by = request.user
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
        form = SurveyHeaderForm()
    return render(request, 'editor/survey_create.html', {'form': form})


# ─── Survey editor main page ─────────────────────────────────────────────────

@survey_permission_required('viewer')
def editor_survey_detail(request, survey_uuid):
    survey = request.survey
    sections = _get_sections_ordered(survey)

    current_section_id = request.GET.get('section')
    current_section = None
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
    })


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

    if request.method == 'POST':
        form = QuestionForm(request.POST, request.FILES, instance=question)
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
        form = QuestionForm(instance=question)
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
        form = QuestionForm(request.POST, request.FILES)
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
            })
            response['HX-Trigger'] = 'questionSaved'
            return response
    else:
        form = QuestionForm()
    return render(request, 'editor/partials/question_form_modal.html', {
        'form': form,
        'survey': survey,
        'section': parent.survey_section,
        'parent': parent,
    })


# ─── Section map position picker ─────────────────────────────────────────────

@survey_permission_required('editor')
def editor_section_map_picker(request, survey_uuid, section_id):
    survey = request.survey
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)

    if request.method == 'POST':
        blocked = _check_structural_edit_allowed(survey)
        if blocked:
            return blocked
        lat = float(request.POST.get('lat', 52.52))
        lng = float(request.POST.get('lng', 13.405))
        zoom = int(request.POST.get('zoom', 12))
        use_geolocation = request.POST.get('use_geolocation', '0') == '1'
        section.start_map_postion = Point(lng, lat)
        section.start_map_zoom = zoom
        section.use_geolocation = use_geolocation
        section.save(update_fields=['start_map_postion', 'start_map_zoom', 'use_geolocation'])
        return HttpResponse(status=204, headers={'HX-Trigger': 'mapPositionSaved'})

    return render(request, 'editor/partials/section_map_picker.html', {
        'survey': survey,
        'section': section,
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
        'existing_geo_answers_json': '{}',
        'section_current': 1,
        'section_total': 1,
        'preview': True,
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
            SurveySession.objects.filter(survey=survey).delete()

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

    elif action == 'remove':
        survey.clear_password()
        survey.save(update_fields=['password_hash'])

    elif action == 'regenerate_token':
        survey.regenerate_test_token()
        survey.save(update_fields=['test_token'])

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

    return redirect('editor_survey_detail', survey_uuid=canonical.uuid)


@survey_permission_required('owner')
@require_POST
def editor_discard_draft(request, survey_uuid):
    """Discard a draft copy without affecting the canonical survey."""
    survey = request.survey

    if not survey.is_draft_copy:
        return HttpResponse('This survey is not a draft copy', status=400)

    canonical = survey.published_version
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
