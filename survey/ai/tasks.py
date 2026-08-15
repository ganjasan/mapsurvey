"""Celery entry point for survey draft generation.

Generation runs in the worker rather than the request thread: a multilingual
draft can take a minute, and the web dyno's thread pool is small enough that
blocking it would risk taking healthy requests down with the slow one (the
gthread worker is killed as a unit when it wedges past the timeout).

The task carries no state of its own — everything lives on the
`AIGenerationEvent` row, which the create page polls. That means a worker
restart mid-generation leaves a visible `pending` row rather than a silently
lost request, and the outcome is readable in the admin afterwards.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)

# Generous: two provider attempts plus materialization. The provider's own
# client timeout (AI_REQUEST_TIMEOUT_SECONDS) is the real bound; this is the
# backstop that keeps a wedged task from occupying a worker slot forever.
SOFT_TIME_LIMIT = 300


@shared_task(soft_time_limit=SOFT_TIME_LIMIT)
def generate_survey_draft_task(event_id, brief_data, languages, header_overrides):
    from .generation import SurveyBrief, generate_survey_draft
    from ..models import AIGenerationEvent

    try:
        event = AIGenerationEvent.objects.get(pk=event_id)
    except AIGenerationEvent.DoesNotExist:
        logger.error('AIGenerationEvent %s does not exist', event_id)
        return

    brief = SurveyBrief(**brief_data)
    try:
        generate_survey_draft(event, brief, languages, header_overrides)
    except Exception as exc:  # noqa: BLE001 - the poller must never wait forever
        logger.exception('AI draft task crashed for event %s', event_id)
        event.outcome = 'error'
        event.error_detail = ('%s: %s' % (type(exc).__name__, exc))[:2000]
        event.save(update_fields=['outcome', 'error_detail'])
