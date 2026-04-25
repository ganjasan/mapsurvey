# Funnel monitoring: source → registration → survey → responses

**Type**: feature
**Priority**: high
**Area**: backend
**Created**: 2026-04-25

## Description

Internal funnel monitoring that tracks each user's journey through the platform stages: traffic source (referrer post, link from another survey, direct, organic search) → registration → first survey created → first question added → published → first response → 5+/10+/N responses. Surface drop-off rates per stage so we can see where users disappear and quantify the impact of UX changes (e.g., the AI survey-creator agent).

## Notes

- Today's blind spot: we know overall registration count and per-survey response counts, but not where the funnel breaks. Need this to quantify any conversion-improvement work.
- Initial event set:
  - `visit` (with referrer + UTM)
  - `register`
  - `survey.create_draft`
  - `survey.add_first_question`
  - `survey.publish`
  - `survey.first_response`
  - `survey.responses_5/10/50/100`
  - `editor.session_start` / `editor.session_end` (time-on-task in editor)
- Capture referrer + UTM params on landing; persist into the user record on registration so we can attribute regs to channels (Reddit posts, Maptionnaire alternative search, direct outreach links, etc.).
- Per-survey funnel view too: published survey → responses → completion rate (per-section drop-off for respondents).
- Storage: separate `analytics_events` table (append-only, no PII beyond user_id and IP→country) to avoid bloating production tables.
- Dashboard: simple admin-only Sankey or stage-bar at `/editor/admin/funnel/`. No third-party (PostHog/Mixpanel) required for v1 — keep data in our own DB.
- Pairs with `idea-ai-survey-creator-chat-agent.md` — needed to measure that feature's lift.
- Existing data points already in DB that can bootstrap this retroactively: `auth_user.date_joined`, `SurveyHeader.created_by_id` + creation timestamp, `SurveySession.start_datetime`. We can already chart historical conversion from registrations.
