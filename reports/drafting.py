"""A report drafted by rules, and a copy of an earlier one (change reports-start, #705).

"Show me something already — I'd rather fix than build." A draft is made from a survey by rules
written from the reports made by hand, never by a model: who took part first, then one fitting
block for every question people answered, in survey order, with the survey's sections as the
story's sections; free-text questions arrive as quotes to pick from, hidden until the author has
chosen. A template is an arrangement of the same draft for a job.

Nothing drafted is published: the report arrives unpublished and unlisted. Text the author has to
write arrives as hidden blocks holding a prompt, so a half-finished draft never shows a
placeholder to a visitor.
"""
from collections import OrderedDict

from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from reports.models import Report, ReportBlock
from reports.render import TEXT_INPUT_TYPES, block_type_for_question, bump_version, unique_slug

TEMPLATES = OrderedDict([
    ('summary', {'label': gettext_lazy('Consultation summary'),
                 'what': gettext_lazy('Who took part, then every question in the survey\'s order, quotes to pick from.')}),
    ('council', {'label': gettext_lazy('Council paper'),
                 'what': gettext_lazy('Numbered sections, results as tables, a place for recommendations.')}),
    ('update', {'label': gettext_lazy('Engagement update'),
                'what': gettext_lazy('Short and live while the survey is open: the numbers, the maps, a link to take part.')}),
    ('yousaid', {'label': gettext_lazy('You said — we did'),
                 'what': gettext_lazy('Each result followed by a place to say what was done about it.')}),
])
MAX_CANDIDATE_QUOTES = 8
QUOTE_MIN, QUOTE_MAX = 30, 320


class _Draft:
    """Blocks appended in order to a new report."""

    def __init__(self, report):
        self.report, self.order = report, 0

    def add(self, block_type, **fields):
        block = ReportBlock.objects.create(report=self.report, block_type=block_type, order=self.order, **fields)
        self.order += 1
        return block

    def heading(self, text):
        return self.add('heading', content={'en': str(text)[:300]})

    def prompt(self, text):
        """A hidden Text block telling the author what to write here."""
        return self.add('text', content={'en': '<p><em>%s</em></p>' % text}, is_hidden=True)

    def numbers(self, items, note=''):
        from reports.story import clean_config
        return self.add('numbers', config=clean_config('numbers', {'items': items}), content={'en': note})

    def question(self, question, **fields):
        block_type = block_type_for_question(question)
        if block_type == 'map':
            from reports.services import new_map_config
            fields.setdefault('config', new_map_config())
        return self.add(block_type, question=question, **fields)


def _answered(survey):
    """{question code: answers} of the survey's family in the public scope."""
    from django.db.models import Count
    from data.scope import SessionScope
    from survey.models import Answer
    from survey.versioning import family_ids
    rows = (Answer.objects
            .filter(question__survey_section__survey_header_id__in=family_ids(survey),
                    question__parent_question_id__isnull=True)
            .filter(SessionScope.public(survey).q('survey_session'))
            .values('question__code').annotate(n=Count('id')).values_list('question__code', 'n'))
    return dict(rows)


def _questions(survey):
    """The canonical survey's top-level questions that people answered, in respondent order, each
    with `.kind` — a block type, or 'quotes' for free text."""
    from data.questions import top_level_questions
    from survey.models import Question
    types = [t for t, _label in Question._meta.get_field('input_type').choices]
    answered = _answered(survey)
    out = []
    for question in top_level_questions(survey, types):
        if not answered.get(question.code):
            continue
        if question.input_type in TEXT_INPUT_TYPES:
            question.kind = 'quotes'
        else:
            question.kind = block_type_for_question(question)
        if question.kind:
            out.append(question)
    return out


def _candidate_quotes(survey, question):
    """Up to eight answers to a free-text question for the author to pick from: the most recent
    ones of a readable length, from clean sessions."""
    from data.scope import SessionScope
    from survey.models import Answer
    from survey.versioning import family_ids
    rows = (Answer.objects
            .filter(question__code=question.code, question__input_type=question.input_type,
                    question__survey_section__survey_header_id__in=family_ids(survey))
            .filter(SessionScope.public(survey).q('survey_session'))
            .exclude(text__isnull=True).exclude(text='')
            .order_by('-id').values_list('text', flat=True)[:200])
    picked = []
    for text in rows:
        text = ' '.join(str(text).split())
        if QUOTE_MIN <= len(text) <= QUOTE_MAX and text not in picked:
            picked.append(text)
        if len(picked) == MAX_CANDIDATE_QUOTES:
            break
    return [{'text': text, 'source': (question.name or '')[:160]} for text in picked]


def _quotes_block(draft, survey, question):
    from reports.story import clean_config
    items = _candidate_quotes(survey, question)
    if not items:
        return None
    # Hidden: a quote reaches the page only after the author picked it (owner, 2026-11-16).
    return draft.add('quotes', config=clean_config('quotes', {'items': items}), is_hidden=True,
                     custom_title={'en': (question.name or '')[:300]})


def _section_title(question):
    section = question.survey_section
    return (section.title or section.name or '').strip()


