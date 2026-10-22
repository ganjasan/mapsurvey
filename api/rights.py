"""Effective rights = scope ∩ organisation role ∩ survey role.

Nothing is re-implemented: the survey role comes from
`survey.permissions.get_effective_survey_role`, the same function the editor
views ask. Two rules of this module:

- a survey the user may not see (or may not see at the required level) is a
  404, never a 403 -- `check_survey_access` answers the browser the same way,
  and a token must not be able to enumerate what the browser cannot;
- a section or question is always looked up THROUGH its survey, because their
  ids are integers and a bare `get(id=…)` is an IDOR.
"""
from survey.models import Question, SurveyHeader, SurveySection
from survey.permissions import SURVEY_ROLE_RANK, get_effective_survey_role

from .errors import SCOPE_MISSING, ApiError, not_found


def require_scope(principal, scope):
    if scope not in principal.scopes:
        raise ApiError(403, SCOPE_MISSING, f'This token lacks the {scope} scope.', scope=scope)


def survey_for(principal, uuid, min_role='viewer'):
    """The survey `uuid` as `principal` may see it at `min_role` or above, else 404."""
    survey = (
        SurveyHeader.objects
        .select_related('organization')
        .filter(uuid=uuid, deleted_at__isnull=True)
        .first()
    )
    if survey is None:
        raise not_found()
    if principal.organization is not None and survey.organization_id != principal.organization.pk:
        raise not_found()
    role = get_effective_survey_role(principal.user, survey)
    if role is None or SURVEY_ROLE_RANK.get(role, -1) < SURVEY_ROLE_RANK.get(min_role, 99):
        raise not_found()
    return survey


def section_for(principal, survey, section_id):
    section = SurveySection.objects.filter(pk=section_id, survey_header=survey).first()
    if section is None:
        raise not_found()
    return section


def question_for(principal, survey, question_id):
    question = (
        Question.objects
        .select_related('survey_section')
        .filter(pk=question_id, survey_section__survey_header=survey)
        .first()
    )
    if question is None:
        raise not_found()
    return question
