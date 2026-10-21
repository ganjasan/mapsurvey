"""Editor endpoints for question groups (change question-groups, #340).

A group is created the moment "Add group" is clicked (the same rule as a question
row created on type pick), edited in its own modal with autosave, reordered with
its questions through one nested reorder endpoint, and deleted with a choice:
only the group (its questions stay where they are) or the group with its
questions (through the answer-loss acknowledgement every delete uses).

Locks follow the live-survey split (design D6): title, description, display style
and translations are content; creating, deleting, moving questions in or out and
the group's rule are structure.
"""
import json
from types import SimpleNamespace

from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext as _
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from . import product_events as pe
from .comments import open_counts as _thread_counts
from .editor_forms import QuestionGroupForm
from .editor_views import (
    _check_content_edit_allowed, _check_structural_edit_allowed, _delete_question_with_layers,
    DELETE_ACKNOWLEDGEMENT as DELETE_ACK, _edit_locks, _lock_context, _parse_visibility_rule,
    _preview_language, _survey_is_unversioned,
    _question_delete_blocker, _refuse_if_answers_at_risk,
    _render_section_detail, _rescreen_if_live, _structural_refusal, _translation_languages,
    _visibility_block_context,
)
from .forms import SurveySectionAnswerForm
from .groups import next_order
from .html_sanitize import coerce_creator_html
from .models import Answer, Question, QuestionGroup, QuestionGroupTranslation, SurveySection
from .permissions import survey_permission_required


def _group_or_404(survey, group_id):
    return get_object_or_404(
        QuestionGroup.objects.select_related('survey_section', 'parent_question'),
        id=group_id, survey_section__survey_header=survey)


def _section_response(request, survey, section, trigger='questionSaved'):
    """The re-rendered section panel, aimed at #section-content whatever the
    element that sent the request targeted."""
    response = _render_section_detail(request, survey, section)
    response['HX-Retarget'] = '#section-content'
    response['HX-Reswap'] = 'innerHTML'
    if trigger:
        response['HX-Trigger'] = trigger
    return response


def _modal_response(request, survey, group, form=None, trigger=None):
    is_read_only, structure_locked = _edit_locks(survey)
    languages = _translation_languages(survey)
    translations = {t.language: t for t in group.translations.all()}
    response = render(request, 'editor/partials/group_form_modal.html', {
        **_visibility_block_context(
            survey, group.survey_section, 'group', host=group, parent=group.parent_question),
        **_lock_context(survey),
        'survey': survey,
        'group': group,
        'form': form or QuestionGroupForm(instance=group),
        'members': list(group.members()),
        'thread_counts': _thread_counts(survey, request.user),
        'translation_rows': [
            {'lang': lang, 't': translations.get(lang)} for lang in languages
        ],
        'primary_language': (survey.available_languages or [None])[0],
    })
    if trigger:
        response['HX-Trigger'] = trigger
    return response


@survey_permission_required('editor')
@require_POST
def editor_group_create(request, survey_uuid, section_id):
    """Create an empty group at the end of a section's top level, or of one
    pop-up when `parent_id` is posted, and open its modal."""
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    section = get_object_or_404(SurveySection, id=section_id, survey_header=survey)
    parent = None
    parent_id = request.POST.get('parent_id')
    if parent_id:
        parent = get_object_or_404(
            Question, id=parent_id, survey_section=section, parent_question_id__isnull=True)
        if not parent.can_have_subquestions:
            return HttpResponse('This question has no pop-up.', status=400)
    group = QuestionGroup.objects.create(
        survey_section=section, parent_question=parent,
        order_number=next_order(section, parent), display_style='card')
    # groupsChanged re-renders the section list behind the open modal.
    return _modal_response(request, survey, group, trigger='groupsChanged')


