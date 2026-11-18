"""Key numbers a report can take from its survey (change report-key-numbers, #744).

A key number is stored as `{'value', 'label'}`; a value that is one live-number token
(`reports.tokens`) follows the answers. The author never types such a token in a Key numbers
block: a new block arrives with `defaults`, and the editor's menu offers `choices`.
"""
from django.utils.translation import gettext as _

from reports.tokens import TOKEN, Tokens

MAX_MAP_QUESTIONS = 8


def is_live(value):
    """Whether a key number's value is exactly one token: a number picked, not typed."""
    return bool(TOKEN.fullmatch(str(value or '').strip()))


def defaults(map_code=''):
    """The numbers a report most often opens with — who opened, answered and finished, and the
    marks on a map question. One list for the drafted report and for a block added by hand."""
    items = [{'value': '{opened}', 'label': _('opened the survey')},
             {'value': '{responses}', 'label': _('answered')},
             {'value': '{finished}', 'label': _('finished')}]
    if map_code:
        items.append({'value': '{marks:%s}' % map_code, 'label': _('marks on the map')})
    return items


def map_questions(survey):
    """The survey's map questions in survey order, the ones a `{marks:CODE}` number can count."""
    from data.questions import top_level_questions
    from survey.question_types import GEO_TYPES
    return list(top_level_questions(survey, GEO_TYPES))[:MAX_MAP_QUESTIONS]


def defaults_for(survey):
    """`defaults` for a block added to a report of `survey` (canonical)."""
    questions = map_questions(survey)
    return defaults(questions[0].code if questions else '')


def choices(survey, k):
    """What the editor's menu offers: `{'token', 'label', 'detail', 'shown'}` per number of the
    survey, `shown` being its value now (masked under K like everywhere else)."""
    if survey is None:
        return []
    tokens = Tokens(survey, k)
    out = [{'token': item['value'], 'label': item['label'], 'detail': ''} for item in defaults()]
    for question in map_questions(survey):
        out.append({'token': '{marks:%s}' % question.code, 'label': _('marks on the map'),
                    'detail': question.name or question.code})
    for item in out:
        item['shown'] = tokens.fill_plain(item['token'])
    return out
