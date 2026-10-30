"""Every model call costed the moment it ends (design D5, owner 2026-10-29).

One `AIGenerationEvent` row per call (`paper_page` for the answers, `paper_code`
for the footer-text fallback) and, right after the row is written, its
`$ai_generation` in PostHog — span name = the kind, trace = `paper-batch-<id>`
so a batch rolls up on the LLM Analytics dashboard, ids only. PostHog prices
the tokens by model; no dollar figure is stored here.

The creator events (`paper_page_recognised`, …) are the product view of the
same work; they carry counts and outcomes, never content.
"""
from survey import product_events as pe
from survey.models import AIGenerationEvent


def trace_id(batch_id):
    return f'paper-batch-{batch_id}'


def start(page, kind):
    batch = page.batch
    return AIGenerationEvent.objects.create(
        kind=kind, user=batch.created_by, organization=batch.organization, outcome='pending')


def finish(event, page, outcome, usage=None, error=''):
    event.outcome = outcome
    event.error_detail = (error or '')[:2000]
    event.attempts = 1
    if usage is not None:
        event.provider = usage.provider
        event.model = usage.model
        event.input_tokens = usage.input_tokens
        event.output_tokens = usage.output_tokens
        event.thinking_tokens = usage.thinking_tokens
        event.latency_ms = usage.latency_ms
        event.total_latency_ms = usage.latency_ms
    event.save()
    pe.emit_llm_generation(event, trace_id=trace_id(page.batch_id), extra={
        'survey_id': page.batch.survey_id,
        'batch_id': page.batch_id,
        'page_number': page.page_number,
    })
    return event


def page_event(page, outcome):
    """`paper_page_recognised`: outcome, how the code was read, doubtful count."""
    from survey.paper.extract import is_doubtful
    doubtful = sum(1 for f in (page.extraction or {}).values() if is_doubtful(f)) if outcome == 'recognised' else 0
    pe.emit(pe.PAPER_PAGE_RECOGNISED, page.batch.created_by_id, {
        'survey_id': page.batch.survey_id,
        'outcome': outcome,
        'code_source': page.code_source,
        'doubtful': doubtful,
    })
