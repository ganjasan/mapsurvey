import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.gis.geos import Point
from django.db import transaction
from django.db.models import Q, Max
from django.http import HttpResponse, JsonResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.utils import translation
from django.views.decorators.http import require_POST

from .models import (
    SurveyHeader, SurveySection, SurveySectionTranslation,
    Question, QuestionTranslation,
)
from .editor_forms import SurveyHeaderForm, SurveySectionForm, QuestionForm
from .forms import SurveySectionAnswerForm


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

@login_required
def editor_survey_create(request):
    if request.method == 'POST':
        form = SurveyHeaderForm(request.POST)
        if form.is_valid():
            survey = form.save()
            # Create default first section
            SurveySection.objects.create(
                survey_header=survey,
                name='section_1',
                title='Section 1',
                code='S1',
                is_head=True,
            )
            return redirect('editor_survey_detail', survey_name=survey.name)
    else:
        form = SurveyHeaderForm()
    return render(request, 'editor/survey_create.html', {'form': form})


# ─── Survey editor main page ─────────────────────────────────────────────────

@login_required
def editor_survey_detail(request, survey_name):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
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

    return render(request, 'editor/survey_detail.html', {
        'survey': survey,
        'sections': sections,
        'current_section': current_section,
        'questions': questions,
    })


# ─── Survey settings ─────────────────────────────────────────────────────────

@login_required
def editor_survey_settings(request, survey_name):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
    if request.method == 'POST':
        form = SurveyHeaderForm(request.POST, instance=survey)
        if form.is_valid():
            form.save()
            if request.headers.get('HX-Request'):
                return HttpResponse(status=204, headers={'HX-Trigger': 'settingsSaved'})
            return redirect('editor_survey_detail', survey_name=survey.name)
    else:
        form = SurveyHeaderForm(instance=survey)
    return render(request, 'editor/survey_settings_modal.html', {
        'survey': survey,
        'form': form,
    })


# ─── Section CRUD ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def editor_section_create(request, survey_name):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
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


@login_required
def editor_section_detail(request, survey_name, section_id):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)

    if request.method == 'POST':
        form = SurveySectionForm(request.POST, instance=section)
        if form.is_valid():
            form.save()
            # Save translations
            _save_section_translations(request, section, survey)
            if request.headers.get('HX-Request'):
                return HttpResponse(status=204, headers={'HX-Trigger': 'sectionSaved'})
            return redirect('editor_survey_detail', survey_name=survey_name)
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


@login_required
@require_POST
def editor_section_delete(request, survey_name, section_id):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
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

@login_required
@require_POST
def editor_sections_reorder(request, survey_name):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
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

@login_required
def editor_question_create(request, survey_name, section_id):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
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


@login_required
def editor_question_edit(request, survey_name, question_id):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
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


@login_required
@xframe_options_sameorigin
def editor_question_preview(request, survey_name, question_id):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
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


@login_required
@require_POST
def editor_question_delete(request, survey_name, question_id):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
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

@login_required
@require_POST
def editor_questions_reorder(request, survey_name):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
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

@login_required
def editor_subquestion_create(request, survey_name, parent_id):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
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

@login_required
def editor_section_map_picker(request, survey_name, section_id):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)

    if request.method == 'POST':
        lat = float(request.POST.get('lat', 59.945))
        lng = float(request.POST.get('lng', 30.317))
        zoom = int(request.POST.get('zoom', 12))
        section.start_map_postion = Point(lng, lat)
        section.start_map_zoom = zoom
        section.save(update_fields=['start_map_postion', 'start_map_zoom'])
        return HttpResponse(status=204, headers={'HX-Trigger': 'mapPositionSaved'})

    return render(request, 'editor/partials/section_map_picker.html', {
        'survey': survey,
        'section': section,
    })


# ─── Live preview ─────────────────────────────────────────────────────────────

@login_required
@xframe_options_sameorigin
def editor_section_preview(request, survey_name, section_name):
    survey = get_object_or_404(SurveyHeader, name=survey_name)
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
