"""Surveys: create, settings, name, thanks page, map start, trash."""
import json

from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils.translation import gettext as _

from .. import audit
from .. import product_events as pe
from ..editor_forms import SurveyCreateForm, SurveyHeaderForm, SurveyRenameForm
from ..html_sanitize import sanitize_creator_html
from ..models import SurveyCollaborator, SurveySection
from .. import schedule
from ..trash import trash_survey
from . import locks
from .common import bind, validate
from .errors import Conflict, ValidationFailed


@transaction.atomic
def create(actor, survey, organization, *, start=None, surface):
    """Save an unsaved `SurveyHeader` as a new survey a creator can work on:
    the owner collaborator, the head section, `survey_created`.

    `start` is a `map_start` result (lat, lng, zoom, source) or None;
    `surface` names where the survey was made (`start_blank`, `create_page`,
    `api`). Names only reach PostHog, never coordinates.
    """
    survey.organization = organization
    survey.created_by = actor.user
    if start is not None:
        survey.start_map_postion = Point(start.lng, start.lat)
        survey.start_map_zoom = start.zoom
    survey.save()
    # `creation_method` is what makes the AI generator measurable: every
    # historical survey is `manual` by definition, so this is the baseline its
    # variant gets compared against.
    pe.emit(pe.SURVEY_CREATED, actor.user_id, {
        'survey_id': str(survey.id),
        'creation_method': pe.CREATION_MANUAL,
        'surface': surface,
        'map_source': start.source if start is not None else '',
    })
    SurveyCollaborator.objects.create(user=actor.user, survey=survey, role='owner')
    SurveySection.objects.create(
        survey_header=survey, name='section_1', title='Section 1', code='S1', is_head=True,
    )
    return survey


def create_blank(actor, organization, *, name, language, start=None, surface):
    """A new empty survey named `name` in `language` -- what a programmatic
    client gets from `POST /surveys`."""
    form = validate(SurveyCreateForm(
        {'name': (name or '').strip(), 'available_languages': json.dumps([language])}))
    return create(actor, form.save(commit=False), organization, start=start, surface=surface)


@transaction.atomic
def update_settings(actor, survey, data, files=None, *, partial=False):
    """The Settings form: name, redirect, languages, visibility, cover,
    basemaps, branding, style. `redirect_url` reaches the row only through the
    form's `clean_redirect_url`. Re-screened when live."""
    locks.assert_settings_editable(survey)
    form = validate(bind(SurveyHeaderForm, data, files, instance=survey, partial=partial))
    # Switching the badge off without the plan spends one Pro-trial switch-off
    # (change pro-trial-allowances) -- or starts the workspace's trial with it
    # (change pro-trial-auto). Inside this transaction, so a refused save gives
    # the use back and leaves no trial behind.
    if form.consumes_unbranded():
        from billing import trial
        if not trial.use(survey.organization, 'unbranded', actor=actor.user):
            form.add_error('show_branding', _('Your Pro trial has used its switch-off of the badge.'))
            raise ValidationFailed(form.errors, form=form)
    form.save()
    # The period belongs to the live survey even when the form was bound to the
    # draft copy (change survey-schedule).
    schedule.move_to_canonical(survey)
    locks.rescreen_if_live(survey)
    return survey


@transaction.atomic
def rename(actor, survey, data):
    """The name and nothing else. A draft copy has no name of its own: its
    header names the published survey."""
    if survey.is_draft_copy:
        raise Conflict('A draft is renamed by renaming the published survey.')
    validate(SurveyRenameForm(data, instance=survey)).save()
    return survey


@transaction.atomic
def set_thanks(actor, survey, html_by_lang, *, show_on_thanks=None, languages=None):
    """The thanks page, per language, through the creator-HTML allow-list.
    `languages` limits which languages are written (default: all of the
    survey's, the editor's full form); the rest keep their text.
    `show_on_thanks` (None = untouched) is the results page's toggle."""
    locks.assert_settings_editable(survey)
    langs = list(survey.available_languages) or ['en']
    existing = survey.thanks_html or {}
    if isinstance(existing, str):
        existing = {langs[0]: existing}
    thanks = {} if languages is None else {k: v for k, v in existing.items() if k in langs}
    written = langs if languages is None else [lang for lang in languages if lang in langs]
    for lang in written:
        cleaned = sanitize_creator_html(html_by_lang.get(lang, '') or '')
        if cleaned:
            thanks[lang] = cleaned
        else:
            thanks.pop(lang, None)
    survey.thanks_html = thanks
    survey.save(update_fields=['thanks_html'])
    # Source hashes (change translation-table) for the translated pages whose
    # text changed; the primary page is the source.
    from .. import translation_table
    for lang in written:
        if lang != langs[0] and thanks.get(lang, '') != existing.get(lang, ''):
            translation_table.record_hashes(survey, lang, [
                (translation_table.THANKS_KEY, thanks.get(langs[0], ''), translation_table.RICH, thanks.get(lang, ''))])
    locks.rescreen_if_live(survey)
    results_page = getattr(survey, 'public_results_page', None)
    if results_page is not None and show_on_thanks is not None:
        results_page.show_on_thanks = bool(show_on_thanks)
        results_page.save(update_fields=['show_on_thanks'])
    return survey


def _number(value, kind, field):
    try:
        return kind(value)
    except (TypeError, ValueError):
        raise ValidationFailed.single(field, 'Enter a number.')


@transaction.atomic
def set_map_position(actor, survey, *, lat=None, lng=None, zoom=None, clear_position=False,
                     use_geolocation=False):
    """Where the survey's map opens and whether it asks for the respondent's location."""
    locks.assert_settings_editable(survey)
    if clear_position:
        survey.start_map_postion = None
        survey.start_map_zoom = None
    else:
        lat = _number(52.52 if lat is None else lat, float, 'lat')
        lng = _number(13.405 if lng is None else lng, float, 'lng')
        zoom = _number(12 if zoom is None else zoom, int, 'zoom')
        survey.start_map_postion = Point(lng, lat)
        survey.start_map_zoom = zoom
    survey.use_geolocation = use_geolocation
    survey.save(update_fields=['start_map_postion', 'start_map_zoom', 'use_geolocation'])
    return survey


@transaction.atomic
def trash(actor, survey):
    """Move a survey to the trash: recoverable for TRASH_RETENTION_DAYS."""
    trash_survey(survey)
    audit.record(actor, 'survey_trash', survey)
    return survey
