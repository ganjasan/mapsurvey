"""What may be edited on a survey right now (change edit-live-survey, moved
here from editor_views by rest-api-v1).

A published/closed survey takes SAFE edits in place and refuses STRUCTURAL
ones, which belong on its unpublished changes. While unpublished changes
exist, nothing on the live survey may be edited, because publishing them
replaces the live structure and settings and would silently drop the edit.
"""
from ..content_screening import screen_survey
from ..versioning import draft_copy_of, is_live, live_editing_enabled
from .errors import ContentLocked, StructureLocked

STRUCTURE_LOCKED_MESSAGE = 'Structural edits are not allowed on published or closed surveys'
DRAFT_SHADOWS_CONTENT_MESSAGE = (
    'This survey has unpublished changes. Edit those instead, so that '
    'publishing them does not overwrite this edit.')
READ_ONLY_MESSAGE = 'Edits are not allowed on published or closed surveys'
DRAFT_SHADOWS_SETTINGS_MESSAGE = (
    'This survey has unpublished changes. Edit its settings there, so that '
    'publishing them does not overwrite this edit.')


def locks(survey):
    """(content_locked, structure_locked) -- the editor's (is_read_only,
    structure_locked).

    `structure_locked`: adding, deleting, reordering, pasting, type/visibility
    changes are refused -- every live survey. `content_locked`: nothing at all
    may be edited -- a live survey with the switch off (the pre-change
    behaviour), or one that has unpublished changes.
    """
    if not is_live(survey):
        return False, False
    if not live_editing_enabled() or survey.has_draft_copy():
        return True, True
    return False, True


def _draft(survey):
    return None if survey.is_draft_copy else draft_copy_of(survey)


def assert_content_editable(survey):
    """Raise ContentLocked unless safe (non-structural) edits may be saved now."""
    content_locked, _ = locks(survey)
    if not content_locked:
        return
    if live_editing_enabled() and survey.has_draft_copy():
        raise ContentLocked(DRAFT_SHADOWS_CONTENT_MESSAGE, draft=_draft(survey))
    raise ContentLocked(READ_ONLY_MESSAGE)


def assert_structure_editable(survey):
    """Raise StructureLocked for a structural operation (add, delete, reorder,
    paste) on a live survey. Status-based on purpose: the editor routes such
    operations to the unpublished changes before the request is ever sent."""
    if survey.status in ('published', 'closed'):
        raise StructureLocked(STRUCTURE_LOCKED_MESSAGE, draft=_draft(survey) if is_live(survey) else None)


def assert_settings_editable(survey):
    """Raise ContentLocked when the live survey's settings are about to be
    replaced anyway: publish_draft() copies languages, visibility, redirect,
    thanks page and map start from the draft onto the canonical survey.
    Narrower than assert_content_editable on purpose: settings and the thanks
    page stay editable on a plain live survey, as they always were."""
    if live_editing_enabled() and is_live(survey) and survey.has_draft_copy():
        raise ContentLocked(DRAFT_SHADOWS_SETTINGS_MESSAGE, draft=_draft(survey))


def rescreen_if_live(survey):
    """Creator text edited on a published survey goes live at once, so it is
    screened again (spec survey-content-screening)."""
    if survey.status == 'published':
        screen_survey(survey, trigger='live_edit')