@survey_permission_required('editor')
def editor_group_edit(request, survey_uuid, group_id):
    """GET: the group modal. POST (autosave): save content fields, translations
    and — structure permitting — the visibility rule; answers JSON."""
    survey = request.survey
    group = _group_or_404(survey, group_id)
    if request.method != 'POST':
        return _modal_response(request, survey, group)

    blocked = _check_content_edit_allowed(survey)
    if blocked:
        return blocked
    _, structure_locked = _edit_locks(survey)
    form = QuestionGroupForm(request.POST, instance=group)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors}, status=422)
    vis_present, vis_rule, vis_error = _parse_visibility_rule(request)
    if vis_error:
        return JsonResponse({'ok': False, 'errors': {'visibility': [vis_error]}}, status=422)
    before_rule = group.visibility_rule
    if structure_locked and vis_present and vis_rule != before_rule:
        return _structural_refusal(request, ['visibility rule'])
    group = form.save(commit=False)
    if vis_present:
        group.visibility_rule = vis_rule
    group.save()
    _save_group_translations(request, group, survey)
    if structure_locked:
        pe.emit(pe.LIVE_EDIT_SAVED, request.user.pk, {'survey_id': str(survey.id), 'kind': 'group'})
        _rescreen_if_live(survey)
    response = JsonResponse({'ok': True})
    response['HX-Trigger'] = 'questionUpdated'
    return response


def _save_group_translations(request, group, survey):
    """Translated title/description for every non-primary language; the
    description passes the same creator-HTML coercion as the base one."""
    for lang in _translation_languages(survey):
        if f'translation_{lang}_title' not in request.POST and \
                f'translation_{lang}_description' not in request.POST:
            continue
        title = request.POST.get(f'translation_{lang}_title', '').strip()[:512]
        description = coerce_creator_html(
            request.POST.get(f'translation_{lang}_description', '')).strip()
        if title or description:
            QuestionGroupTranslation.objects.update_or_create(
                group=group, language=lang,
                defaults={'title': title or None, 'description': description or None})
        else:
            QuestionGroupTranslation.objects.filter(group=group, language=lang).delete()


@survey_permission_required('editor')
def editor_group_delete(request, survey_uuid, group_id):
    """GET: the delete dialog (a choice when the group holds questions).
    POST: delete the group; with `with_questions=1` its questions too, behind
    the same answer-loss acknowledgement as deleting a question."""
    survey = request.survey
    group = _group_or_404(survey, group_id)
    members = list(group.members())
    if request.method != 'POST':
        return render(request, 'editor/partials/group_delete_dialog.html', {
            'survey': survey, 'group': group, 'member_count': len(members),
        })
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    section = group.survey_section
    with_questions = (request.POST.get('with_questions') or request.GET.get('with_questions')) == '1'
    if with_questions and members:
        for member in members:
            refusal = _question_delete_blocker(survey, member)
            if refusal:
                return refusal
        ids = []
        for member in members:
            ids.extend(member.descendant_question_ids())
        refusal = _refuse_if_answers_at_risk(
            request, survey, Answer.objects.filter(question_id__in=ids).count())
        if refusal:
            return refusal
        with transaction.atomic():
            for member in members:
                _delete_question_with_layers(survey, member)
            group.delete()
    else:
        # SET_NULL on Question.group: the members stay in place, ungrouped.
        group.delete()
    return _section_response(request, survey, section)


