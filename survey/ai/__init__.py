"""AI plumbing shared by generation features.

Survey draft generation lives here today; AI analytics (#92) and AI response
triage (#95) are expected to reuse `client.py` (provider access) and the
`AIGenerationEvent` log (`kind` enum) — add sibling modules, do not fork the
client. See openspec/changes/ai-survey-generator/design.md.
"""
