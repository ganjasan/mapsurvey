"""Provider-agnostic LLM access.

The rest of `survey/ai/` (and future AI features, #92/#95) talks to models
only through `LLMProvider.complete_structured()` — vendor SDKs are imported
in this module and nowhere else. That keeps a second provider (an EU-hosted
model for data-residency-sensitive deals, or a local model) a one-class
addition instead of a refactor.

Failure taxonomy mirrors `survey/acquisition.py`:
  NotConfigured  — credentials absent; a state, not an error. Raised before
                   any network call.
  ProviderError  — configured but the call failed (network, non-2xx,
                   refusal, unparseable payload).
  TruncatedOutput — the model hit the output-token ceiling mid-JSON. A
                   subclass of ProviderError, but distinguished because the
                   orchestrator's single retry (with a "be more concise"
                   hint) is worth attempting where a network error is not.
"""
import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from django.conf import settings

from .progress import DraftProgress

logger = logging.getLogger('survey.ai')


def _transient_status(status):
    """Is this HTTP status the provider having a bad second, rather than a verdict?

    429 and 5xx only. A 4xx other than rate limiting is a statement about the
    request — a bad key, a model this key may not use, a payload the API
    rejects — and repeating it unchanged just spends the creator's wait twice
    to reach the same answer.
    """
    return status == 429 or 500 <= status < 600


def _report(on_progress, tracker):
    """Hand progress to the caller, never letting it break what it describes.

    A draft lost because a progress write hit a database hiccup would be a
    strictly worse product than a draft with no progress bar, so the callback's
    failures are logged and swallowed rather than propagated.
    """
    try:
        on_progress(tracker.sections, tracker.questions)
    except Exception:  # noqa: BLE001 - see docstring
        logger.warning('AI progress callback failed; generation continues', exc_info=True)


class NotConfigured(Exception):
    """The selected provider has no credentials — feature is off, not broken."""


class ProviderError(Exception):
    """The provider call failed after being properly configured.

    `transient` says whether trying again is worth the creator's time. It is set
    at each raise site rather than sniffed from the message later, because only
    the code that saw the status line knows the difference between "the model is
    busy" and "this key may not use this model".

    Defaults to False: a failure nobody classified is shown to the creator once
    rather than retried blindly, which is the safer way to be wrong. Overload,
    connection loss and malformed output are the classified-transient cases —
    all three are the provider having a bad second, and all three cost the
    creator a dead end today when a second attempt would very likely land.
    """

    def __init__(self, message, transient=False):
        super().__init__(message)
        self.transient = transient


class TruncatedOutput(ProviderError):
    """The model ran out of output tokens before finishing the JSON.

    Carries the usage of the truncated call: those tokens were spent and are
    usually the most expensive attempt of the set, so dropping them would
    understate what a failed generation actually cost.
    """

    def __init__(self, message, usage=None):
        super().__init__(message)
        self.usage = usage


@dataclass
class LLMUsage:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    # Reasoning tokens the model spent before writing its answer. `None` means
    # the provider did not report them -- deliberately not 0, because "we could
    # not see it" and "it reasoned for nothing" are different facts, and
    # averaging the first into the second is how a latency question stops being
    # answerable. Anthropic reports no such number here and leaves it None.
    thinking_tokens: Optional[int] = None


