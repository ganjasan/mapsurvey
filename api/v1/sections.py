"""/surveys/{uuid}/sections: the pages of a survey."""
from typing import List
from uuid import UUID

from django.db import transaction
from ninja import Router, Status

from survey.services import sections as svc_sections
from survey.services.common import UNSET

from .. import scopes
from . import deps, forms_bridge, out
from .auth import Bearer
from .docs import errors
from .schemas import SectionIn, SectionOrderIn, SectionOut

router = Router(tags=['Sections'])

READ = Bearer(scopes.SURVEYS_READ)
WRITE = Bearer(scopes.SURVEYS_WRITE)


def _apply(request, section, body):
    """One PATCH-shaped body through the services, strict (rules checked
    against the structure, locked fields refused instead of ignored)."""
    actor = deps.actor(request)
    data = forms_bridge.section(body)
    translations = forms_bridge.translations(body) if 'translations' in body else UNSET
    rule = forms_bridge.visibility(body)
    if data or translations is not UNSET or rule is not UNSET:
        svc_sections.update(actor, section, data, translations=translations, visibility_rule=rule,
                            partial=True, strict=True)
    if 'map_start' in body or 'use_geolocation' in body:
        start = body.get('map_start', out._map_start(section))
        svc_sections.set_map(
            actor, section, clear_position=start is None,
            lat=start and start['lat'], lng=start and start['lng'], zoom=start and start['zoom'],
            use_geolocation=body.get('use_geolocation', section.use_geolocation),
            override_basemap=section.override_basemap)


def _all(survey):
    return [out.section(s, i) for i, s in enumerate(svc_sections.ordered(survey))]


@router.get('/surveys/{uuid}/sections', response=List[SectionOut], auth=READ, openapi_extra=errors())
def list_sections(request, uuid: UUID):
    """The survey's sections in respondent order."""
    return _all(deps.survey(request, uuid))


@router.post('/surveys/{uuid}/sections', response={201: SectionOut}, auth=WRITE, openapi_extra=errors(409))
def create_section(request, uuid: UUID, payload: SectionIn = None):
    """Append a section; the body sets its fields at once."""
    survey = deps.survey(request, uuid, role='editor')
    body = payload.dict(exclude_unset=True) if payload else {}
    with transaction.atomic():
        section = svc_sections.create(deps.actor(request), survey)
        if body:
            _apply(request, section, body)
    section.refresh_from_db()
    return Status(201, out.section(section))


@router.put('/surveys/{uuid}/sections/order', response=List[SectionOut], auth=WRITE,
            openapi_extra=errors(409))
def order_sections(request, uuid: UUID, payload: SectionOrderIn):
    """The new order; list every section exactly once. (Declared before the
    `{section_id}` routes: ninja matches that segment as a string.)"""
    survey = deps.survey(request, uuid, role='editor')
    svc_sections.reorder(deps.actor(request), survey, payload.section_ids, strict=True)
    return _all(survey)


@router.get('/surveys/{uuid}/sections/{section_id}', response=SectionOut, auth=READ, openapi_extra=errors())
def get_section(request, uuid: UUID, section_id: int):
    survey = deps.survey(request, uuid)
    return out.section(deps.section(request, survey, section_id))


@router.patch('/surveys/{uuid}/sections/{section_id}', response=SectionOut, auth=WRITE,
              openapi_extra=errors(409))
def patch_section(request, uuid: UUID, section_id: int, payload: SectionIn):
    """Change the fields the body names. On a live survey wording is applied in
    place; the code and the visibility rule are structure (`409 draft_required`)."""
    survey = deps.survey(request, uuid, role='editor')
    section = deps.section(request, survey, section_id)
    with transaction.atomic():
        _apply(request, section, payload.dict(exclude_unset=True))
    section.refresh_from_db()
    return out.section(section)


@router.delete('/surveys/{uuid}/sections/{section_id}', response={204: None}, auth=WRITE,
               openapi_extra=errors(409, codes=('answers_at_risk',)))
def delete_section(request, uuid: UUID, section_id: int, acknowledge_answer_loss: bool = False):
    """Delete a section with its questions. Answers to them go too: the first
    call answers `409 answers_at_risk` with the count; repeat with
    `acknowledge_answer_loss=true`."""
    survey = deps.survey(request, uuid, role='editor')
    section = deps.section(request, survey, section_id)
    svc_sections.delete(deps.actor(request), section, acknowledge_answer_loss=acknowledge_answer_loss)
    return Status(204, None)
