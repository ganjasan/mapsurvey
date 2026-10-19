"""Question groups: one continuous order shared with the questions around them.

A `QuestionGroup` takes a slot in the same `order_number` sequence as its
sibling questions (the top-level questions of a section, or the sub-questions
of one geo / Objects-on-the-map question) and its members follow it
contiguously. So `section.questions()`, `subQuestions()` and the visibility
engine's "controller is earlier" test keep working unchanged, and only the
surfaces that draw a group need to know about it — through `group_runs`.

Change question-groups (#340), design D2.
"""
from django.db.models import F, Max

from .models import Question, QuestionGroup


def groups_for(section, parent=None):
    """Groups of a section's top level (parent None) or of one pop-up."""
    qs = QuestionGroup.objects.filter(survey_section=section)
    if parent is None:
        return qs.filter(parent_question__isnull=True).order_by('order_number', 'id')
    return qs.filter(parent_question=parent).order_by('order_number', 'id')


def group_runs(questions, groups):
    """Merge sibling questions and groups into `[(group | None, [questions])]`.

    Walks both lists by `order_number` (a group before a question of the same
    number). A question joins the run of the group it names when that group is
    the open run; a member found out of place — another question between it and
    its group — opens a second run of the same group, so a broken invariant
    repeats a header rather than dropping a question. A question naming a group
    that is not among `groups` renders ungrouped. Empty groups yield an empty
    run; callers that must not show them filter on the list.
    """
    groups = list(groups)
    by_id = {g.id: g for g in groups}
    items = sorted(
        [(g.order_number, 0, g.id, g) for g in groups]
        + [(q.order_number, 1, q.id, q) for q in questions],
        key=lambda t: t[:3],
    )
    runs = []
    for _order, kind, _id, obj in items:
        if kind == 0:
            runs.append((obj, []))
            continue
        group = by_id.get(obj.group_id)
        if group is None:
            if not runs or runs[-1][0] is not None:
                runs.append((None, []))
            runs[-1][1].append(obj)
        elif runs and runs[-1][0] is group:
            runs[-1][1].append(obj)
        else:
            runs.append((group, [obj]))
    return runs


def runs_for(section, parent=None, questions=None):
    """`group_runs` over a section's top level or one pop-up, read from the DB."""
    if questions is None:
        questions = section.questions() if parent is None else parent.subQuestions()
    return group_runs(questions, groups_for(section, parent))


def _bucket(model, section, parent):
    qs = model.objects.filter(survey_section=section)
    if model is Question:
        return qs.filter(parent_question_id__isnull=True) if parent is None else qs.filter(parent_question_id=parent)
    return qs.filter(parent_question__isnull=True) if parent is None else qs.filter(parent_question=parent)


def max_order(section, parent=None):
    """Highest order_number over questions AND groups of a bucket, or None."""
    values = [
        _bucket(model, section, parent).aggregate(m=Max('order_number'))['m']
        for model in (Question, QuestionGroup)
    ]
    values = [v for v in values if v is not None]
    return max(values) if values else None


def next_order(section, parent=None):
    """order_number for a new last item of a bucket (a question or a group)."""
    current = max_order(section, parent)
    return 0 if current is None else current + 1


def shift_down(section, parent, after_order):
    """Make room after `after_order`: +1 for every question and group past it."""
    for model in (Question, QuestionGroup):
        _bucket(model, section, parent).filter(order_number__gt=after_order).update(
            order_number=F('order_number') + 1
        )


def last_member_order(group):
    """order_number of a group's last member, or the group's own when empty."""
    m = group.questions.aggregate(m=Max('order_number'))['m']
    return group.order_number if m is None else max(m, group.order_number)