@survey_permission_required('viewer')
@require_POST
@xframe_options_sameorigin
def editor_group_preview_live(request, survey_uuid, group_id):
    """The group modal's "Respondent sees": the group as currently typed
    (title, description, style — unsaved), between two faded neighbour
    questions, so the difference between plain, card and collapsible shows
    against what surrounds it. A group with no questions yet is filled with
    two example questions, marked as such. A pop-up group renders in pop-up
    styling (frameless cards), the way respondents meet it."""
    from django.utils import translation as dj_translation
    from django.utils.translation import gettext as _
    survey = request.survey
    group = _group_or_404(survey, group_id)
    lang = _preview_language(request, survey)
    in_popup = group.parent_question_id is not None
    members = list(group.members())
    is_example = not members
    if is_example:
        members = [
            Question(code='__qg_example_1', name=_('Example question'), input_type='text_line'),
            Question(code='__qg_example_2', name=_('Another example question'), input_type='choice',
                     choices=[{'code': 1, 'name': _('Option A')}, {'code': 2, 'name': _('Option B')}]),
        ]
    where = _('this pop-up') if in_popup else _('this section')
    before = Question(code='__qg_before', input_type='text_line',
                      name=_('A question before the group in %(where)s') % {'where': where})
    after = Question(code='__qg_after', input_type='text_line',
                     name=_('A question after the group'))
    form = SurveySectionAnswerForm(
        initial={}, section=group.survey_section, question=None, survey_session_id=None,
        language=lang, questions_override=[before, *members, after])
    style = request.POST.get('display_style')
    if style not in dict(QuestionGroup._meta.get_field('display_style').choices):
        style = group.display_style
    title = request.POST.get('title', group.title)
    description = coerce_creator_html(request.POST.get('description', group.description) or '')
    fields = [form[q.code] for q in members if q.code in form.fields]
    form.runs_override = [{
        'group': SimpleNamespace(code=group.code, display_style=style),
        'title': title, 'description': description, 'fields': fields,
    }]
    if lang:
        dj_translation.activate(lang)
    response = render(request, 'editor/partials/group_preview_frame.html', {
        'form': form,
        'before_field': form['__qg_before'],
        'after_field': form['__qg_after'],
        'in_popup': in_popup,
        'is_example': is_example,
    })
    if lang:
        dj_translation.deactivate()
    return response


def _parse_root(body, survey):
    """(section, parent_id) of the list a drag body names; raises on anything else."""
    section = SurveySection.objects.get(id=int(body['section_id']), survey_header=survey)
    parent_id = body.get('parent_id')
    parent_id = int(parent_id) if parent_id not in (None, '') else None
    items = body['items']
    if not isinstance(items, list):
        raise ValueError
    return section, parent_id, items


def _apply_nested_order(section, parent_id, items):
    """Renumber one root (a section's top level or one pop-up) 0..N from its
    nested DOM state and set each question's group from where it sits. Raises
    ValueError when an id is not of this root, or is listed twice."""
    q_qs = Question.objects.filter(survey_section=section)
    g_qs = QuestionGroup.objects.filter(survey_section=section)
    if parent_id is None:
        q_qs, g_qs = q_qs.filter(parent_question_id__isnull=True), g_qs.filter(parent_question__isnull=True)
    else:
        q_qs, g_qs = q_qs.filter(parent_question_id=parent_id), g_qs.filter(parent_question_id=parent_id)
    questions = {q.id: q for q in q_qs}
    groups = {g.id: g for g in g_qs}

    sequence = []          # [(kind, obj, group_or_None)]
    try:
        for item in items:
            if 'g' in item:
                group = groups[int(item['g'])]
                sequence.append(('g', group, None))
                for qid in item.get('q') or []:
                    sequence.append(('q', questions[int(qid)], group))
            else:
                sequence.append(('q', questions[int(item['q'])], None))
    except (KeyError, TypeError, ValueError):
        # An id of another section or pop-up, or of nothing.
        raise ValueError('foreign id')
    seen = {(kind, obj.id) for kind, obj, _g in sequence}
    if len(seen) != len(sequence):
        raise ValueError('listed twice')
    # Rows the page did not list (another tab added them) keep their relative
    # order after everything that was listed.
    rest = sorted(
        [('q', q, q.group if q.group_id in groups else None) for q in questions.values() if ('q', q.id) not in seen]
        + [('g', g, None) for g in groups.values() if ('g', g.id) not in seen],
        key=lambda t: (t[1].order_number, t[1].id))
    for i, (kind, obj, group) in enumerate(sequence + rest):
        if kind == 'g':
            QuestionGroup.objects.filter(pk=obj.pk).update(order_number=i)
        else:
            Question.objects.filter(pk=obj.pk).update(
                order_number=i, group_id=group.pk if group else None)


@survey_permission_required('editor')
@require_POST
def editor_items_reorder(request, survey_uuid):
    """One list's order after a drag: a section's top level or one pop-up,
    with group nesting. Body: {"section_id", "parent_id" | null, "items":
    [{"g": <id>, "q": [<id>, ...]} | {"q": <id>}, ...]}. Renumbers groups and
    questions 0..N as ONE sequence and sets each question's group from where
    it was dropped (design D7)."""
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    try:
        section, parent_id, items = _parse_root(json.loads(request.body), survey)
        with transaction.atomic():
            _apply_nested_order(section, parent_id, items)
    except (ValueError, KeyError, TypeError, SurveySection.DoesNotExist):
        return HttpResponse(status=400)
    response = HttpResponse(status=204)
    response['HX-Trigger'] = 'questionUpdated'
    return response


