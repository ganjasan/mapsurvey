# Sub-question Discoverability Testing

**Type**: idea
**Priority**: medium
**Area**: general
**Created**: 2026-04-14

## Description

Test whether users can find and use the sub-question feature in the survey editor. Currently only 4 of ~50 active users have used sub-questions. The "Add Sub-question" button (fa-sitemap icon) only appears on geo questions with no help text, onboarding hint, or visual emphasis — likely a discoverability problem.

## Proposed Approaches

1. **Ask in outreach replies** — Add a question to follow-up emails with Manuel, Galanthus, hmsbrito7: "Did you know you can add follow-up questions to map points?" Quick, free, natural context. Downside: only 3 people.

2. **Micro-task usability test** — Email 5-10 Tier 1A users with a concrete task: "Try adding a follow-up question that appears after someone places a point on the map. Let me know if you can figure out how — and how long it took." Tests real discoverability without hinting where the button is. Downside: asking users to spend time, low conversion expected.

3. **Meta-survey on mapsurvey.org** — Create a short survey that itself uses sub-questions as a demo (dogfooding). Ask about editor UX, which features users found, what was confusing. Send link to all users. Upside: demonstrates the feature in action, collects structured data. Downside: needs to be built.

## Notes

- Sub-question button: `fa-sitemap` icon, conditionally rendered only for point/line/polygon questions
- No backend restriction — UI-only gating
- Power user example: hmsbrito7 has 34 sub-questions (point → multichoice + text pattern)
- Consider improving discoverability regardless of test results (tooltip, help text, onboarding)