class AnthropicProvider:
    """Anthropic Messages API via the official SDK.

    Structured output is enforced natively with `output_config.format`
    (json_schema), so the response text is guaranteed-parseable JSON — no
    prose scraping. The call streams internally (`get_final_message()`)
    because the SDK refuses large `max_tokens` on non-streaming requests;
    nothing token-by-token ever reaches the caller.
    """

    name = 'anthropic'

    @staticmethod
    def configured():
        return bool(settings.ANTHROPIC_API_KEY)

    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise NotConfigured('ANTHROPIC_API_KEY is not set')
        import anthropic  # deferred: the dependency is only needed when configured
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=float(settings.AI_REQUEST_TIMEOUT_SECONDS),
            max_retries=1,
        )
        self._model = settings.AI_SURVEY_DRAFT_MODEL

    def complete_structured(self, *, system, user, schema, max_tokens=64000, on_progress=None):
        # type: (...) -> Tuple[Dict, LLMUsage]
        started = time.monotonic()
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            ) as stream:
                if on_progress is not None:
                    # The increments were always there — this call has streamed
                    # since it was written, because the SDK refuses large
                    # max_tokens otherwise — and were simply thrown away.
                    tracker = DraftProgress()
                    for text in stream.text_stream:
                        if tracker.feed(text):
                            _report(on_progress, tracker)
                message = stream.get_final_message()
        except self._anthropic.APIConnectionError as exc:
            raise ProviderError('connection error: %s' % exc, transient=True) from exc
        except self._anthropic.APIStatusError as exc:
            raise ProviderError(
                'API error %s: %s' % (exc.status_code, exc.message),
                transient=_transient_status(exc.status_code),
            ) from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        usage = LLMUsage(
            provider=self.name,
            model=self._model,
            input_tokens=getattr(message.usage, 'input_tokens', 0) or 0,
            output_tokens=getattr(message.usage, 'output_tokens', 0) or 0,
            latency_ms=latency_ms,
        )

        # Check stop_reason BEFORE touching content: a refusal carries no
        # usable content, and a max_tokens stop means the JSON is cut off.
        if message.stop_reason == 'refusal':
            raise ProviderError('model refused the request')
        text = next((b.text for b in message.content if b.type == 'text'), '')
        if message.stop_reason == 'max_tokens':
            raise TruncatedOutput(
                'output truncated at %d tokens' % usage.output_tokens, usage=usage,
            )
        try:
            return json.loads(text), usage
        except ValueError as exc:
            raise ProviderError('unparseable model output: %s' % exc, transient=True) from exc