@survey_permission_required('editor')
@require_POST
def editor_question_move(request, survey_uuid, question_id):
    """Move a question between a section's top level and a pop-up of the same
    section (design D7b). Body: the target root as for editor_items_reorder,
    with the moved question already in `items`. Answers cannot be carried over
    (one per respondent in a section, one per mark in a pop-up), so they are
    deleted behind the usual acknowledgement; rules the move breaks are
    removed and named in `removed_rules`."""
    from .editor_forms import SUBQUESTION_DISALLOWED_INPUT_TYPES
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    question = get_object_or_404(Question, id=question_id, survey_section__survey_header=survey)
    try:
        body = json.loads(request.body or b'{}')
        section, parent_id, items = _parse_root(body, survey)
    except (ValueError, KeyError, TypeError, SurveySection.DoesNotExist):
        return HttpResponse(status=400)
    if section.id != question.survey_section_id:
        return HttpResponse('A question moves within its section only.', status=400)
    if parent_id == question.parent_question_id_id:
        return HttpResponse('Same list: use the reorder endpoint.', status=400)
    target_parent = None
    if parent_id is not None:
        target_parent = Question.objects.filter(
            pk=parent_id, survey_section=section, parent_question_id__isnull=True).first()
        if target_parent is None or not target_parent.can_have_subquestions:
            return HttpResponse('That question has no pop-up.', status=400)
        if question.input_type in SUBQUESTION_DISALLOWED_INPUT_TYPES \
                or Question.objects.filter(parent_question_id=question).exists():
            return JsonResponse({'blocked': _('This kind of question cannot go into a pop-up.')}, status=409)

    ack = request.GET.get(DELETE_ACK) == 'true' or body.get(DELETE_ACK) in (True, 'true')
    answer_count = question.answer_count()
    if answer_count and not ack:
        return JsonResponse({
            'answers_at_risk': answer_count,
            'explain_versioning': _survey_is_unversioned(survey),
        }, status=409)

    with transaction.atomic():
        if answer_count:
            Answer.objects.filter(question_id__in=question.descendant_question_ids()).delete()
        own_rule = isinstance(question.visibility_rule, dict)
        question.parent_question_id = target_parent
        question.group = None
        question.visibility_rule = None
        if target_parent is None or target_parent.input_type != 'layer_objects':
            question.share_with_respondents = False
        question.save(update_fields=['parent_question_id', 'group', 'visibility_rule',
                                     'share_with_respondents'])
        try:
            _apply_nested_order(section, parent_id, items)
        except ValueError:
            transaction.set_rollback(True)
            return HttpResponse(status=400)
        removed = _drop_rules_broken_by_move(survey, question.code)
    if own_rule:
        removed.insert(0, question.name or question.code)
    response = JsonResponse({'ok': True, 'removed_rules': removed})
    response['HX-Trigger'] = 'questionUpdated'
    return response


def _drop_rules_broken_by_move(survey, code):
    """Rules naming `code` that no longer resolve after it moved: removed,
    and the labels of their hosts returned for the editor's notice."""
    from .templatetags.question_utils import visibility_info
    removed = []
    hosts = list(SurveySection.objects.filter(survey_header=survey, visibility_rule__question_code=code))
    hosts += list(Question.objects.filter(survey_section__survey_header=survey,
                                          visibility_rule__question_code=code))
    hosts += list(QuestionGroup.objects.filter(survey_section__survey_header=survey,
                                               visibility_rule__question_code=code))
    for host in hosts:
        info = visibility_info(host, survey) if getattr(settings, 'CONDITIONAL_VISIBILITY', False) else None
        if info and info.get('broken'):
            host.visibility_rule = None
            host.save(update_fields=['visibility_rule'])
            removed.append(getattr(host, 'name', None) or getattr(host, 'title', None) or getattr(host, 'code', ''))
    return removed
