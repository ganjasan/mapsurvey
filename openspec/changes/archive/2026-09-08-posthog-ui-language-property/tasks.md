## 1. Implementation

- [x] 1.1 `product_events.set_person_properties(user_id, props)` — `posthog.set`, no-op when disabled, never raises
- [x] 1.2 `set_creator_language` calls it with `{'ui_language': language}` after saving the preference
- [x] 1.3 `sync_posthog_person_properties` adds `ui_language` from `CreatorPreferences` (`''` when absent)
- [x] 1.4 Tests (GIVEN/WHEN/THEN): switch sends the property and still redirects; dry-run sync includes `ui_language`; disabled PostHog is silent

## 2. Rollout

- [x] 2.1 Suite green; PR; merge
- [ ] 2.2 After deploy: run `sync_posthog_person_properties` in the production container; add an AARRR tile "activation by ui_language"
