"""Quotes picked from the answers (change report-quotes-from-answers, #749).

The Quotes block is still written by the author — a quote is published as it stands in the block —
but the author can take it from the answers instead of copying it out of Responses. This module is
what the block's picker lists, how a picked quote is told from one written by hand, and which
quotes carry contact details. Nothing here writes: `reports.services` stores what it returns.
"""
import re

from django.utils.translation import gettext as _

QUOTE_INPUT_TYPES = ('text', 'text_line')
READABLE_MIN, READABLE_MAX = 30, 320      # what the drafting already offers as candidate quotes
PAGE = 50
SCAN = 2000                               # newest answers read per question: plenty for a report


def normalise(text):
    return ' '.join(str(text or '').split())


def text_questions(survey):
    """The free-text questions of a canonical survey, in survey order."""
    from data.questions import top_level_questions
    return top_level_questions(survey, QUOTE_INPUT_TYPES)


def _answers(survey, code):
    """Normalised texts of the answers to question `code` across the survey's versions, clean
    sessions only, newest first, each text once."""
    from data.scope import SessionScope
    from survey.models import Answer
    from survey.versioning import family_ids
    rows = (Answer.objects
            .filter(question__code=code, question__input_type__in=QUOTE_INPUT_TYPES,
                    question__survey_section__survey_header_id__in=family_ids(survey),
                    parent_answer_id__isnull=True)
            .filter(SessionScope.public(survey).q('survey_session'))
            .exclude(text__isnull=True).exclude(text='')
            .order_by('-id').values_list('text', flat=True)[:SCAN])
    out, seen = [], set()
    for text in rows:
        text = normalise(text)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def answers_for(survey, code, search=''):
    """What the picker lists: (answers, number found). Readable lengths first, newest first
    within each; `search` keeps the answers holding every word typed."""
    words = [w.lower() for w in normalise(search).split() if w]
    texts = [t for t in _answers(survey, code) if all(w in t.lower() for w in words)]
    readable = [t for t in texts if READABLE_MIN <= len(t) <= READABLE_MAX]
    rest = [t for t in texts if not READABLE_MIN <= len(t) <= READABLE_MAX]
    return (readable + rest)[:PAGE], len(texts)


def mark_origins(items, surveys_by_uuid=None):
    """Mark each picked quote `shortened` when its text is no longer one of its question's
    answers; a ref to a survey that cannot be found is dropped (the quote stays, as written by
    hand). Returns the items."""
    from survey.models import SurveyHeader
    cache = {}
    for item in items:
        ref = item.get('ref')
        if not ref:
            item.pop('shortened', None)
            continue
        key = (ref['survey'], ref['question'])
        if key not in cache:
            survey = (surveys_by_uuid or {}).get(ref['survey'])
            if survey is None:
                survey = SurveyHeader.objects.filter(uuid=ref['survey'], deleted_at__isnull=True).first()
            cache[key] = set(_answers(survey, ref['question'])) if survey is not None else None
        answers = cache[key]
        if answers is None:
            item.pop('ref', None)
            item.pop('shortened', None)
        elif normalise(item.get('text')) in answers:
            item.pop('shortened', None)
        else:
            item['shortened'] = True
    return items


EMAIL = re.compile(r'[\w.+-]+@[\w-]+(\.[\w-]+)+')
URL = re.compile(r'(https?://|www\.)\S+|\b[\w-]+\.(com|org|net|io|co|de|fr|uk|ru|info|gov|edu)\b', re.I)
PHONE = re.compile(r'(?<![\w])\+?(\d[\s.\-()]{0,2}){7,}')


def contact_flags(text):
    """What a quote carries that can reach a person: a subset of ('email', 'phone', 'url')."""
    text = str(text or '')
    flags = []
    if EMAIL.search(text):
        flags.append('email')
    if PHONE.search(EMAIL.sub('', text)):
        flags.append('phone')
    if URL.search(EMAIL.sub('', text)):
        flags.append('url')
    return flags


def flag_label(flags):
    names = {'email': _('an email address'), 'phone': _('a phone number'), 'url': _('a web address')}
    return ', '.join(str(names[f]) for f in flags)
