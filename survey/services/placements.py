"""Where a survey's reference layers show: the ONE write path for `LayerPlacement`
(change map-layers-study-area, spec map-layer-placement).

The Map card in Build, Survey settings' "Layers used here", the Objects question save, REST v1
and the MCP server all call these functions. A placement belongs to the CANONICAL survey and
names sections by reference (`survey.section_refs`), so every function resolves the owner first
and works the same whether it is handed the live survey, its unpublished changes or a version.

Placement is a SAFE edit (design D2): it collects nothing, so it applies in place on a published
survey and never creates unpublished changes. Refusals are `ValidationFailed` with the field.
"""
from django.db import transaction
from django.db.models import Max

from ..audit import record as audit_record
from ..layers import layer_owner, layers_for, placement_covers
from ..models import LayerPlacement, SurveyHeader, SurveySection
from ..section_refs import refs_for, split
from .errors import ValidationFailed

SCOPES = (LayerPlacement.SCOPE_ALL, LayerPlacement.SCOPE_SECTIONS)


def _audit(actor, action, owner, **meta):
    if actor is not None:
        audit_record(actor, action, owner, **meta)


def _family_headers(owner):
    """The canonical survey and its unpublished changes: where a placed section may live."""
    return [owner.pk] + list(SurveyHeader.objects.filter(published_version=owner).values_list('pk', flat=True))


def map_section_refs(survey):
    """{ref: section} of the map sections of `survey` itself, in survey order."""
    refs = refs_for(survey.pk)
    out = {}
    for section in SurveySection.objects.filter(survey_header=survey).order_by('id'):
        if section.has_map:
            out[refs[section.pk]] = section
    return out


def _clean_refs(owner, sections):
    """Section references as stored: strings, de-duplicated, each naming a map section of the
    canonical survey or of its unpublished changes."""
    if not isinstance(sections, (list, tuple)):
        raise ValidationFailed.single('sections', 'Sections must be a list of section references.')
    known = set()
    for header_id in _family_headers(owner):
        header = SurveyHeader(pk=header_id)
        known |= {split(r) for r in map_section_refs(header)}
    out = []
    for ref in sections:
        ref = str(ref or '').strip()
        if not ref:
            continue
        if split(ref) not in known:
            raise ValidationFailed.single('sections', f'"{ref}" is not a section with a map in this survey.')
        if split(ref) not in {split(r) for r in out}:
            out.append(ref)
    return out


def _reachable_layer(owner, layer_id):
    layer = layers_for(owner).filter(pk=layer_id).first()
    if layer is None:
        raise ValidationFailed.single(
            'layer', f'Layer {layer_id} is not linked to this survey. Add it to the survey first.')
    return layer


def get(survey, layer_id):
    return LayerPlacement.objects.filter(survey=layer_owner(survey), layer_id=layer_id).first()


def place(actor, survey, layer_id, scope=LayerPlacement.SCOPE_ALL, sections=None, automatic=False):
    """Put a linked or owned layer on the survey's maps (or change where it already shows).
    Returns the placement."""
    owner = layer_owner(survey)
    _reachable_layer(owner, layer_id)
    if scope not in SCOPES:
        raise ValidationFailed.single('scope', 'Scope must be "all" or "sections".')
    refs = _clean_refs(owner, sections or []) if scope == LayerPlacement.SCOPE_SECTIONS else []
    if scope == LayerPlacement.SCOPE_SECTIONS and not refs:
        raise ValidationFailed.single('sections', 'Pick at least one section, or remove the layer from the map.')
    with transaction.atomic():
        placement = (LayerPlacement.objects.select_for_update()
                     .filter(survey=owner, layer_id=layer_id).first())
        if placement is None:
            position = (LayerPlacement.objects.filter(survey=owner).aggregate(m=Max('position'))['m'] or 0) + 1
            placement = LayerPlacement.objects.create(survey=owner, layer_id=layer_id, scope=scope,
                                                      sections=refs, position=position)
            action = 'layer_place'
        else:
            placement.scope, placement.sections = scope, refs
            placement.save(update_fields=['scope', 'sections'])
            action = 'layer_place_scope'
    _audit(actor, action, owner, layer_id=layer_id, scope=scope, sections=refs, automatic=automatic)
    if actor is not None:
        from ..product_events import LAYER_PLACED, emit
        emit(LAYER_PLACED, actor.user_id, {'survey_id': owner.pk, 'layer_id': layer_id, 'scope': scope,
                                          'automatic': automatic, 'surface': actor.surface})
    return placement


