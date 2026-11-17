"""What a report block reads (change reports-object, #703).

A block about one question names a dataset of the Data module and the question's code. A map block
reads the `answers` dataset of (canonical survey, code); a chart, objects or budget block reads the
survey's `responses` dataset. Nothing here aggregates — `reports.render` does, through `data`.
"""
from data.models import Dataset


def _canonical(question):
    from survey.versioning import canonical_of
    return canonical_of(question.survey_section.survey_header)


def dataset_for(question):
    """The dataset a block about `question` reads, created when the registry has not met it yet
    (rows are otherwise written by the read-time `data.datasets.sync`)."""
    from survey.question_types import GEO_TYPES
    survey = _canonical(question)
    is_geo = question.input_type in GEO_TYPES and question.parent_question_id_id is None and question.code
    if is_geo:
        lookup = dict(kind=Dataset.KIND_ANSWERS, survey=survey, question_code=question.code)
        name = question.name or question.code
    else:
        lookup = dict(kind=Dataset.KIND_RESPONSES, survey=survey, question_code='')
        name = survey.name
    dataset, _created = Dataset.objects.get_or_create(
        **lookup, defaults=dict(organization_id=survey.organization_id, name=(name or '')[:200],
                                privacy_class=Dataset.PRIVACY_AGGREGATED))
    return dataset


# The resolver of a question by code lives in Data (change data-analysis-views): views need it
# too, and Data never imports Reports.
from data.questions import questions_of as _questions_of  # noqa: E402


def question_for(block):
    """The question of `block.question_code` as it stands in the dataset's survey today, or None
    when the code is gone from every version."""
    if not block.dataset_id or not block.question_code or not block.dataset.survey_id:
        return None
    return _questions_of(block.dataset.survey, [block.question_code]).get(block.question_code)


def attach_questions(blocks):
    """Resolve `block.question` for a list of blocks in one pass per source survey, instead of a
    lookup per block. Returns the list."""
    blocks = list(blocks)
    by_survey = {}
    for block in blocks:
        if block.dataset_id and block.question_code and block.dataset.survey_id:
            by_survey.setdefault(block.dataset.survey_id, (block.dataset.survey, set()))[1].add(block.question_code)
    found = {sid: _questions_of(survey, codes) for sid, (survey, codes) in by_survey.items()}
    for block in blocks:
        sid = block.dataset.survey_id if block.dataset_id else None
        block.__dict__['question'] = found.get(sid, {}).get(block.question_code) if block.question_code else None
    return blocks


def source_surveys(report):
    """Canonical surveys the report's blocks read, the home survey first."""
    from survey.models import SurveyHeader
    from survey.versioning import canonical_of
    ids = list(report.blocks.filter(dataset__survey__isnull=False)
               .values_list('dataset__survey_id', flat=True).distinct())
    home = canonical_of(report.survey) if report.survey_id else None
    surveys = {s.id: s for s in SurveyHeader.objects.filter(id__in=ids)}
    out = [home] if home is not None else []
    out += [s for sid, s in surveys.items() if home is None or sid != home.id]
    return out
