# Tasks

## 1. Build context

- [x] 1.1 Add `.dockerignore` excluding `env/`, `staticfiles/`, `.git/`, `.env`, `.env.*`,
      `__pycache__/`, `*.pyc`, `mediafiles/`, `media/`, `openspec/`, `loadtest/`,
      `.claude/`, `node_modules/`. **`docs/` stays in** — `survey/tests.py:17348` reads
      `docs/marketing/cohorts/`, and the suite must remain runnable inside the image.

## 2. Static assets at build time

- [x] 2.1 `Dockerfile`: add `RUN python manage.py collectstatic --no-input` after `COPY . $APP_HOME`
      and before `RUN chown -R app:app $APP_HOME`, so the collected tree is owned by `app`.
- [ ] 2.2 Verify the build succeeds with no `SECRET_KEY` / database in the environment
      (`settings.py:28` supplies the fallback). Not verifiable locally — `load_dotenv` picks up the
      worktree's `.env`, which the image never has. Confirmed by the Render build instead (4.1).

## 3. Migrations at pre-deploy

- [x] 3.1 `render.yaml`: add `preDeployCommand` to the `mapsurvey` web service —
      `python manage.py migrate && python manage.py createsuperuser --noinput || true`.
      Web service only; not the worker, not the cron. YAML parses; no other service carries it.
- [x] 3.2 `entrypoint.sh`: wrap `migrate`, `collectstatic` and `createsuperuser` in
      `if [ -z "$RENDER" ]`, leaving the local path unchanged. Keep the existing
      `DATABASE_URL`-gated Postgres wait as it is — it answers a different question.

## 4. Verification

- [x] 4.0 Entrypoint branching, exercised against a stubbed `python`: with `RENDER` unset →
      `migrate`, `collectstatic`, `createsuperuser`, then exec; with `RENDER=true` → straight to
      exec, no management command at all; with no `DJANGO_SUPERUSER_USERNAME` → superuser skipped.
      `sh -n` clean.
- [ ] 4.1 Build the image and confirm `staticfiles/` is present inside it, owned by `app`, with the
      manifest (`staticfiles.json`) generated. **A local build could not complete** — `apt-get
      install ... gdal-bin` stalled for 30 min at zero CPU on a Debian mirror, unrelated to this
      change (that layer is untouched). Do this on the PR preview build, which is also the only
      place `preDeployCommand` can be exercised at all.
- [ ] 4.2 Confirm the image still starts locally with `RENDER` unset — migrations applied,
      superuser created, gunicorn serving. Blocked on 4.1.
- [ ] 4.3 On the PR preview: confirm the deploy log shows the pre-deploy migrate running *before*
      the instance swap, and the container start going straight to gunicorn.
- [x] 4.4 Run `./run_tests.sh survey` — no application code changes, so this is a regression check
      that nothing in the static pipeline moved. 1047 tests, OK (skipped=1).

## 5. Measurement (informs the follow-up disk-removal change)

- [ ] 5.1 Read the current 502 window off Render's deploy logs for the last deploy (stop of the old
      instance → first successful request on the new one) and record it in `design.md`.
- [ ] 5.2 After this change is deployed, record the same number and the delta.
