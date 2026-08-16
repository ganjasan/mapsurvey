"""Creator-lifecycle events for PostHog — the stages the admin funnel reconstructs.

Every event here is one the database can also reproduce *historically*, from a
timestamp we already store. That is the design constraint, not a coincidence: an
event we could not backfill would give the funnel a step that is empty before
today, which is exactly the discontinuity this whole change exists to avoid.
See openspec/changes/posthog-funnel-migration/design.md §1.

Two rules worth keeping in mind when adding to this file:

- `distinct_id` is always the user's primary key, matching the browser snippet in
  `survey/templates/partials/_analytics.html`. That is what makes a backfilled
  `survey_created` from March land on the same person as today's `$pageview`.
- These are *creator* events. Nothing here may describe a respondent — the
  boundary drawn in openspec/changes/posthog-internal-analytics. `survey_first_response`
  records that a survey received its first answer, never who answered.
"""

import logging

logger = logging.getLogger(__name__)

# Event names. Kept as constants because the backfill command and the forward
# emission points must agree exactly -- a typo in one produces a funnel with a
# step that silently halves.
CREATOR_REGISTERED = 'creator_registered'
CREATOR_ACTIVATED = 'creator_activated_account'
SURVEY_CREATED = 'survey_created'
SURVEY_QUESTION_ADDED = 'survey_question_added'
SURVEY_PUBLISHED = 'survey_published'
SURVEY_FIRST_RESPONSE = 'survey_first_response'

CREATOR_FUNNEL_EVENTS = (
    CREATOR_REGISTERED,
    CREATOR_ACTIVATED,
    SURVEY_CREATED,
    SURVEY_QUESTION_ADDED,
    SURVEY_PUBLISHED,
    SURVEY_FIRST_RESPONSE,
)

# The AI-drafting sub-funnel, which sits *inside* the step between activation and
# `survey_created`. Same backfill constraint as above -- each one names the
# `AIGenerationEvent` field a historical reconstruction reads its timestamp from:
#
#   ai_draft_requested -> created_at      (brief accepted, task enqueued)
#   ai_draft_finished  -> the row's terminal state (outcome recorded)
#   ai_draft_opened    -> redirected_at   (creator was still there when it landed)
#
# `ai_draft_opened` is a separate event rather than a `waited` property on
# `ai_draft_finished` because at finish time nobody knows yet: `redirected_at` is
# written later, by the status endpoint. The gap between a successful finish and
# an open is the abandonment measure.
AI_DRAFT_REQUESTED = 'ai_draft_requested'
AI_DRAFT_FINISHED = 'ai_draft_finished'
AI_DRAFT_OPENED = 'ai_draft_opened'

AI_DRAFT_EVENTS = (
    AI_DRAFT_REQUESTED,
    AI_DRAFT_FINISHED,
    AI_DRAFT_OPENED,
)

# How a survey came into being. Historical events are all `manual` by definition,
# which is the baseline the AI generator gets measured against.
CREATION_MANUAL = 'manual'
CREATION_AI = 'ai'

# Whether an event's timestamp is the real moment or a reconstruction.
# `survey_published` has no publish-transition timestamp before this change, so
# backfilled rows use survey creation as a proxy (see funnel.py:_published_first_created).
# Insights that care about timing can exclude the approximate half instead of
# silently averaging two different things.
SOURCE_LIVE = 'live'
SOURCE_BACKFILL = 'backfill'
SOURCE_BACKFILL_PROXY = 'backfill_proxy'


def creation_method_for(survey_id):
    """`ai` if the generator produced this survey, `manual` otherwise.

    A lookup, not a stored column: `SurveyHeader` has no origin field, and adding
    one would mean a migration plus a backfill for a fact `AIGenerationEvent`
    already records. Called on publish and on a survey's first response — both
    rare enough that one indexed existence check does not matter.

    Carrying the method on the later events is what turns "do AI drafts get
    published more often?" into a breakdown instead of a join back to
    `survey_created` through `survey_id`.
    """
    if survey_id is None:
        return CREATION_MANUAL
    from .models import AIGenerationEvent

    is_ai = AIGenerationEvent.objects.filter(created_survey_id=survey_id).exists()
    return CREATION_AI if is_ai else CREATION_MANUAL


def emit(event, user_id, properties=None, timestamp=None):
    """Send one creator-lifecycle event. Never raises.

    Silent no-op when PostHog is unconfigured (`posthog.disabled`, set in
    `survey.apps.SurveyConfig`), which is the case in tests and local
    development. Analytics that can break a request is worse than no analytics --
    the same rule the Celery error reporter follows.
    """
    if user_id is None:
        return
    try:
        import posthog

        if posthog.disabled:
            return
        props = {'timestamp_source': SOURCE_LIVE}
        props.update(properties or {})
        posthog.capture(
            event,
            distinct_id=str(user_id),
            properties=props,
            timestamp=timestamp,
        )
    except Exception:
        logger.warning('posthog: failed to emit %s', event, exc_info=True)
