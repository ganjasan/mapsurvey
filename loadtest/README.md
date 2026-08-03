# Load testing

Reproduces the lecture-hall burst that broke a real survey on 2026-07-13: ~45 students
opened a one-question point survey at the same time, the single gunicorn sync worker
serialized them, and Render's proxy returned 170 × 502. Only 4 of 45 sessions recorded
an answer; none finished.

## Why not localhost

A dev machine has many fast cores; a Render Starter instance has 0.5 CPU. Locally the
page renders in ~50 ms, so even a single worker drains 20 queued requests in about a
second and the failure never reproduces. A test that stays green before the fix proves
nothing after it. Run this against a **Render PR preview**, which inherits
`plan: starter` from `render.yaml` — the same hardware as production, with no live users
on it.

**Never run this against production.**

## Setup

Install k6 (single binary, no runtime):

```bash
# Debian/Ubuntu
sudo gpg -k && sudo gpg --no-default-keyring \
  --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

A PR preview starts with an **empty database**, so seed the survey first (idempotent).
Use the preview service's SSH address from the Render dashboard:

```bash
ssh srv-<preview-id>@ssh.oregon.render.com 'python manage.py seed_loadtest_survey'
# prints: uuid: <uuid>  /  path: /surveys/<uuid>/section_1/
```

## Run

```bash
k6 run -e BASE_URL=https://mapsurvey-pr-<N>.onrender.com \
       -e SURVEY=<uuid> \
       loadtest/lecture-burst.js
```

Options: `-e STUDENTS=50` (peak concurrent students, default 50), `-e RAMP=10s` (how fast
they arrive — 10 s models a link appearing on a lecture slide).

## Baseline vs fix

The number that matters is not throughput, it is whether anyone sees an error page. To
show the fix addresses *this* failure, run the identical scenario against two previews —
one from `master` (single sync worker) and one from the branch — and compare:

| | master (1 sync worker) | branch (2 × 4 gthread) |
|---|---|---|
| 5xx responses | expected > 0 | **must be 0** |
| page load p95 | expected multi-second | < 3 s |
| submits accepted | expected < 100 % | > 99 % |

Thresholds in the script fail the run automatically if the branch does not meet the
right-hand column.

## Reading the results

The script prints a short summary and writes `summary.json` for the full metric set.
Alongside it, check the Render dashboard for the preview instance:

- **Memory** must stay under ~350 MB. Two workers cost roughly 2 × 110 MB against a
  512 MB limit; if memory approaches the limit, lower `WEB_CONCURRENCY` or
  `GUNICORN_THREADS` (both are env vars, no rebuild needed).
- **HTTP 502/499** should be absent for the branch run.

Note that preview instances start cold. The script issues a warm-up request in `setup()`
so container start does not land inside the measured window.
