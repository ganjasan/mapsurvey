# Referrer tracking (Phase 2)

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: survey-analytics
**Created**: 2026-04-02
**Depends on**: [Survey event tracking](feature-survey-event-tracking.md)

## Description

Capture HTTP Referer header when respondents first open a survey, like Plausible does. Normalize referrer domains (instagram.com → "Instagram", t.co → "Twitter/X", mail.google.com → "Gmail", empty → "Direct"). Show referrer breakdown in analytics dashboard. No special links needed — the browser provides this automatically.

## Scope

- Capture `HTTP_REFERER` on session_start (store in SurveyEvent metadata or SurveySession field)
- Referrer normalization: map known domains to human-readable source names
- Dashboard: pie/bar chart of traffic sources
- Categories: Social (Instagram, Facebook, Twitter, LinkedIn), Email (Gmail, Outlook), Search (Google, Bing), Direct, Other

## Notes

- Free data — browser sends Referer header automatically
- Works alongside UTM (Phase 3) — referrer is fallback when no UTM present
- Some browsers/privacy settings strip Referer — "Direct" category will include these
- Depends on SurveyEvent model from feature-survey-event-tracking.md
