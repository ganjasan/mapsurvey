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

from django.utils.translation import gettext as _
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from .comments import open_counts as _thread_counts
from .editor_forms import QuestionGroupForm
from .editor_views import (
    _answers_at_risk_response, _check_content_edit_allowed, _check_structural_edit_allowed,
    DELETE_ACKNOWLEDGEMENT as DELETE_ACK, _edit_locks, _lock_context, _locked_response,
    _parse_visibility_rule, _preview_language, _render_section_detail, _structural_refusal,
    _translation_languages, _visibility_block_context,
)
from .forms import SurveySectionAnswerForm
from .html_sanitize import coerce_creator_html
from .models import Question, QuestionGroup, SurveySection
from .permissions import survey_permission_required
from .services import groups as svc_groups
from .services import questions as svc_questions
from .services import structure as svc_structure
from .services.common import UNSET
from .services.context import Actor
from .services.errors import (
    AnswersAtRisk, DeleteBlocked, ServiceError, StructureLocked, ValidationFailed,
)


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
    try:
        group = svc_groups.create(Actor.from_request(request), section, parent=parent)
    except ValidationFailed as err:
        return HttpResponse(err.message, status=400)
    except ServiceError as err:
        return _locked_response(err)
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
    form = QuestionGroupForm(request.POST, instance=group)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors}, status=422)
    vis_present, vis_rule, vis_error = _parse_visibility_rule(request)
    if vis_error:
        return JsonResponse({'ok': False, 'errors': {'visibility': [vis_error]}}, status=422)
    try:
        svc_groups.update(
            Actor.from_request(request), group,
            {name: request.POST.get(name, '') for name in QuestionGroupForm._meta.fields},
            visibility_rule=vis_rule if vis_present else UNSET,
            translations=_posted_group_translations(request, survey))
    except StructureLocked as err:
        return _structural_refusal(request, err.reasons)
    except ValidationFailed as err:
        return JsonResponse({'ok': False, 'errors': err.fields}, status=422)
    except ServiceError as err:
        return _locked_response(err)
    response = JsonResponse({'ok': True})
    response['HX-Trigger'] = 'questionUpdated'
    return response


def _posted_group_translations(request, survey):
    """`{lang: {title, description}}` for the languages the modal posted; the
    service caps the title and coerces the description like the base ones."""
    out = {}
    for lang in _translation_languages(survey):
        keys = (f'translation_{lang}_title', f'translation_{lang}_description')
        if any(key in request.POST for key in keys):
            out[lang] = {'title': request.POST.get(keys[0], ''), 'description': request.POST.get(keys[1], '')}
    return out


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
    try:
        # Without questions, SET_NULL on Question.group keeps the members in place, ungrouped.
        svc_groups.delete(Actor.from_request(request), group, with_questions=with_questions,
                          acknowledge_answer_loss=request.POST.get(DELETE_ACK) == 'true')
    except DeleteBlocked as err:
        return JsonResponse(err.body, status=409)
    except AnswersAtRisk as err:
        return _answers_at_risk_response(err)
    except ServiceError as err:
        return _locked_response(err)
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
        svc_questions.reorder(Actor.from_request(request), section, parent_id, items)
    except (ValueError, KeyError, TypeError, SurveySection.DoesNotExist, ValidationFailed):
        return HttpResponse(status=400)
    response = HttpResponse(status=204)
    response['HX-Trigger'] = 'questionUpdated'
    return response


@survey_permission_required('editor')
@require_POST
def editor_question_move(request, survey_uuid, question_id):
    """Move a question (services.structure.move_question).

    Drag between a section's top level and one of its pop-ups (design D7b of
    question-groups): the body is the target root as for editor_items_reorder,
    with the moved question already in `items`. "Move to section…" (change
    api-v2-structure): `{"section_id"}` of another section and no `items`;
    the question goes to the end of its top level. Answers that cannot follow
    a change of level are deleted behind the usual acknowledgement; rules the
    move breaks are removed and named in `removed_rules`."""
    survey = request.survey
    blocked = _check_structural_edit_allowed(survey)
    if blocked:
        return blocked
    question = get_object_or_404(Question, id=question_id, survey_section__survey_header=survey)
    try:
        body = json.loads(request.body or b'{}')
        section = SurveySection.objects.get(id=int(body['section_id']), survey_header=survey)
        parent_id = body.get('parent_id')
        parent_id = int(parent_id) if parent_id not in (None, '') else None
        items = body.get('items')
        if items is not None and not isinstance(items, list):
            raise ValueError
    except (ValueError, KeyError, TypeError, SurveySection.DoesNotExist):
        return HttpResponse(status=400)
    if items is not None and section.id == question.survey_section_id \
            and parent_id == question.parent_question_id_id:
        return HttpResponse('Same list: use the reorder endpoint.', status=400)
    parent = None
    if parent_id is not None:
        parent = Question.objects.filter(
            pk=parent_id, survey_section=section, parent_question_id__isnull=True).first()
        if parent is None:
            return HttpResponse('That question has no pop-up.', status=400)
    ack = request.GET.get(DELETE_ACK) == 'true' or body.get(DELETE_ACK) in (True, 'true')
    try:
        moved = svc_structure.move_question(
            Actor.from_request(request), question, section=section, parent=parent, items=items,
            acknowledge_answer_loss=ack)
    except AnswersAtRisk as err:
        return _answers_at_risk_response(err)
    except ValidationFailed as err:
        if err.message == svc_structure.POPUP_REFUSED:
            return JsonResponse({'blocked': _('This kind of question cannot go into a pop-up.')}, status=409)
        if 'parent_id' in err.fields:
            return HttpResponse(err.message, status=400)
        return HttpResponse(status=400)
    except ServiceError as err:
        return _locked_response(err)
    response = JsonResponse({'ok': True, 'removed_rules': moved.removed_rules})
    response['HX-Trigger'] = 'questionUpdated'
    return response
