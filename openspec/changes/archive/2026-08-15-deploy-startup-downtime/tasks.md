# Tasks

## 1. Build context

- [x] 1.1 Add `.dockerignore` excluding `env/`, `staticfiles/`, `.git/`, `.env`, `.env.*`,
      `__pycache__/`, `*.pyc`, `mediafiles/`, `media/`, `openspec/`, `loadtest/`,
      `.claude/`, `node_modules/`. **`docs/` stays in** — `survey/tests.py:17348` reads
      `docs/marketing/cohorts/`, and the suite must remain runnable inside the image.

## 2. Static assets at build time

- [x] 2.1 `Dockerfile`: add `RUN python manage.py collectstatic --no-input` after `COPY . $APP_HOME`
      and before `RUN chown -R app:app $APP_HOME`, so the collected tree is owned by `app`.
- [x] 2.2 Verify the build succeeds with no `SECRET_KEY` / database in the environment
      (`settings.py:28` supplies the fallback). Not verifiable locally — `load_dotenv` picks up the
      worktree's `.env`, which the image never has. Confirmed by the Render build: `docker build`
      there gets no service environment variables, and the image built and shipped regardless.

## 3. Migrations at pre-deploy

- [x] 3.1 `render.yaml`: add `preDeployCommand` to the `mapsurvey` web service. Web service only;
      not the worker, not the cron. **Shipped broken and fixed in a follow-up:** the inline
      `migrate && createsuperuser || true` failed in production — Render does not run
      `preDeployCommand` through a shell, so the list was parsed as arguments to `migrate`
      (`unrecognized arguments: manage.py createsuperuser || true`, exit 2). Now
      `preDeployCommand: "sh ./predeploy.sh"`.
- [x] 3.3 Add `predeploy.sh` (`set -e`; `migrate`; `createsuperuser || true` when configured).
      Verified against a stubbed `python`: createsuperuser failing → exit 0; no superuser
      configured → migrate only; migrate failing → exit 1, which aborts the deploy.
- [x] 3.2 `entrypoint.sh`: wrap `migrate`, `collectstatic` and `createsuperuser` in
      `if [ -z "$RENDER" ]`, leaving the local path unchanged. Keep the existing
      `DATABASE_URL`-gated Postgres wait as it is — it answers a different question.

## 4. Verification

- [x] 4.0 Entrypoint branching, exercised against a stubbed `python`: with `RENDER` unset →
      `migrate`, `collectstatic`, `createsuperuser`, then exec; with `RENDER=true` → straight to
      exec, no management command at all; with no `DJANGO_SUPERUSER_USERNAME` → superuser skipped.
      `sh -n` clean.
- [x] 4.1 Image build with the collectstatic step: verified on Render, which built and shipped it
      (deploy `dep-da08o8bf2k7s73caticg`, live 15:58:29). Production then served
      `/staticfiles/manifest.3e70cc262ba8.json` and hashed assets with 200s, so the manifest and the
      collected tree are present and readable by the `app` user. A local build could not be used to
      confirm this first — `apt-get install ... gdal-bin` stalled 30 min at zero CPU on a Debian
      mirror, in a layer this change does not touch.
- [x] 4.2 Local start with `RENDER` unset: the entrypoint path is verified by 4.0 rather than by
      running the image, for the same build reason. The local branch is unchanged from what has been
      running all along, and `docker-compose.yml` does not set `RENDER`.
- [x] 4.3 Confirmed on production (deploy `dep-da08o8bf2k7s73caticg`):
      `Starting pre-deploy: sh ./predeploy.sh` 15:57:18 → `Operations to perform:` / `Running
      migrations:` / `No migrations to apply.` 15:57:37 → `Pre-deploy complete!` 15:57:51 →
      `Listening at` 15:58:21 → live 15:58:29. **The site served real users throughout the
      pre-deploy** — a browser got 200 on `/` and every static asset at 15:57:51-52. The new
      instance's logs contain neither `Operations to perform:` nor `static files copied`. The only
      502 in the whole deploy was Render's own monitor at the swap instant (15:58:29); none on
      `mapsurvey.org`.
- [x] 4.4 Run `./run_tests.sh survey` — no application code changes, so this is a regression check
      that nothing in the static pipeline moved. 1047 tests, OK (skipped=1).

## 5. Measurement (informs the follow-up disk-removal change)

- [x] 5.1 Baseline from the two deploys immediately before this one (app logs, `srv-d5v2t8shg0os73a52540`):
      instance `xrntx` — `Operations to perform:` 15:26:01.06 → `203 static files copied … 543
      post-processed` 15:26:05.72 → `Listening at` 15:26:09.56 = **8.5 s**; instance `p7vfm` —
      15:28:39.58 → 15:28:44.08 → 15:28:47.76 = **8.2 s**.
- [x] 5.2 After this change, instance `cgjqg`: **neither `Operations to perform:` nor `static files
      copied` appears at all** — the first app log is `Listening at` 15:50:32.30. ~8 s of Django work
      removed from the window. The window itself is not gone: the remainder is image pull, disk
      mount and container start, which only removing the disk addresses.
