## Context

The web service runs a single Docker image that also backs the Celery worker and the
acquisition-metrics cron, all three sharing `entrypoint.sh`. The web service mounts a 1 GB
persistent disk for uploaded media.

Render's zero-downtime deploy works by starting the new instance, waiting for `healthCheckPath` to
pass, then shifting traffic and retiring the old one. That requires both instances to exist at
once. A Render disk cannot be attached to two instances simultaneously, so any service with a disk
is both pinned to one instance and excluded from zero-downtime deploys — Render stops the old
instance first. The 502 window is therefore structural until the disk is gone.

Its *length*, however, is ours. Today it contains a full static-asset rebuild, a migration run, and
a superuser check, none of which need to be there.

## Goals / Non-Goals

**Goals**

- Remove from the outage window every step that can run earlier — at image build or at pre-deploy.
- Keep `docker compose up` working exactly as it does now for local development, with no extra
  manual steps.
- Make a broken `{% static %}` reference fail the build rather than the running production service.
- Stop the worker and the cron from running migrations they have no business running.

**Non-Goals**

- Eliminating the 502 window. That needs the disk gone (follow-up change).
- Horizontal scaling, `numInstances`, or health-check tuning. All of that belongs with the disk
  removal, where it first becomes possible.
- Changing what the migrations do, or the static pipeline itself (`CompressedManifestStaticFilesStorage`
  stays).

## Decisions

### D1. `collectstatic` runs in the image, not at start

Added to the `Dockerfile` after `COPY . $APP_HOME` and **before** the existing
`RUN chown -R app:app $APP_HOME`, so the generated `staticfiles/` tree is owned by `app` like
everything else.

`settings.py` makes this safe to run without any deploy configuration: `SECRET_KEY` falls back to
`'secret'` (`settings.py:28`) and `DEBUG` to `0`, and `collectstatic` touches no database. The build
therefore needs no build-time secrets.

**Why not keep `--clear`?** `--clear` exists to purge a stale `STATIC_ROOT` between runs. In a
fresh image layer there is nothing to purge, and locally the new `.dockerignore` keeps the host's
`staticfiles/` out of the build context in the first place. Dropping it also drops the risk of a
half-cleared tree if the build is interrupted.

**Interaction with `USE_S3`.** When `USE_S3=TRUE`, `STATICFILES_STORAGE` becomes the S3 backend and
`collectstatic` would need AWS credentials at build time to upload. `USE_S3` is not set on any
Render service today, so the build correctly produces local static assets served by WhiteNoise.
This constraint has to be revisited by the media-to-S3 follow-up, which should move *media* to S3
without dragging *static* along — see Open Questions.

### D2. `migrate` runs as Render's pre-deploy command, not at start

`preDeployCommand` runs after the new image is built and **before** the old instance is replaced,
which is exactly the window we want for schema changes. A failing pre-deploy aborts the deploy with
the current version still serving — strictly better than today, where a failing migration takes the
site down because the old instance is already gone.

`createsuperuser --noinput` joins it in the same command. It is idempotent (`|| true` today, because
it fails once the user exists) and has no reason to sit in the start path.

Command: `python manage.py migrate && python manage.py createsuperuser --noinput || true`

The `|| true` binds to the `createsuperuser` half only; a failing `migrate` short-circuits the `&&`
and fails the pre-deploy, which is the behaviour we want.

### D3. The entrypoint branches on `RENDER`, not on `DATABASE_URL`

Render sets `RENDER=true` in every service's environment. The entrypoint already branches on
`DATABASE_URL` to decide whether to wait for a local Postgres, but that variable is about *which
database*, not *which platform*, and reusing it would couple two unrelated decisions. `RENDER` says
what is actually meant: these steps are handled by the platform's deploy pipeline.

Locally — `docker compose up`, and any `docker run` of the image — `RENDER` is unset, so the
entrypoint keeps running `migrate`, `collectstatic` and `createsuperuser` exactly as today. There is
no new setup step for a developer, and no local workflow that silently starts skipping migrations.

Note that the local runtime `collectstatic` is now redundant with D1 for the common case, but it is
kept: it costs a second or two on a developer machine and it covers image reuse against a checkout
whose assets have moved on.

### D4. The worker and the cron stop migrating

They share the entrypoint, so gating on `RENDER` removes `migrate` from them too. Only the web
service gets a `preDeployCommand`, which makes the web service the single place migrations are
applied — the correct arrangement, and one that removes a latent race where the worker and the web
service could migrate concurrently during a Blueprint sync.

### D5. `.dockerignore`

Excludes `env/`, `staticfiles/`, `.git/`, `.env*`, `__pycache__/`, `mediafiles/`, `media/`, test and
tooling directories. Two reasons, in order of importance:

1. **Reproducibility.** With `collectstatic` in the build, a host `staticfiles/` copied into the
   context would be overwritten by the build step — but any *other* stale artifact in the context
   still lands in the image. The build should depend on tracked sources only.
2. **Not shipping secrets and junk.** `.env` and the `env/` virtualenv currently enter every locally
   built image. On Render the context is a clean clone so no secret is exposed there, but a local
   image should not carry credentials either.

## Risks / Trade-offs

- **The worker can briefly run against a schema the web service has already migrated.** Pre-deploy
  applies migrations before the web instance swaps, and the worker deploys independently. This is
  the standard trade-off of pre-deploy migrations and the usual mitigation applies: additive,
  backward-compatible migrations. It replaces a worse race (two services migrating at once).
- **Pre-deploy adds build-to-live latency.** The migration time moves out of the outage window but
  stays in the total deploy time. That is the point of the change.
- **A migration that must run *after* the new code is live has nowhere to go.** None exist today;
  should one appear, it runs as a one-off Render job rather than moving the pipeline back.
- **Local and Render start paths now differ.** Mitigated by the branch being one variable in one
  file, and by local keeping the strictly-more-work path — a developer cannot get a "works on
  Render, not locally" surprise from it.

## Migration Plan

No data migration. Deploy order is enforced by the Blueprint itself: `render.yaml`, `Dockerfile` and
`entrypoint.sh` land in the same commit, so the image that skips runtime migrations is the same one
whose service definition carries `preDeployCommand`. There is no intermediate state in which
migrations are run by nobody.

Rollback is a `git revert` of the same commit.

## Open Questions

- **Does `healthCheckPath: /` actually return 200?** `/` redirects to login or the editor. It does
  not matter today (with a disk, Render is not gating traffic on it), but it becomes load-bearing
  the moment zero-downtime deploys are enabled. The follow-up change should point the health check
  at a cheap, unconditional 200 — `/robots.txt` is what `docker-compose.yml` already uses for the
  local health check.
- **How long is the window today, and after?** Worth reading off Render deploy logs before and
  after, so the follow-up (disk removal) is argued from a measured number rather than a guess.
- **Should `USE_S3` be split into `USE_S3_MEDIA` and `USE_S3_STATIC`?** The follow-up needs S3 for
  media while static stays in the image behind WhiteNoise (which is faster and cache-busted by hash
  already). The current single flag cannot express that.
