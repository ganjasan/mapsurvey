"""Orchestration: brief in, populated survey out.

`generate_survey_draft()` takes no request and returns no response — it is
called from a Celery task today, and could be called from a management
command or a future chat turn without changing shape. Everything the caller
needs afterwards is on the `AIGenerationEvent` row.
"""
import logging
from dataclasses import dataclass

from django.db import transaction

from . import client, prompts
from .materialize import materialize_draft
from .quota import QuotaExceeded, check_quota
from .schema import survey_draft_schema
from .validator import validate_blob
from ..models import AIGenerationEvent, SurveyCollaborator

logger = logging.getLogger('survey.ai')

KIND_SURVEY_DRAFT = 'survey_draft'
# One retry, never a loop: a model that produced an invalid draft twice with
# the errors spelled out is not going to converge on the third attempt, and
# each attempt costs real money and a minute of the creator's time.
MAX_ATTEMPTS = 2


@dataclass
class SurveyBrief:
    name: str
    goal: str
    audience: str
    map_target: str
    use_case: str

    def as_dict(self):
        return {
            'name': self.name,
            'goal': self.goal,
            'audience': self.audience,
            'map_target': self.map_target,
            'use_case': self.use_case,
        }


def _finish(event, outcome, error_detail='', survey=None, usage=None, blob=None):
    event.outcome = outcome
    event.error_detail = error_detail[:2000]
    if survey is not None:
        event.created_survey = survey
    if blob is not None:
        # The draft as the model produced it, before any human edit — the
        # baseline for the generated-vs-published diff (quality telemetry).
        event.generated_blob = blob
    if usage is not None:
        event.provider = usage.provider
        event.model = usage.model
        event.input_tokens = usage.input_tokens
        event.output_tokens = usage.output_tokens
        event.latency_ms = usage.latency_ms
    event.save()
    return event


def generate_survey_draft(event, brief, languages, header_overrides):
    """Run one generation attempt-set for `event`, updating it in place.

    Never raises for expected failures — every outcome is recorded on the
    event, which is what the status endpoint polls.
    """
    organization = event.organization
    try:
        check_quota(organization, KIND_SURVEY_DRAFT)
    except QuotaExceeded as exc:
        return _finish(event, 'not_configured', str(exc))

    try:
        provider = client.get_provider()
    except client.NotConfigured as exc:
        return _finish(event, 'not_configured', str(exc))

    schema = survey_draft_schema(languages)
    user_prompt = prompts.build_user_prompt(brief, languages)
    usage = None
    errors = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            blob, usage = provider.complete_structured(
                system=prompts.SYSTEM_PROMPT, user=user_prompt, schema=schema,
            )
        except client.TruncatedOutput as exc:
            # Worth one retry with a brevity hint; a second truncation means
            # the brief is asking for more survey than the ceiling allows.
            # Prefer the failed call's own usage: the assignment above never
            # ran, so the outer `usage` is either None or the previous
            # attempt's — both would misreport what this generation cost.
            usage = exc.usage or usage
            if attempt >= MAX_ATTEMPTS:
                return _finish(event, 'provider_error', str(exc), usage=usage)
            errors = ['the previous answer was cut off — produce a shorter survey']
            user_prompt = prompts.build_retry_prompt(brief, languages, errors)
            continue
        except client.ProviderError as exc:
            return _finish(event, 'provider_error', str(exc), usage=usage)

        errors = validate_blob(blob, languages)
        if not errors:
            break
        logger.info('AI draft attempt %d rejected: %s', attempt, '; '.join(errors))
        if attempt >= MAX_ATTEMPTS:
            # Keep the rejected blob too: reading real failures against real
            # briefs is how the prompt gets iterated.
            return _finish(event, 'invalid_draft', '; '.join(errors), usage=usage, blob=blob)
        user_prompt = prompts.build_retry_prompt(brief, languages, errors)

    try:
        with transaction.atomic():
            survey, warnings = materialize_draft(
                blob, header_overrides, languages,
                organization=organization, created_by=event.user,
            )
            # The import path deliberately does not create collaborators;
            # without this the creator would not own their own survey.
            SurveyCollaborator.objects.create(
                user=event.user, survey=survey, role='owner',
            )
    except Exception as exc:  # noqa: BLE001 - recorded, never surfaced raw
        logger.exception('AI draft materialization failed')
        return _finish(event, 'error', '%s: %s' % (type(exc).__name__, exc), usage=usage, blob=blob)

    if warnings:
        logger.info('AI draft imported with warnings: %s', '; '.join(warnings))
    return _finish(event, 'success', survey=survey, usage=usage, blob=blob)


def start_generation(user, organization, brief, languages):
    """Create the pending event row that the task and the poller share."""
    return AIGenerationEvent.objects.create(
        kind=KIND_SURVEY_DRAFT,
        user=user,
        organization=organization,
        brief=brief.as_dict(),
        languages=list(languages),
        outcome='pending',
    )