def _key_numbers(draft, questions):
    from reports.numbers import defaults
    geo = next((q for q in questions if q.kind == 'map'), None)
    return draft.numbers(defaults(geo.code if geo is not None else ''))


def _summary(draft, survey, questions):
    from reports import services
    _key_numbers(draft, questions)
    services.add_view_block(draft.actor, draft.report, 'engagement', survey)
    draft.order += 1
    sections = []
    for q in questions:
        title = _section_title(q)
        if title not in sections:
            sections.append(title)
    current = None
    for q in questions:
        title = _section_title(q)
        if len(sections) > 1 and title != current and title:
            draft.heading(title)
            draft.prompt(_('Write what this part of the survey showed.'))
        current = title
        if q.kind == 'quotes':
            _quotes_block(draft, survey, q)
        else:
            draft.question(q)
    draft.heading(_('What happens next'))
    draft.prompt(_('Say what will be done with these answers, and when.'))


def _council(draft, survey, questions):
    from reports import services
    draft.heading(_('1. Background'))
    draft.prompt(_('Why the survey was run, who ran it and when.'))
    draft.heading(_('2. Who took part'))
    services.add_view_block(draft.actor, draft.report, 'engagement', survey)
    draft.order += 1
    draft.heading(_('3. What residents said'))
    for q in questions:
        if q.kind == 'chart':
            draft.question(q, viz='table')
        elif q.kind == 'quotes':
            _quotes_block(draft, survey, q)
        elif q.kind != 'map':
            draft.question(q)
    maps = [q for q in questions if q.kind == 'map']
    number = 4
    if maps:
        draft.heading(_('4. Places'))
        for q in maps:
            draft.question(q)
        number = 5
    draft.heading(_('%(n)s. Recommendations') % {'n': number})
    draft.prompt(_('What the council is asked to decide.'))


def _update(draft, survey, questions):
    from reports import services
    _key_numbers(draft, questions)
    services.add_view_block(draft.actor, draft.report, 'engagement', survey)
    draft.order += 1
    for q in questions:
        if q.kind == 'map':
            draft.question(q)


def _yousaid(draft, survey, questions):
    for q in questions:
        if q.kind == 'quotes':
            continue
        draft.heading(_('You said: %(question)s') % {'question': q.name or q.code})
        draft.question(q)
        draft.prompt(_('We did: say what was done about it.'))


_BUILDERS = {'summary': _summary, 'council': _council, 'update': _update, 'yousaid': _yousaid}
_TITLES = {
    'summary': gettext_lazy('%(survey)s: what we heard'),
    'council': gettext_lazy('%(survey)s: consultation report'),
    'update': gettext_lazy('%(survey)s: update'),
    'yousaid': gettext_lazy('%(survey)s: you said, we did'),
}


def build_draft(actor, survey, template='summary'):
    """A new, unpublished report of `survey` arranged by `template`. The survey's first report
    (the one its Public results tab opens) is left as it is."""
    from django.db import transaction
    from survey.versioning import canonical_of
    if template not in TEMPLATES:
        template = 'summary'
    survey = canonical_of(survey)
    title = str(_TITLES[template] % {'survey': survey.name})[:200]
    with transaction.atomic():
        report = Report.objects.create(
            organization_id=survey.organization_id, survey=survey, slug=unique_slug(title),
            intro={'title': {'en': title},
                   'body': {'en': str(_('{responses} people answered. This is what they said.'))}},
            visibility='unlisted', is_published=False, template=template,
            show_participate_cta=(template == 'update'), show_response_count=False,
            scaffolded_at=timezone.now(), created_by=actor.user)
        draft = _Draft(report)
        draft.actor = actor
        _BUILDERS[template](draft, survey, _questions(survey))
        # Blocks made through services took their own order; number everything once.
        for index, block in enumerate(report.blocks.order_by('order', 'id')):
            if block.order != index:
                ReportBlock.objects.filter(pk=block.pk).update(order=index)
        bump_version(report)
    return report


def copy_report(actor, report, onto=None):
    """A second report with the same opening and blocks, unpublished and workspace-only — the
    report file's own round trip, so a copy can never drift from an export and an import.

    `onto` (change reports-reuse, #711) points the copy at another survey of the workspace: the
    next round. Returns the copy; `copy.copy_notes` names the blocks that found no question."""
    import io
    from reports.files import export_report, import_report
    from survey import product_events as pe
    from survey.versioning import canonical_of
    if onto is not None:
        onto = canonical_of(onto)
    _name, data = export_report(report)
    copy, notes = import_report(actor, report.organization, io.BytesIO(data), onto=onto)
    intro = dict(copy.intro or {})
    intro['title'] = {'en': str(_('%(title)s (copy)') % {'title': report.title})[:200]}
    copy.intro = intro
    copy.template = report.template
    copy.k_anonymity_threshold = report.k_anonymity_threshold
    copy.save(update_fields=['intro', 'template', 'k_anonymity_threshold', 'updated_at'])
    copy.copy_notes = notes
    pe.emit(pe.REPORT_REUSED, getattr(actor.user, 'pk', None), {
        'source': str(report.pk), 'report': str(copy.pk), 'onto': onto is not None,
        'blocks': copy.blocks.count(), 'unmatched': len(notes) if onto is not None else 0})
    return copy