def unplace(actor, survey, layer_id):
    """Take a layer off every map of the survey (it stays linked). Returns whether one was removed."""
    owner = layer_owner(survey)
    deleted, _ = LayerPlacement.objects.filter(survey=owner, layer_id=layer_id).delete()
    if deleted:
        _audit(actor, 'layer_unplace', owner, layer_id=layer_id)
    return bool(deleted)


def set_on_section(actor, survey, layer_id, section, on):
    """The Map card's tick for one section: add or drop that section from the layer's placement.
    Unticking a layer placed on every section keeps it on all the other map sections of `survey`;
    unticking the last section removes the placement."""
    from ..section_refs import section_ref
    owner = layer_owner(survey)
    if not section.has_map:
        raise ValidationFailed.single('section', 'This section has no map.')
    ref = section_ref(section)
    placement = get(owner, layer_id)
    if on:
        if placement is None:
            return place(actor, survey, layer_id, LayerPlacement.SCOPE_SECTIONS, [ref])
        if placement_covers(placement, ref):
            return placement
        return place(actor, survey, layer_id, LayerPlacement.SCOPE_SECTIONS, list(placement.sections or []) + [ref])
    if placement is None or not placement_covers(placement, ref):
        return placement
    if placement.scope == LayerPlacement.SCOPE_ALL:
        rest = [r for r in map_section_refs(section.survey_header) if split(r) != split(ref)]
    else:
        rest = [r for r in placement.sections if split(r) != split(ref)]
    if not rest:
        unplace(actor, survey, layer_id)
        return None
    return place(actor, survey, layer_id, LayerPlacement.SCOPE_SECTIONS, rest)


def ensure_on_section(actor, survey, layer_id, section):
    """An Objects question or a budget asks about this layer here: make sure the section's map
    shows it (design D3). Nothing changes when a placement already covers the section."""
    if not section.has_map:
        return get(survey, layer_id)
    return set_on_section(actor, survey, layer_id, section, True)


def reorder(actor, survey, layer_ids):
    """Stacking order of the placed layers: every placed layer exactly once."""
    owner = layer_owner(survey)
    current = list(LayerPlacement.objects.filter(survey=owner).values_list('layer_id', flat=True))
    layer_ids = [int(i) for i in layer_ids]
    if sorted(current) != sorted(layer_ids) or len(set(layer_ids)) != len(layer_ids):
        raise ValidationFailed.single('layer_ids', 'Give every layer on the map exactly once.')
    with transaction.atomic():
        for position, pk in enumerate(layer_ids, start=1):
            LayerPlacement.objects.filter(survey=owner, layer_id=pk).update(position=position)
    _audit(actor, 'layer_place_reorder', owner, layer_ids=layer_ids)


def describe(placement, survey):
    """Plain data for a placement: what the Map card, the publish check, REST and MCP show."""
    names = []
    if placement.scope == LayerPlacement.SCOPE_SECTIONS:
        by_ref = map_section_refs(survey)
        for ref in placement.sections or []:
            section = next((s for r, s in by_ref.items() if split(r) == split(ref)), None)
            names.append(section.title or section.name if section else ref)
    return {'layer_id': placement.layer_id, 'scope': placement.scope,
            'sections': list(placement.sections or []), 'section_names': names,
            'position': placement.position}
