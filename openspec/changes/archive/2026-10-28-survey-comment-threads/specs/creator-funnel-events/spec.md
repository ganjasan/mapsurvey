## ADDED Requirements

### Requirement: Comment thread activity is emitted as creator events
The system SHALL emit `comment_thread_opened`, `comment_reply_posted` and
`comment_thread_resolved` through `product_events.emit` when a member opens a thread, posts a
reply or resolves a thread. Properties SHALL be limited to `survey_id`, `organization_id` and
`anchor_kind`; the comment body, mentions and attachment names SHALL never be attached.
Without a PostHog client the emission SHALL be a silent no-op.

#### Scenario: Reply emits one event
- **WHEN** a member posts a reply in a thread on a question
- **THEN** exactly one `comment_reply_posted` is captured with `distinct_id` = the member's user id and `anchor_kind` = `question`, and the payload contains no body text

#### Scenario: No PostHog client, no error
- **WHEN** `POSTHOG_PROJECT_KEY` is unset and a thread is resolved
- **THEN** the request succeeds and nothing is captured
