"""Object lookups every route makes: the survey at a role, gated on Pro, and
nested ids always through that survey (integer ids are IDORs otherwise)."""
from survey.layers import layers_for
from survey.models import Question, SurveySection
from survey.permissions import SURVEY_ROLE_RANK, get_effective_survey_role
from survey.services.context import SURFACE_API, Actor

from .. import gates, rights
from ..errors import FORBIDDEN_ROLE, ApiError, not_found


def actor(request):
    from survey.abuse import client_ip
    return Actor(user=request.principal.user, ip=client_ip(request) or None, surface=SURFACE_API)


def survey(request, uuid, role='viewer'):
    """The survey as the caller may see it, gated on the owning workspace's
    plan. Invisible ⇒ 404; visible but under `role` ⇒ 403 forbidden_role (the
    survey's existence is no secret to someone who can read it)."""
    p = request.principal
    obj = rights.survey_for(p, uuid, min_role='viewer')
    gates.require_pro_api(p, obj.organization)
    have = get_effective_survey_role(p.user, obj)
    if SURVEY_ROLE_RANK.get(have, -1) < SURVEY_ROLE_RANK[role]:
        raise ApiError(403, FORBIDDEN_ROLE, f'This needs the {role} role on the survey; you are {have}.',
                       role=role)
    return obj


def section(request, survey_obj, section_id):
    return rights.section_for(request.principal, survey_obj, section_id)


def question(request, survey_obj, question_id):
    return rights.question_for(request.principal, survey_obj, question_id)


def layer(request, survey_obj, layer_id, with_geojson=False):
    qs = layers_for(survey_obj)
    if with_geojson:
        qs = qs.defer(None)
    obj = qs.filter(pk=layer_id).first()
    if obj is None:
        raise not_found()
    return obj


def layers_list(survey_obj):
    """Metadata only: `layers_for` defers the geometry text (layer memory rules)."""
    return layers_for(survey_obj)


def sections_of(survey_obj):
    return SurveySection.objects.filter(survey_header=survey_obj)


def top_questions(section_obj):
    return Question.objects.filter(survey_section=section_obj, parent_question_id__isnull=True)