class GeminiProvider:
    """Google AI Studio (Gemini) over plain HTTP.

    Deliberately not the Google SDK: this provider exists so the feature can be
    exercised end-to-end on a free key, and pulling another vendor SDK into the
    production image to serve a test path is a bad trade. `requests` is already
    a dependency.

    Gemini's structured output is close to ours but not identical, so the
    schema is adapted (see `_to_gemini_schema`) rather than passed through.
    """

    name = 'gemini'
    endpoint = 'https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent'
    # `?alt=sse` matters: without it the streaming endpoint answers with one
    # long JSON array, which cannot be consumed incrementally and would defeat
    # the entire point of asking for a stream.
    stream_endpoint = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        '%s:streamGenerateContent?alt=sse'
    )

    @staticmethod
    def configured():
        return bool(settings.GEMINI_API_KEY)

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise NotConfigured('GEMINI_API_KEY is not set')
        self._api_key = settings.GEMINI_API_KEY
        self._model = settings.GEMINI_MODEL

    def complete_structured(self, *, system, user, schema, max_tokens=64000, on_progress=None):
        # type: (...) -> Tuple[Dict, LLMUsage]
        payload = self._payload(system, user, schema, max_tokens)
        started = time.monotonic()
        if on_progress is None:
            text, meta, finish_reason, block_reason = self._collect(payload)
        else:
            text, meta, finish_reason, block_reason = self._collect_streamed(payload, on_progress)
        # Before the outcome checks, exactly as in the non-streaming original:
        # a truncated call carries its usage, and that usage needs a duration.
        latency_ms = int((time.monotonic() - started) * 1000)

        usage = LLMUsage(
            provider=self.name,
            model=self._model,
            input_tokens=meta.get('promptTokenCount') or 0,
            output_tokens=meta.get('candidatesTokenCount') or 0,
            latency_ms=latency_ms,
            thinking_tokens=_thinking_tokens(meta),
        )

        if block_reason is not None:
            # Prompt-level block: the request never produced a candidate.
            raise ProviderError('request blocked by the provider (%s)' % block_reason)
        if finish_reason == 'MAX_TOKENS':
            raise TruncatedOutput(
                'output truncated at %d tokens' % usage.output_tokens, usage=usage,
            )
        if finish_reason not in (None, 'STOP'):
            raise ProviderError('generation stopped: %s' % finish_reason)

        try:
            return json.loads(text), usage
        except ValueError as exc:
            raise ProviderError('unparseable model output: %s' % exc, transient=True) from exc

    def _payload(self, system, user, schema, max_tokens):
        generation_config = {
            "responseMimeType": "application/json",
            "responseSchema": _to_gemini_schema(schema),
            "maxOutputTokens": max_tokens,
        }
        # Reasoning effort is ours to choose, not the provider's to assume: left
        # unset, Gemini 3 models reason at `medium`, which is unbounded time we
        # neither asked for nor measured. An empty setting omits the key
        # entirely so a model that rejects the field is an env-var edit rather
        # than a hotfix -- the same escape GEMINI_MODEL exists for.
        if settings.AI_THINKING_LEVEL:
            generation_config["thinkingConfig"] = {
                "thinkingLevel": settings.AI_THINKING_LEVEL,
            }
        return {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": generation_config,
        }

    def _post(self, payload, endpoint, stream=False):
        import requests

        # For a blocking call the timeout bounds the whole read, which is the
        # behaviour AI_REQUEST_TIMEOUT_SECONDS was written for. Streaming
        # changes its meaning under our feet: `requests` restarts the read
        # timer on every chunk, so the same number stops bounding anything a
        # trickle of data can reset. There it becomes the STALL limit — how
        # long the stream may go silent — and the total budget is enforced in
        # `_collect_streamed`'s loop, where wall-clock is actually visible.
        timeout = (
            settings.AI_STREAM_STALL_SECONDS if stream
            else settings.AI_REQUEST_TIMEOUT_SECONDS
        )
        try:
            response = requests.post(
                endpoint % self._model,
                json=payload,
                # Header rather than ?key=: keeps the credential out of URLs,
                # proxy logs and tracebacks.
                headers={"x-goog-api-key": self._api_key},
                timeout=timeout,
                stream=stream,
            )
        except requests.RequestException as exc:
            raise ProviderError('connection error: %s' % exc, transient=True) from exc

        if response.status_code == 404:
            # Model names churn faster than this file does, and a listed model
            # can still be closed to new keys — the API explains which, so pass
            # its message through instead of replacing it with a guess.
            raise ProviderError(
                'model %r unavailable — set GEMINI_MODEL to a model your key can '
                'use (see AI Studio). Provider said: %s'
                % (self._model, _error_message(response))
            )
        if response.status_code >= 400:
            raise ProviderError(
                'API error %s: %s' % (response.status_code, _error_message(response)),
                transient=_transient_status(response.status_code),
            )
        return response

    def _collect(self, payload):
        """One blocking call → (text, usage metadata, finish reason, block reason)."""
        body = self._post(payload, self.endpoint).json()
        meta = body.get('usageMetadata') or {}
        candidates = body.get('candidates') or []
        if not candidates:
            reason = (body.get('promptFeedback') or {}).get('blockReason', 'unknown')
            return '', meta, None, reason
        candidate = candidates[0]
        parts = (candidate.get('content') or {}).get('parts') or []
        text = ''.join(part.get('text', '') for part in parts)
        return text, meta, candidate.get('finishReason'), None

    def _collect_streamed(self, payload, on_progress):
        """Same tuple, assembled from an SSE stream, reporting progress as it goes.

        Status is checked before the body is consumed (in `_post`), so an
        outright rejection still fails the same way it does unstreamed. A
        failure *after* headers — the case that only exists here — is normalized
        to ProviderError like any other, and lands on the same `provider_error`
        outcome. `usageMetadata` rides the final chunk, so a stream that dies
        mid-way leaves none, exactly as a connection error does today.
        """
        import requests

        response = self._post(payload, self.stream_endpoint, stream=True)
        tracker = DraftProgress()
        chunks = []
        meta = {}
        finish_reason = None
        block_reason = None
        # The stall limit lives in the read timeout (see _post); this is the
        # other bound — total wall clock. Checked per line because that is the
        # only place a streamed call can see the clock at all: a stream that
        # keeps trickling resets the read timeout forever, which is exactly how
        # 2026-08-17's stall ran until Celery's 300s soft limit shot the task.
        deadline = time.monotonic() + settings.AI_REQUEST_TIMEOUT_SECONDS
        try:
            for line in response.iter_lines(decode_unicode=True):
                if time.monotonic() > deadline:
                    raise ProviderError(
                        'stream exceeded %ss total; %d characters received'
                        % (settings.AI_REQUEST_TIMEOUT_SECONDS, len(''.join(chunks))),
                        transient=True,
                    )
                event = _sse_payload(line)
                if event is None:
                    continue
                if event.get('usageMetadata'):
                    # Later chunks supersede earlier ones: the counts are
                    # cumulative, and the last one is the whole call.
                    meta = event['usageMetadata']
                candidates = event.get('candidates') or []
                if not candidates:
                    reason = (event.get('promptFeedback') or {}).get('blockReason')
                    if reason:
                        block_reason = reason
                    continue
                candidate = candidates[0]
                if candidate.get('finishReason'):
                    finish_reason = candidate['finishReason']
                parts = (candidate.get('content') or {}).get('parts') or []
                text = ''.join(part.get('text', '') for part in parts)
                if not text:
                    continue
                chunks.append(text)
                if tracker.feed(text):
                    _report(on_progress, tracker)
        except requests.RequestException as exc:
            raise ProviderError('connection lost mid-stream: %s' % exc, transient=True) from exc

        if block_reason is None and finish_reason is None:
            # The stream ran out without ever saying why it stopped. That is not
            # a complete answer, it is a connection that closed mid-sentence —
            # and unlike the blocking call, which gets a whole body or nothing,
            # this failure mode only exists here. Left unchecked the partial
            # JSON falls through to json.loads and surfaces as "unparseable
            # model output", which is what reached production on 2026-08-17
            # and read to the creator as the AI being unreachable.
            #
            # Transient: the draft was arriving and simply got cut off, so the
            # retry that rides out a 503 is exactly the right response here too.
            raise ProviderError(
                'stream ended after %d characters without a finish reason'
                % len(''.join(chunks)),
                transient=True,
            )

        return ''.join(chunks), meta, finish_reason, block_reason


