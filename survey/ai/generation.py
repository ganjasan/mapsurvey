"""Orchestration: brief in, populated survey out.

`generate_survey_draft()` takes no request and returns no response — it is
called from a Celery task today, and could be called from a management
command or a future chat turn without changing shape. Everything the caller
needs afterwards is on the `AIGenerationEvent` row.
"""
import logging
import time
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from . import client, prompts
from .materialize import materialize_draft
from .quota import QuotaExceeded, check_quota
from .schema import survey_draft_schema
from .validator import validate_blob
from .. import product_events as pe
from ..models import AIGenerationEvent, Question, SurveyCollaborator

logger = logging.getLogger('survey.ai')

KIND_SURVEY_DRAFT = 'survey_draft'
# One retry, never a loop: a model that produced an invalid draft twice with
# the errors spelled out is not going to converge on the third attempt, and
# each attempt costs real money and a minute of the creator's time.
MAX_ATTEMPTS = 2

# Waits between retries of a *transient* provider failure — overload, a dropped
# connection, a malformed payload. A separate budget from MAX_ATTEMPTS on
# purpose: that one is about the model writing a bad survey, this one is about
# the provider having a bad second, and spending one on the other means a 503
# eats the retry a genuinely invalid draft needed.
#
# Sized from what we have actually seen: both of 2026-08-17's failures were of
# this kind, a minute apart, and both were shown to the creator as a dead end.
# Backing off to ~23s total keeps the whole thing inside the Celery task's
# 300s soft limit even when every retry is spent on top of a 50s generation.
TRANSIENT_BACKOFF_SECONDS = (2, 6, 15)


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


class AttemptSet:
    """Running account of the provider calls one generation makes.

    Exists because `usage` used to be reassigned on every iteration of the retry
    loop: a two-attempt generation then reported only its second call, while the
    creator had waited for both, and nothing in the row said a retry had
    happened at all. With MAX_ATTEMPTS=2 and a 120s client timeout that is up to
    four minutes of waiting that the log would render as one ordinary call.

    Counts calls *started*, not calls that returned: a call that raised before
    producing usage still cost the creator their wait. Its duration is simply
    unknown, so it contributes to `count` and not to `total_latency_ms` —
    understating the time is honest, inventing it is not.
    """

    def __init__(self):
        self.count = 0
        self.total_latency_ms = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.thinking_tokens = None
        self.terminal = None

    def started(self):
        self.count += 1

    def record(self, usage):
        """Fold in a call that came back with usage — completed or truncated."""
        if usage is None:
            return
        self.terminal = usage
        self.total_latency_ms += usage.latency_ms or 0
        self.input_tokens += usage.input_tokens or 0
        self.output_tokens += usage.output_tokens or 0
        if usage.thinking_tokens is not None:
            # Summed across the set like the other token counts, but only over
            # the calls that reported: staying None until something is actually
            # measured keeps "not reported" distinguishable from "reasoned for
            # nothing", which is the whole point of the field.
            self.thinking_tokens = (self.thinking_tokens or 0) + usage.thinking_tokens


def _call_provider(provider, attempts, on_progress, **kwargs):
    """One draft from the provider, riding out a provider that is briefly unwell.

    The creator asked for a survey, not for a status report on Google's
    capacity. A 503 that the API itself calls "usually temporary", a dropped
    connection, a reply that arrives malformed — none of those are answers to
    their request, and handing them back as "Couldn't reach the AI service" ends
    the interaction at the exact moment the product was about to deliver. Both
    of the failures on 2026-08-17 were this, one minute apart.

    Retries only what `ProviderError.transient` marks: a rejected key or a model
    this key may not use is a verdict, and repeating it would spend the
    creator's wait twice to arrive at the same message.

    `TruncatedOutput` passes straight through — it is a content problem the
    caller answers with a "be shorter" prompt, not something a delay fixes.
    Every call is counted in `attempts`, including the ones spent here, so the
    event row still says how much waiting really happened.
    """
    for delay in TRANSIENT_BACKOFF_SECONDS + (None,):
        attempts.started()
        try:
            return provider.complete_structured(on_progress=on_progress, **kwargs)
        except client.TruncatedOutput:
            raise
        except client.ProviderError as exc:
            if not exc.transient or delay is None:
                raise
            logger.warning(
                'AI provider failed transiently (%s); retrying in %ss', exc, delay,
            )
            time.sleep(delay)


def _progress_recorder(event):
    """A callback that publishes draft counts to the row the poller reads.

    `queryset.update()` rather than saving the instance, for the reason already
    documented at the status endpoint: the worker and the poller write this row
    concurrently, and a load-modify-save here could clobber a terminal outcome
    with a stale `pending`. The `outcome='pending'` filter is the second half of
    that guarantee — once the generation has finished, a late progress callback
    matches nothing and writes nothing.

    Fresh per attempt, and only writes when a count actually advances: a section
    closing happens a handful of times per generation, not per chunk.

    Clearing the stored counts up front is what makes a retry legible. The
    second attempt writes a whole new draft, so leaving the first one's numbers
    in place would make the counter jump backwards when the new draft's first
    section closes. Back to null, and the overlay hides the counter until the
    replacement draft has actually produced something.
    """
    # Both the row and the in-memory instance, always together: `_finish()`
    # ends with a full `event.save()`, so an instance still carrying the stale
    # values it was loaded with would write them back over everything recorded
    # here. Keeping the two in step is what makes the counts survive the finish.
    event.sections_drafted = None
    event.questions_drafted = None
    AIGenerationEvent.objects.filter(pk=event.pk, outcome='pending').update(
        sections_drafted=None, questions_drafted=None,
    )
    seen = {'sections': -1, 'questions': -1}

    def record(sections, questions):
        if sections <= seen['sections'] and questions <= seen['questions']:
            return
        seen['sections'] = sections
        seen['questions'] = questions
        event.sections_drafted = sections
        event.questions_drafted = questions
        AIGenerationEvent.objects.filter(pk=event.pk, outcome='pending').update(
            sections_drafted=sections, questions_drafted=questions,
        )

    return record


