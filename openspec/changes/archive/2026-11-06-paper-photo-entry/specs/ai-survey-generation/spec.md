# ai-survey-generation — delta for paper-photo-entry

## MODIFIED Requirements

### Requirement: Provider-agnostic LLM client
LLM access SHALL go through a provider interface (`complete_structured(system, user,
schema, max_tokens, images=None)`), selected by `AI_PROVIDER` (default `anthropic`). Vendor SDKs SHALL
be imported only inside `survey/ai/client.py`; provider failures SHALL be normalized to
`NotConfigured` (credentials absent) or `ProviderError` (call failed). The Anthropic
implementation SHALL use the official SDK with model `AI_SURVEY_DRAFT_MODEL` (default
`claude-opus-5`), an explicit request timeout, and structured JSON output. A Gemini
implementation (`AI_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL`) SHALL be available
over plain HTTP without adding a vendor SDK, adapting the shared schema to that provider's
JSON Schema subset at the client boundary.

`images` SHALL be an optional list of `(mime_type, bytes)`; each provider SHALL place them in its
own request shape (Gemini: `inline_data` parts before the user text; Anthropic: `image` content
blocks), and a call without `images` SHALL produce the same request body as before the parameter
existed. No module outside `survey/ai/client.py` SHALL know how an image is encoded for a provider.

Reasoning effort SHALL be a value this system sets rather than a provider default it inherits: the
Gemini implementation SHALL send `AI_THINKING_LEVEL` (default `medium`, matching the provider's own
default so the setting's introduction changes no behavior) as `generationConfig.thinkingConfig.thinkingLevel`,
and SHALL omit `thinkingConfig` entirely when the setting is empty.

Usage returned by a provider SHALL additionally carry reasoning-token usage where the provider
accounts for it. Reasoning usage SHALL be read from the provider's own reasoning-token field when
present, and otherwise derived as total minus prompt minus candidate tokens when that difference is
positive. When neither yields a value, reasoning usage SHALL be absent — never zero, because a
provider that does not report reasoning and a generation that reasoned for zero tokens are
different facts.

`complete_structured` SHALL accept an optional `on_progress` callback. A provider able to stream
SHALL invoke it as content arrives; a provider unable to stream SHALL remain conformant by never
invoking it, and its behavior SHALL be unchanged from the non-streaming case. An exception raised by
the callback SHALL NOT fail the generation: progress reporting is strictly less important than the
draft it describes.

#### Scenario: Credentials absent
- **WHEN** the selected provider's credentials are not configured and generation is invoked programmatically
- **THEN** `NotConfigured` is raised before any network call and the event outcome is `not_configured`

#### Scenario: Switching providers changes no other module
- **WHEN** `AI_PROVIDER` selects a different implemented provider
- **THEN** prompts, validation, materialization and the orchestrator behave identically, and only the client's request/response translation differs

#### Scenario: Provider call fails
- **WHEN** the provider API times out, returns a non-2xx error, or refuses the request
- **THEN** the failure is recorded as `provider_error` with detail, nothing is written to survey tables, and the user sees a retry-or-create-empty message

#### Scenario: Thinking level is sent on every Gemini request
- **WHEN** `AI_THINKING_LEVEL` is set to a non-empty value and a Gemini generation is requested
- **THEN** the request body carries that value at `generationConfig.thinkingConfig.thinkingLevel`

#### Scenario: Thinking level can be disabled entirely
- **WHEN** `AI_THINKING_LEVEL` is set to an empty string
- **THEN** the request body contains no `thinkingConfig` key at all, so a provider that rejects the field can be worked around by configuration rather than by a deploy

#### Scenario: Provider reports reasoning tokens directly
- **WHEN** the provider response's usage metadata contains a reasoning-token count
- **THEN** that value is carried on the returned usage, without consulting the derived fallback

#### Scenario: Provider accounts for reasoning only in the total
- **WHEN** usage metadata carries no reasoning-token field but its total exceeds prompt plus candidate tokens
- **THEN** the difference is carried as reasoning usage

#### Scenario: Reasoning usage is unavailable
- **WHEN** usage metadata carries no reasoning-token field and its total does not exceed prompt plus candidate tokens
- **THEN** reasoning usage is absent rather than zero

#### Scenario: Streaming provider reports progress
- **WHEN** a progress callback is supplied and the provider streams its response
- **THEN** the callback is invoked as content arrives, and the parsed blob and usage returned at the end are the same as they would be without a callback

#### Scenario: Progress callback is optional
- **WHEN** no progress callback is supplied
- **THEN** the provider behaves exactly as it does for a non-streaming call and nothing about the result changes

#### Scenario: A failing progress callback cannot fail the draft
- **WHEN** the supplied callback raises
- **THEN** the generation continues and completes normally

#### Scenario: Image parts on a Gemini request
- **WHEN** `complete_structured` is called with one JPEG in `images`
- **THEN** the Gemini request body carries one `inline_data` part with `mime_type` `image/jpeg` and the base64 bytes before the text part

#### Scenario: No images, no change
- **WHEN** `complete_structured` is called without `images`
- **THEN** the request body is identical to the one built before the parameter existed
