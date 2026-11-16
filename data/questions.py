"""Questions of a collected dataset, by CODE (change data-analysis-views, #692).

A collected dataset names a canonical survey and codes, never question rows: publishing
unpublished changes replaces the rows. Views and report blocks resolve a code to the question as it
stands today through here.
"""


def questions_of(survey, codes):
    """{code: question} for a canonical survey: the canonical survey's row first, else the newest
    row of any version, else the draft copy's (a block added while editing unpublished changes);
    a top-level question before a sub-question that happens to share the code."""
    from survey.models import Question
    from survey.versioning import draft_copy_of, family_ids
    ids = set(family_ids(survey))
    draft = draft_copy_of(survey)
    draft_id = draft.id if draft is not None else None
    if draft_id is not None:
        ids.add(draft_id)

    def rank(q):
        header_id = q.survey_section.survey_header_id
        # canonical row, then archived versions (newest first: rows come ordered by -id), the
        # draft copy last.
        return (0 if header_id == survey.id else (2 if header_id == draft_id else 1),
                0 if q.parent_question_id_id is None else 1)

    best = {}
    for q in (Question.objects.filter(code__in=list(codes), survey_section__survey_header_id__in=ids)
              .select_related('survey_section__survey_header').order_by('-id')):
        have = best.get(q.code)
        if have is None or rank(q) < rank(have):
            best[q.code] = q
    return best


def question_of(survey, code):
    return questions_of(survey, [code]).get(code) if code else None


def top_level_questions(survey, input_types):
    """The canonical survey's top-level questions of the given types, in survey order — what a
    view form offers."""
    from survey.models import Question, SurveySection
    sections = {s.id: s for s in SurveySection.objects.filter(survey_header=survey)
                .only('id', 'is_head', 'next_section_id')}
    position, current, seen = {}, next((s for s in sections.values() if s.is_head), None), set()
    while current is not None and current.id not in seen:     # the sections' linked list
        seen.add(current.id)
        position[current.id] = len(position)
        current = sections.get(current.next_section_id)
    rows = list(Question.objects
                .filter(survey_section__survey_header=survey, parent_question_id__isnull=True,
                        input_type__in=list(input_types))
                .exclude(code=''))
    rows.sort(key=lambda q: (position.get(q.survey_section_id, len(position)), q.order_number, q.id))
    return rows