def _finish(event, outcome, error_detail='', survey=None, attempts=None, blob=None):
    event.outcome = outcome
    event.error_detail = error_detail[:2000]
    if survey is not None:
        event.created_survey = survey
    if blob is not None:
        # The draft as the model produced it, before any human edit — the
        # baseline for the generated-vs-published diff (quality telemetry).
        event.generated_blob = blob
    if attempts is not None and attempts.count:
        event.attempts = attempts.count
    usage = attempts.terminal if attempts is not None else None
    if usage is not None:
        # provider/model from the terminal call (they cannot differ within a
        # set); token counts and elapsed summed, because that is what the
        # generation cost and how long the creator waited. `latency_ms` stays
        # the terminal call alone — see the model's field comment.
        event.provider = usage.provider
        event.model = usage.model
        event.input_tokens = attempts.input_tokens
        event.output_tokens = attempts.output_tokens
        event.thinking_tokens = attempts.thinking_tokens
        event.latency_ms = usage.latency_ms
        event.total_latency_ms = attempts.total_latency_ms
    event.save()
    _emit_terminal_events(event, outcome, survey)
    return event


def _emit_terminal_events(event, outcome, survey):
    """Analytics for a finished generation. After the save, never before it.

    `survey_created` lives here rather than in `materialize_draft()` because a
    materialized survey is not yet a created one: the collaborator row is added
    by the caller, and a failure between the two rolls the survey back. This is
    the point where the outcome is final.

    The manual path emits its own `survey_created` in `editor_views`; without
    this call an AI-drafted survey would produce none at all, and the
    `manual`/`ai` split would read 100% manual forever.
    """
    properties = {'outcome': outcome}
    if event.provider:
        properties['provider'] = event.provider
    if event.model:
        properties['model'] = event.model
    # Each omitted when absent rather than sent as 0: a breakdown that averages
    # "not reported" in as a zero is worse than one with fewer rows in it.
    for field in ('latency_ms', 'total_latency_ms', 'attempts',
                  'input_tokens', 'output_tokens', 'thinking_tokens'):
        value = getattr(event, field)
        if value is not None:
            properties[field] = value
    pe.emit(pe.AI_DRAFT_FINISHED, event.user_id, properties)

    if survey is None:
        return

    # `survey.id`, not `survey.uuid`: the manual path and the backfill both
    # send the primary key, and two id spaces under one property name would
    # make the ai/manual comparison unjoinable.
    survey_props = {
        'survey_id': str(survey.id),
        'creation_method': pe.CREATION_AI,
    }
    pe.emit(pe.SURVEY_CREATED, event.user_id, survey_props)

    # The step that would otherwise read backwards. `survey_question_added`
    # fires in `editor_question_create` -- a human adding a question in the
    # editor. An AI draft arrives with its questions already written, so the
    # creator never visits that view, and the funnel would report AI users as
    # stuck at the empty-editor step this generator exists to remove: the
    # improvement would show up as a regression.
    if Question.objects.filter(survey_section__survey_header=survey).exists():
        pe.emit(pe.SURVEY_QUESTION_ADDED, event.user_id, survey_props)


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
    attempts = AttemptSet()
    errors = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        # Reset per attempt: a retry starts a new draft, and counts that carried
        # over would show the creator a survey growing past what any single
        # answer contains.
        record_progress = _progress_recorder(event) if settings.AI_STREAMING_ENABLED else None
        try:
            blob, usage = _call_provider(
                provider, attempts, record_progress,
                system=prompts.SYSTEM_PROMPT, user=user_prompt, schema=schema,
            )
        except client.TruncatedOutput as exc:
            # Worth one retry with a brevity hint; a second truncation means
            # the brief is asking for more survey than the ceiling allows.
            # The failed call's own usage still counts: those tokens were spent
            # and that time was waited, so it folds into the set like any other.
            attempts.record(exc.usage)
            if attempt >= MAX_ATTEMPTS:
                return _finish(event, 'provider_error', str(exc), attempts=attempts)
            errors = ['the previous answer was cut off — produce a shorter survey']
            user_prompt = prompts.build_retry_prompt(brief, languages, errors)
            continue
        except client.ProviderError as exc:
            # No usage to fold in: the call raised before reporting any. The
            # attempt is still counted by `started()` above, so the row shows a
            # call was made even though its cost is unknown.
            return _finish(event, 'provider_error', str(exc), attempts=attempts)

        attempts.record(usage)
        errors = validate_blob(blob, languages)
        if not errors:
            break
        logger.info('AI draft attempt %d rejected: %s', attempt, '; '.join(errors))
        if attempt >= MAX_ATTEMPTS:
            # Keep the rejected blob too: reading real failures against real
            # briefs is how the prompt gets iterated.
            return _finish(event, 'invalid_draft', '; '.join(errors), attempts=attempts, blob=blob)
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
        return _finish(event, 'error', '%s: %s' % (type(exc).__name__, exc),
                       attempts=attempts, blob=blob)

    if warnings:
        logger.info('AI draft imported with warnings: %s', '; '.join(warnings))
    return _finish(event, 'success', survey=survey, attempts=attempts, blob=blob)


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
