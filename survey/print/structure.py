"""The respondent structure a paper form is printed from — and read back against.

`plan_items(survey, language)` is the ONE walk shared by `pdf.build_form` (what
goes on paper) and `survey/paper/extract.py` (what a photographed page is read
against, change paper-photo-entry, #495): sections in chain order, `group_runs`,
the `respondent` surface of the visibility engine, audience-hidden items left
out. Two walks would drift — a question printed but never read, or read but
never printed — so neither module has its own.
"""
from survey.groups import group_runs, groups_for
from survey.models import FILE_INPUT_TYPES
from survey.question_types import SURFACE_RESPONDENT
from survey.services.sections import ordered
from survey.visibility import compute_visibility


def plan_items(survey, language):
    """[(section, [(group | None, [question, ...]), ...]), ...] for the respondent surface."""
    vmap = compute_visibility(survey, {}, surface=SURFACE_RESPONDENT)
    hidden = vmap.audience_hidden
    plan = []
    for section in ordered(survey):
        if ('section', section.id) in hidden:
            continue
        runs = []
        for group, members in group_runs(section.questions(), groups_for(section)):
            if group is not None and ('group', group.id) in hidden:
                continue
            # A file question has no paper form: nothing can be answered on it, and
            # the "Online only" stub only took space (owner, 2026-11-01).
            members = [q for q in members if ('question', q.id) not in hidden and q.input_type not in FILE_INPUT_TYPES]
            if group is None and not members:
                continue
            runs.append((group, members))
        plan.append((section, runs))
    return plan


def mark_letters(geo_questions):
    """The legend letter of each geo question of one section, in section order:
    A, B, … Z, AA, BB — printed in the legend and on the sub-question table rows
    (A1, A2 …), and what a photographed mark is labelled with when it is read
    back (survey/paper/marks.py). One function, so paper and reader agree."""
    import string
    return [string.ascii_uppercase[i % 26] * (1 + i // 26) for i in range(len(geo_questions))]


def item_keys(plan):
    """The `section:` / `group:` / `question:` keys of a plan, in drawing order —
    the vocabulary `PrintedForm.layout[page]["items"]` is written in."""
    keys = []
    for section, runs in plan:
        keys.append(f'section:{section.code}')
        for group, members in runs:
            if group is not None:
                keys.append(f'group:{group.code}')
            keys.extend(f'question:{q.code}' for q in members)
    return keys
