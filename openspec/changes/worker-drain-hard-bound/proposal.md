# Proposal: worker-drain-hard-bound

## Why

On 2026-09-18 12:08 UTC production answered nothing for ~90 seconds and Render restarted the
instance (health check timed out). Both gunicorn workers reached `--max-requests` two seconds
apart, stopped accepting, and neither could leave: each held a pool thread blocked in
client-socket I/O, so the drain ran to `graceful_timeout`, the interpreter then hung in
`atexit → concurrent.futures._python_exit → t.join()`, and the arbiter killed them 60 s later.
The replacement worker is spawned only when the old process is gone. Reproduced locally
(scratch `drain_check3.py`): gthread puts client sockets in blocking mode with **no timeout**,
so a peer that sends half a request and goes silent parks a thread forever; stock `gthread` +
two such connections gives the byte-identical traceback, `WORKER TIMEOUT` ×2 and 36 failed
requests. Postgres, Redis and the layer endpoint were ruled out with data (backlog #182).

Recycling exists for a reason (`layer-memory-diet`) and the draining worker (#188) fixed the
one-502-per-recycle defect; this change fixes what both left open: a worker's exit is not
bounded, and nothing keeps at least one worker accepting.

## What Changes

- `DrainingThreadWorker` sets a socket timeout (`--timeout`) on every connection it hands to
  its thread pool: a silent peer costs one thread for ≤60 s, never the process.
- The exit is hard-bounded: drain plus the wait for in-flight requests fit inside
  `--graceful-timeout`, after which the worker leaves with `os._exit(0)` and logs how many
  request threads it abandoned. The arbiter reaps it and spawns the replacement within
  seconds whatever a stuck thread is doing.
- Workers recycle one at a time: a worker whose request budget is spent takes a
  per-master `flock`; if another worker holds it, this one keeps serving and retries after a
  few more requests. A deploy's SIGTERM bypasses the lock — every worker must go.
- `faulthandler` is chained onto SIGABRT, so a worker the arbiter has to abort prints every
  thread's stack to the Render log first.
- `scripts/gunicorn_recycle_check.py` gains a "silent peers" scenario (half-request
  connections held open while workers recycle) and fails on any `WORKER TIMEOUT` or a request
  slower than a few seconds. Red on stock `gthread`, green on the draining worker.
- Tunables: `GUNICORN_GRACEFUL_TIMEOUT` (new, 10 s), `GUNICORN_THREADS` 4 → 8,
  `GUNICORN_MAX_REQUESTS` 300 → 1500, `GUNICORN_MAX_REQUESTS_JITTER` 60 → 1500 in
  `render.yaml`; the Dockerfile grows the graceful-timeout flag with the same env fallback.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `render-deployment`: a worker's exit is bounded and the service never loses its last
  accepting worker to a recycle (delta adds a requirement; the recycling requirement added by
  `layer-memory-diet`'s delta is untouched).

## Impact

- `mapsurvey/gunicorn_workers.py` — the four behaviours above; no new dependency
  (`fcntl`, `faulthandler`, `os` are stdlib).
- `scripts/gunicorn_recycle_check.py` — new scenario and stricter pass criteria.
- `Dockerfile` CMD, `render.yaml` env block and comments, `CLAUDE.md` layer-memory paragraph.
- Operations: 16 thread slots instead of 8 means 16 persistent Postgres connections
  (`CONN_MAX_AGE`) from the web service, against the basic-256 plan's limit of 97. Recycles
  become five times rarer; each is invisible to the proxy. Rollback is the env vars: the
  worker class back to `gthread` from the dashboard, the numbers back to their old values.
- Not in scope: moving layer bytes off the threads (backlog #183), the production source of
  half-requests.
