## Why

Every deploy of the web service returns 502 for as long as the new container takes to become
ready. Render's zero-downtime ("blue/green") deploy is unavailable to us: the service mounts a
persistent disk (`media-storage` at `/home/app/web/mediafiles`, `render.yaml`), and a Render disk
can be attached to exactly one instance at a time. Render therefore cannot run the old and new
instances side by side — it must stop the old one, detach the disk, and only then start the new
one. Removing the disk is a separate, larger change (media to S3); it is not in scope here.

What *is* in scope is that the outage window is far longer than the disk forces it to be, because
`entrypoint.sh` does all of the slow work *after* the old instance is already gone:

```sh
python manage.py migrate
python manage.py collectstatic --no-input --clear
python manage.py createsuperuser --noinput || true
exec gunicorn ...
```

- **`collectstatic --clear` rebuilds the entire static tree on every container start.** 203 files
  copied, 541 post-processed through `CompressedManifestStaticFilesStorage` (hashing + gzip/brotli
  of every asset). None of it depends on anything known only at runtime — it is pure build output
  being recomputed on a 0.5 CPU instance while the site is down.
- **Migrations run inside the outage window.** They can run before the old instance is stopped,
  which is what Render's pre-deploy command exists for.
- **`createsuperuser` runs on every start**, adding another Django boot to the window for something
  that is idempotent bookkeeping.

Two more consequences of the same layout:

- The Celery worker and the acquisition cron share this entrypoint, so **every worker restart and
  every nightly cron run also does a full `migrate` + `collectstatic`** before doing its job. The
  cron's real work takes seconds; its startup work does not.
- `CompressedManifestStaticFilesStorage` fails `collectstatic` on a dangling `{% static %}`
  reference. Today that failure happens at container start on production — the deploy is already
  committed, the old instance is already gone, and the result is a 502 that does not end. Moving
  the step into the image turns the same mistake into a failed build, which never reaches
  production.

## What Changes

- **`collectstatic` moves into the Docker image** (build time), before the `chown` that hands the
  tree to the `app` user. The runtime no longer rebuilds static assets.
- **`migrate` moves to Render's `preDeployCommand`** for the web service, so schema changes are
  applied while the current instance is still serving. `createsuperuser` joins it there.
- **`entrypoint.sh` skips both steps when running on Render** (detected via the `RENDER`
  environment variable Render sets) and keeps doing them otherwise, so `docker compose up` for
  local development is unchanged.
- **A `.dockerignore` is added.** The repository has none, so `COPY . $APP_HOME` currently copies
  the developer's local `env/` virtualenv, `staticfiles/`, `.git/`, and `.env` into the image. With
  `collectstatic` moving into the build, a stale host-built `staticfiles/` would otherwise be
  copied in and then overwritten — build output that depends on the developer's machine. On Render
  this is invisible (the build context is a clean clone); locally it is the difference between a
  reproducible image and a lucky one.

Not in scope: removing the persistent disk, moving media to S3, and the horizontal scaling that
unblocks. That is the follow-up change, and it is the one that actually delivers zero-downtime
deploys. This change only shortens the window that the disk makes unavoidable.

## Capabilities

### New Capabilities

- `deploy-startup`: what the container does between being started and serving traffic, which of
  those steps run at build time versus deploy time versus start time, and which run on Render
  versus locally.

## Impact

- `Dockerfile` — `collectstatic` at build, ordering against `chown`.
- `entrypoint.sh` — runtime `migrate` / `collectstatic` / `createsuperuser` gated on not-Render.
- `render.yaml` — `preDeployCommand` on the `mapsurvey` web service.
- `.dockerignore` — new file.
- No migration. No model changes. No application code.
- Behaviour on the Celery worker and the acquisition cron changes as a side effect: they stop
  running migrations and `collectstatic` at start. Neither should have been doing so.