def _error_message(response):
    """Pull the provider's own explanation out of an error response.

    Worth the few lines: a retired-model 404 and a bad-key 404 look identical
    without it, and the API states which in plain language.
    """
    try:
        return (response.json().get('error') or {}).get('message') or response.text[:300]
    except ValueError:
        return response.text[:300]


def _sse_payload(line):
    # type: (str) -> Optional[Dict]
    """One SSE line → its decoded JSON event, or None if it carries no event.

    Keep-alives, blank separators and the terminal sentinel are all normal
    traffic rather than errors. An undecodable data line is skipped too: half a
    progress count is not worth failing a generation that is still arriving.
    """
    if not line or not line.startswith('data:'):
        return None
    raw = line[len('data:'):].strip()
    if not raw or raw == '[DONE]':
        return None
    try:
        return json.loads(raw)
    except ValueError:
        logger.warning('undecodable SSE chunk from the provider; skipped')
        return None


def _thinking_tokens(meta):
    # type: (Dict) -> Optional[int]
    """Reasoning tokens from Gemini's usage metadata, or None if unknowable.

    Two sources, in order, because the field name is not something to bet the
    measurement on: Google renames and adds keys here faster than we deploy
    (`GEMINI_MODEL` is an env var for the same reason), and a hardcoded key that
    quietly stops matching would record nothing while looking like it worked.

    The fallback is arithmetic on fields the documented response shape does
    carry: whatever the total accounts for beyond prompt and candidates is
    reasoning. Guarded to a positive difference so a provider that excludes
    reasoning from the total yields None rather than a fabricated 0 or a
    negative.
    """
    reported = meta.get('thoughtsTokenCount')
    if reported is not None:
        return reported
    total = meta.get('totalTokenCount')
    if total is None:
        return None
    accounted = (meta.get('promptTokenCount') or 0) + (meta.get('candidatesTokenCount') or 0)
    remainder = total - accounted
    return remainder if remainder > 0 else None


# Gemini accepts a subset of JSON Schema: `additionalProperties` is rejected,
# and the REST surface expects the type names uppercased. Adapting here keeps
# `schema.py` written against one shape instead of the union of every
# provider's dialect.
_GEMINI_ALLOWED_KEYS = ('type', 'properties', 'required', 'items', 'enum', 'description')


def _to_gemini_schema(schema):
    # type: (Dict) -> Dict
    if not isinstance(schema, dict):
        return schema
    adapted = {}
    for key, value in schema.items():
        if key not in _GEMINI_ALLOWED_KEYS:
            continue
        if key == 'type':
            adapted[key] = value.upper() if isinstance(value, str) else value
        elif key == 'properties':
            adapted[key] = {k: _to_gemini_schema(v) for k, v in value.items()}
        elif key == 'items':
            adapted[key] = _to_gemini_schema(value)
        else:
            adapted[key] = value
    return adapted


_PROVIDERS = {
    'anthropic': AnthropicProvider,
    'gemini': GeminiProvider,
}


def get_provider():
    """Instantiate the configured provider; raises NotConfigured when unusable."""
    name = settings.AI_PROVIDER
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise NotConfigured('unknown AI_PROVIDER %r' % name)
    return provider_cls()


def provider_configured():
    """Cheap truthiness check for UI gating — no network, no SDK import."""
    provider_cls = _PROVIDERS.get(settings.AI_PROVIDER)
    return bool(provider_cls and provider_cls.configured())
