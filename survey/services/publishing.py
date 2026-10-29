"""The survey lifecycle: status transitions and unpublished changes.

`transition` is the publishing widget's one action (draft ⇄ testing →
published ⇄ closed → archived). The unpublished-changes trio --
`create_draft`, `publish_draft`, `discard_draft` -- plus `restore_version`
wrap `versioning.py`, which holds the cloning and the version swap; what
lives here is everything around it: translation gaps, test-data cleanup,
the audit trail, product events, the public results scaffold and content
screening.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from django.db import transaction

from .. import audit
from .. import product_events as pe
from ..content_screening import pending_review_for, screen_survey
from ..models import SurveyHeader, SurveySession
from ..public_results import scaffold_page
from ..translation_gaps import survey_translation_gaps
from ..versioning import IncompatibleDraftError, clone_survey_for_draft, publish_draft as _publish_draft
from .common import surface_props
from .errors import Conflict, EmailUnconfirmed, IncompatibleDraft, TransitionRefused, TranslationGaps

logger = logging.getLogger(__name__)


@dataclass
class Published:
    """What a publish leaves behind: the live survey and whether content
    screening held it ('pending') -- the caller is told, respondents see the
    unavailable page until the owner decides."""
    survey: SurveyHeader
    review: Optional[str] = None


def review_state(survey):
    return 'pending' if pending_review_for(survey) is not None else None


def _check_translation_gaps(survey, acknowledged):
    """Publishing with holes is allowed, but never silently -- the
    respondent-side fallback would mask them."""
    if not acknowledged:
        gaps = survey_translation_gaps(survey)
        if gaps:
            raise TranslationGaps(gaps)


def _require_confirmed_email(actor):
    """Nothing goes live from an unconfirmed address (change login-grace-period):
    an account may build during its grace period but not publish. Checked
    before every other publish rule, so the refusal names the real blocker."""
    from ..email_verification import is_verified
    if actor.user is not None and not is_verified(actor.user):
        raise EmailUnconfirmed()


def transition(actor, survey, status, *, acknowledge_translation_gaps=False, clear_test_data=False,
               refuse_draft_copy=False):
    """Move `survey` to `status` along `VALID_TRANSITIONS`.

    `refuse_draft_copy` (the API): unpublished changes are published with
    `publish_draft`, never by changing their own status.
    """
    if refuse_draft_copy and survey.is_draft_copy:
        raise Conflict('These are unpublished changes; publish them with draft/publish.')
    if status == 'published':
        _require_confirmed_email(actor)
    can, error = survey.can_transition_to(status)
    if not can:
        raise TransitionRefused(error)
    if status == 'published':
        _check_translation_gaps(survey, acknowledge_translation_gaps)

    with transaction.atomic():
        if survey.status == 'testing' and status == 'published' and clear_test_data:
            deleted_count, _ignored = SurveySession.objects.filter(survey=survey).delete()
            audit.record(actor, 'clear_test_data', survey, deleted_sessions=deleted_count)

        audit.record(actor, 'status_transition', survey, old_status=survey.status, new_status=status)
        survey.status = status
        if status == 'archived':
            survey.is_archived = True
        survey.save(update_fields=['status', 'is_archived'])

    if status != 'published':
        return Published(survey)
    # The real publish moment, attributed to the survey's creator (the funnel
    # follows creators, not whoever pressed the button).
    pe.emit(pe.SURVEY_PUBLISHED, survey.created_by_id, {
        'survey_id': str(survey.id),
        'creation_method': pe.creation_method_for(survey.id),
        **surface_props(actor),
    })
    # A failed scaffold must never block the publish itself -- worst case is
    # no results page draft, and the config tab retries later.
    try:
        scaffold_page(survey)
    except Exception:
        logger.exception('public results scaffold failed for survey %s', survey.id)
    # Phishing screening: may HOLD the survey until the owner decides. Fails
    # open inside, never blocks.
    screen_survey(survey, trigger='publish')
    return Published(survey, review_state(survey))


def create_draft(actor, survey, *, then=''):
    """Start unpublished changes on a published or closed survey."""
    if survey.status not in ('published', 'closed'):
        raise TransitionRefused('Only published or closed surveys can have draft copies')
    if survey.has_draft_copy():
        raise Conflict('A draft already exists for this survey')
    draft = clone_survey_for_draft(survey)
    pe.emit(pe.UNPUBLISHED_CHANGES_STARTED, actor.user_id, {
        'survey_id': str(survey.id), 'then': then or 'edit', **surface_props(actor)})
    return draft


def restore_version(actor, survey, version):
    """Unpublished changes holding an archived version's questionnaire.
    Append-only: publishing them creates a NEW version."""
    if survey.status != 'published':
        raise TransitionRefused('Only published surveys can restore a version')
    if survey.has_draft_copy():
        raise Conflict('A draft already exists for this survey')
    try:
        version_num = int(str(version).lstrip('v'))
    except (TypeError, ValueError):
        raise TransitionRefused('Invalid version')
    archived = SurveyHeader.objects.filter(
        canonical_survey=survey, is_canonical=False, version_number=version_num).first()
    if archived is None:
        return None
    draft = clone_survey_for_draft(survey, structure_source=archived)
    audit.record(actor, 'version_restore', survey, version=version_num, draft_uuid=str(draft.uuid))
    return draft


def publish_draft(actor, draft, *, force=False, acknowledge_translation_gaps=False):
    """Publish unpublished changes as a new version of the live survey."""
    if not draft.is_draft_copy:
        raise Conflict('This survey is not a draft copy')
    _require_confirmed_email(actor)
    # Same translation-gap warning as the draft→published transition: this
    # path replaces the live version's content.
    _check_translation_gaps(draft, acknowledge_translation_gaps)
    draft_uuid = str(draft.uuid)
    try:
        canonical = _publish_draft(draft, force=force)
    except IncompatibleDraftError as e:
        raise IncompatibleDraft(e.issues)
    audit.record(actor, 'draft_publish', canonical, draft_uuid=draft_uuid, version=canonical.version_number)
    pe.emit(pe.UNPUBLISHED_CHANGES_PUBLISHED, actor.user_id, {
        'survey_id': str(canonical.id), 'forced': force, **surface_props(actor)})
    # The draft's text now lives on the canonical survey -- screen that.
    screen_survey(canonical, trigger='draft_publish')
    return Published(canonical, review_state(canonical))


def discard_draft(actor, draft):
    """Throw unpublished changes away; the live survey is untouched."""
    if not draft.is_draft_copy:
        raise Conflict('This survey is not a draft copy')
    canonical = draft.published_version
    audit.record(actor, 'draft_discard', canonical, draft_uuid=str(draft.uuid))
    pe.emit(pe.UNPUBLISHED_CHANGES_DISCARDED, actor.user_id,
            {'survey_id': str(canonical.id), **surface_props(actor)})
    with transaction.atomic():
        # SurveySession.survey is PROTECT, so previewing a draft even once used
        # to make it undiscardable. publish_draft drops the same test sessions.
        SurveySession.objects.filter(survey=draft).delete()
        draft.delete()
    return canonical
