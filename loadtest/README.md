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

Run the identical scenario against two previews — one from the `loadtest-baseline`
branch (master's app: single sync worker, no persistent DB connections) and one from
the fix branch — and compare. Measured 2026-08-03, 25 students over 30 s:

| | baseline (1 sync worker) | fix, workers only | fix + `CONN_MAX_AGE` |
|---|---|---|---|
| 5xx responses | 0 | 0 | **0** |
| page load p95 | 7 435 ms | 12 107 ms (!) | **502 ms** |
| requests served | 1 239 | 1 111 | **2 401** |
| submits accepted | 100 % | 100 % | **100 %** |

Two lessons baked into the scenario:

1. At this scale the baseline fails on **latency**, not errors — Render's proxy queues
   patiently, so `page_load_ms` is the discriminating threshold. The 502 storm of the
   real incident needs a bigger crowd than a single-IP test can generate (see below).
2. The middle column is why this harness exists: adding workers **without** persistent
   DB connections made p95 *worse* than the single worker — eight concurrent slots
   multiplied per-request Postgres connection forks and pegged the 0.1-vCPU database
   while web CPU idled. A deploy that "obviously fixes it" measurably regressed it.

Thresholds in the script fail the run automatically if the branch does not meet the
right-hand column.

## Single-IP limits (why STUDENTS defaults to 25)

k6 sends all traffic from one machine. Past roughly this concurrency Render's edge
anti-abuse starts answering 502 instantly (≈17 ms, fixed ~218 KB body) without the app
ever seeing the request. The script counts those separately (`edge_throttled`) and
declares the run invalid if any occur — those numbers describe Render's DDoS
protection, not our gunicorn. A real lecture hall behind one campus NAT is far below
this threshold (each student loads the page once — with Cloudflare caching static,
that's ~2 origin requests per student spread over minutes, vs. k6's continuous
looping), but it is not zero risk; see the PR discussion.

## Reading the results

The script prints a short summary and writes `summary.json` for the full metric set.
Alongside it, check the Render dashboard for the preview instance:

- **Memory** must stay under ~350 MB. Two workers cost roughly 2 × 110 MB against a
  512 MB limit; if memory approaches the limit, lower `WEB_CONCURRENCY` or
  `GUNICORN_THREADS` (both are env vars, no rebuild needed).
- **HTTP 502/499** should be absent for the branch run.

Note that preview instances start cold. The script issues a warm-up request in `setup()`
so container start does not land inside the measured window.
