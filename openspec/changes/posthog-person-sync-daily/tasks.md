## 1. Cron

- [x] 1.1 Append `python manage.py sync_posthog_person_properties` to `reclaim.sh` after `notify_lapsed`, with a comment, and update the header comment's list of steps
- [x] 1.2 Declare `POSTHOG_PROJECT_KEY` and `POSTHOG_API_HOST` (`sync: false`) on the `mapsurvey-preview-media-reclaim` cron in `render.yaml`

## 2. Verify

- [x] 2.1 `sh -n reclaim.sh` passes and the Blueprint parses (`python -c "import yaml; yaml.safe_load(open('render.yaml'))"`)
- [ ] 2.2 `python manage.py sync_posthog_person_properties --dry-run` runs locally

## 3. Rollout (owner)

- [ ] 3.1 Set both variables on the cron in the Render dashboard
- [ ] 3.2 After the next run, the log shows `updated N people` and PostHog has `plan=pro` on the paying creators
