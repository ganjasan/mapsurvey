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
import time
from dataclasses import dataclass
from typing import Dict, Tuple

from django.conf import settings


class NotConfigured(Exception):
    """The selected provider has no credentials — feature is off, not broken."""


class ProviderError(Exception):
    """The provider call failed after being properly configured."""


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

    def complete_structured(self, *, system, user, schema, max_tokens=64000):
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
                message = stream.get_final_message()
        except self._anthropic.APIConnectionError as exc:
            raise ProviderError('connection error: %s' % exc) from exc
        except self._anthropic.APIStatusError as exc:
            raise ProviderError('API error %s: %s' % (exc.status_code, exc.message)) from exc

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
            raise ProviderError('unparseable model output: %s' % exc) from exc



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

    @staticmethod
    def configured():
        return bool(settings.GEMINI_API_KEY)

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise NotConfigured('GEMINI_API_KEY is not set')
        self._api_key = settings.GEMINI_API_KEY
        self._model = settings.GEMINI_MODEL

    def complete_structured(self, *, system, user, schema, max_tokens=64000):
        # type: (...) -> Tuple[Dict, LLMUsage]
        import requests

        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": _to_gemini_schema(schema),
                "maxOutputTokens": max_tokens,
            },
        }
        started = time.monotonic()
        try:
            response = requests.post(
                self.endpoint % self._model,
                json=payload,
                # Header rather than ?key=: keeps the credential out of URLs,
                # proxy logs and tracebacks.
                headers={"x-goog-api-key": self._api_key},
                timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise ProviderError('connection error: %s' % exc) from exc

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
                'API error %s: %s' % (response.status_code, _error_message(response))
            )

        latency_ms = int((time.monotonic() - started) * 1000)
        body = response.json()
        meta = body.get('usageMetadata') or {}
        usage = LLMUsage(
            provider=self.name,
            model=self._model,
            input_tokens=meta.get('promptTokenCount') or 0,
            output_tokens=meta.get('candidatesTokenCount') or 0,
            latency_ms=latency_ms,
        )

        candidates = body.get('candidates') or []
        if not candidates:
            # Prompt-level block: the request never produced a candidate.
            reason = (body.get('promptFeedback') or {}).get('blockReason', 'unknown')
            raise ProviderError('request blocked by the provider (%s)' % reason)

        candidate = candidates[0]
        finish_reason = candidate.get('finishReason')
        if finish_reason == 'MAX_TOKENS':
            raise TruncatedOutput(
                'output truncated at %d tokens' % usage.output_tokens, usage=usage,
            )
        if finish_reason not in (None, 'STOP'):
            raise ProviderError('generation stopped: %s' % finish_reason)

        parts = (candidate.get('content') or {}).get('parts') or []
        text = ''.join(part.get('text', '') for part in parts)
        try:
            return json.loads(text), usage
        except ValueError as exc:
            raise ProviderError('unparseable model output: %s' % exc) from exc


def _error_message(response):
    """Pull the provider's own explanation out of an error response.

    Worth the few lines: a retired-model 404 and a bad-key 404 look identical
    without it, and the API states which in plain language.
    """
    try:
        return (response.json().get('error') or {}).get('message') or response.text[:300]
    except ValueError:
        return response.text[:300]


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
