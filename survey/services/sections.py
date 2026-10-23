"""Sections of a survey: create, edit, delete, reorder, map start."""
from django.contrib.gis.geos import Point
from django.db import transaction

from .. import product_events as pe
from ..editor_forms import SurveySectionForm
from ..models import SurveySection, SurveySectionTranslation
from ..versioning import section_snapshot, structural_edit_message, structural_section_changes
from . import locks
from .common import (
    UNSET, bind, check_rule, guard_answer_loss, locked_changes, save_translations, surface_props,
    validate,
)
from .errors import StructureLocked, ValidationFailed

TRANSLATION_FIELDS = ('title', 'subheading', 'next_label')


def ordered(survey):
    """Sections in linked-list order (head first); orphans at the end."""
    sections = list(SurveySection.objects.filter(survey_header=survey))
    by_id = {s.id: s for s in sections}
    head = next((s for s in sections if s.is_head), None)
    chain, seen = [], set()
    current = head
    while current is not None and current.id not in seen:
        chain.append(current)
        seen.add(current.id)
        current = by_id.get(current.next_section_id)
    chain.extend(s for s in sections if s.id not in seen)
    return chain


def save_translations_for(section, survey, translations):
    save_translations(
        SurveySectionTranslation, 'section', section, survey, translations,
        TRANSLATION_FIELDS, rich=('subheading',), caps={'next_label': 30})


@transaction.atomic
def create(actor, survey, sections=None):
    """Append an empty section ("section_N", code "SN"); the first one is the head.
    `sections` is the caller's already-ordered list, when it has one."""
    locks.assert_structure_editable(survey)
    if sections is None:
        sections = ordered(survey)
    existing_names = {s.name for s in sections}
    count = len(sections) + 1
    while f'section_{count}' in existing_names:
        count += 1
    section = SurveySection.objects.create(
        survey_header=survey,
        name=f'section_{count}',
        title=f'Section {count}',
        code=f'S{count}',
        is_head=(not sections),
    )
    if sections:
        last = sections[-1]
        last.next_section = section
        last.save(update_fields=['next_section'])
        section.prev_section = last
        section.save(update_fields=['prev_section'])
    return section


@transaction.atomic
def update(actor, section, data, *, translations=UNSET, visibility_rule=UNSET,
           partial=False, strict=False):
    """Edit a section's fields (`SurveySectionForm` names), its translations
    (`{lang: {title, subheading, next_label}}`) and its visibility rule.

    Everything is validated before anything is written. On a live survey a
    change of code or visibility rule is structural (StructureLocked); the
    rest is applied in place, measured and re-screened. `strict` (the API):
    rules are checked against the structure, and a posted code that differs
    on a live survey is refused instead of ignored.
    """
    survey = section.survey_header
    locks.assert_content_editable(survey)
    _, structure_locked = locks.locks(survey)
    before = section_snapshot(section)
    form = validate(bind(SurveySectionForm, data, instance=section, partial=partial,
                         lock_structure=structure_locked))
    if visibility_rule is not UNSET:
        check_rule(visibility_rule, 'section', strict, survey=survey, section=section)
    if structure_locked:
        candidate = section.visibility_rule
        if visibility_rule is not UNSET:
            section.visibility_rule = visibility_rule
        reasons = structural_section_changes(before, section)
        if strict:
            reasons += locked_changes(form, data, {'code': 'the section code'})
        section.visibility_rule = candidate
        if reasons:
            raise StructureLocked(structural_edit_message(reasons), reasons=reasons,
                                  draft=locks._draft(survey))
    form.save()
    if visibility_rule is not UNSET:
        section.visibility_rule = visibility_rule
        section.save(update_fields=['visibility_rule'])
    if translations is not UNSET:
        save_translations_for(section, survey, translations)
    if structure_locked:
        pe.emit(pe.LIVE_EDIT_SAVED, actor.user_id,
                {'survey_id': str(survey.id), 'kind': 'section', **surface_props(actor)})
        # Section text now changes on a live page: same screen as the thanks
        # page and redirect URL, the other live text paths.
        locks.rescreen_if_live(survey)
    return section


@transaction.atomic
def delete(actor, section, *, acknowledge_answer_loss=False):
    """Delete a section and everything in it, re-linking its neighbours."""
    survey = section.survey_header
    locks.assert_structure_editable(survey)
    guard_answer_loss(survey, section.answer_count(), acknowledge_answer_loss)
    prev_sec = section.prev_section
    next_sec = section.next_section
    if prev_sec:
        prev_sec.next_section = next_sec
        prev_sec.save(update_fields=['next_section'])
    if next_sec:
        next_sec.prev_section = prev_sec
        next_sec.save(update_fields=['prev_section'])
        if section.is_head:
            next_sec.is_head = True
            next_sec.save(update_fields=['is_head'])
    section.delete()


def _int_ids(raw_ids, field):
    try:
        return [int(i) for i in raw_ids]
    except (TypeError, ValueError):
        raise ValidationFailed.single(field, 'Ids must be integers.')


@transaction.atomic
def reorder(actor, survey, section_ids, *, strict=False):
    """Re-link the sections in the order given. The editor's lenient mode
    skips ids that are not this survey's (a stale list); `strict` (the API)
    refuses them and requires every section exactly once."""
    locks.assert_structure_editable(survey)
    section_ids = _int_ids(section_ids, 'section_ids')
    sections = {s.id: s for s in SurveySection.objects.filter(survey_header=survey)}
    if strict and (sorted(section_ids) != sorted(sections) or len(set(section_ids)) != len(section_ids)):
        raise ValidationFailed.single('section_ids', 'List every section of the survey exactly once.')
    for i, sid in enumerate(section_ids):
        s = sections.get(sid)
        if not s:
            continue
        s.is_head = (i == 0)
        s.prev_section = sections.get(section_ids[i - 1]) if i > 0 else None
        s.next_section = sections.get(section_ids[i + 1]) if i < len(section_ids) - 1 else None
        s.save(update_fields=['is_head', 'prev_section', 'next_section'])


def _number(value, kind, field):
    try:
        return kind(value)
    except (TypeError, ValueError):
        raise ValidationFailed.single(field, 'Enter a number.')


@transaction.atomic
def set_map(actor, section, *, lat=None, lng=None, zoom=None, clear_position=False,
            use_geolocation=False, override_basemap=None):
    """Where this section's map opens, whether it asks for the respondent's
    location, and which basemap it uses instead of the survey's."""
    survey = section.survey_header
    locks.assert_content_editable(survey)
    if clear_position:
        section.start_map_postion = None
        section.start_map_zoom = None
    else:
        lat = _number(52.52 if lat is None else lat, float, 'lat')
        lng = _number(13.405 if lng is None else lng, float, 'lng')
        zoom = _number(12 if zoom is None else zoom, int, 'zoom')
        section.start_map_postion = Point(lng, lat)
        section.start_map_zoom = zoom
    section.use_geolocation = use_geolocation
    section.override_basemap = override_basemap or None
    section.save(update_fields=['start_map_postion', 'start_map_zoom', 'use_geolocation', 'override_basemap'])
    if locks.is_live(survey):
        pe.emit(pe.LIVE_EDIT_SAVED, actor.user_id,
                {'survey_id': str(survey.id), 'kind': 'map', **surface_props(actor)})
    return section
