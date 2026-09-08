## 1. Fix

- [x] 1.1 In `DirectActivationView.post`, send `user_activated` after a successful `activate()`; comment why (`form_valid` bypassed)
- [x] 1.2 Test (GIVEN/WHEN/THEN): real POST to `/accounts/activate/` emits exactly one `creator_activated_account`; replay emits none

## 2. Rollout

- [x] 2.1 Run the survey suite; PR; merge
- [ ] 2.2 After deploy: `python manage.py backfill_posthog_events` in the production container (idempotent) so August/September activations appear; confirm `activated_live` > 0 for the first live activation
