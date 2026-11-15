"""Answers read as features (change data-catalogue, #667).

The one reader of a collected `answers` dataset: the top-level answers to one geo question
(by code across the survey's version family) within a session scope, as
(session id, answer id, geometry). The public grid (`data.aggregate.grid`), the dataset page and
the API read answers-as-features through here rather than each writing the lineage query.
"""
from data.scope import SessionScope


def question_features(survey, question_code, scope=None):
    """[(session_id, answer_id, GEOSGeometry)] of `question_code` in `survey`'s family.

    `scope` defaults to Responses' view (non-trashed, moderated included); public callers pass
    `SessionScope.public(survey)`."""
    from survey.models import Answer
    from survey.question_types import GEO_TYPES, geo_column
    from survey.versioning import family_ids
    ids = family_ids(survey)
    scope = scope or SessionScope(ids, include_moderated=True)
    out = []
    rows = (Answer.objects
            .filter(question__survey_section__survey_header_id__in=ids, question__code=question_code,
                    question__parent_question_id__isnull=True, question__input_type__in=GEO_TYPES)
            .filter(scope.q('survey_session'))
            .select_related('question'))
    for a in rows:
        geom = getattr(a, geo_column(a.question.input_type))
        if geom is not None:
            out.append((a.survey_session_id, a.id, geom))
    return out
