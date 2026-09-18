# render-deployment — delta for worker-drain-hard-bound

## ADDED Requirements

### Requirement: A worker's exit is bounded and never leaves the service without an acceptor
The web service SHALL bound every gunicorn worker's exit: a worker that stops serving — its
request budget is spent or the master received a deploy's SIGTERM — SHALL be gone within
`--graceful-timeout` regardless of the state of its request threads, and a budget recycle
SHALL NOT begin while another worker of the same master is already leaving. Every connection
handed to a request thread SHALL carry a socket timeout equal to `--timeout`, so a peer that
stops sending or reading releases the thread. A worker the master aborts SHALL print the stack
of every thread before it dies. `GUNICORN_GRACEFUL_TIMEOUT`, `GUNICORN_THREADS`,
`GUNICORN_MAX_REQUESTS` and `GUNICORN_MAX_REQUESTS_JITTER` SHALL be environment variables
declared in `render.yaml`.

#### Scenario: A silent peer at recycle time
- **WHEN** a worker's request budget is spent while one of its threads is blocked reading a request a peer never completes
- **THEN** the worker stops accepting, serves what it holds, and exits within `--graceful-timeout`, logging how many request threads it abandoned; the master spawns its replacement at once and no request is failed or delayed beyond a few seconds (`scripts/gunicorn_recycle_check.py --poison N` reports zero failures, zero `WORKER TIMEOUT`, no request over 5 s)

#### Scenario: Two workers spend their budgets together
- **WHEN** the second worker of a master reaches its request budget while the first is still draining
- **THEN** the second keeps accepting and serving, and recycles only after the first is gone

#### Scenario: A deploy stops every worker
- **WHEN** the master receives SIGTERM
- **THEN** every worker drains and exits within `--graceful-timeout` without waiting for one another

#### Scenario: A blocked thread outside a recycle
- **WHEN** a peer sends part of a request and then nothing for `--timeout` seconds
- **THEN** the thread serving it logs a socket error and returns to the pool; the worker keeps serving throughout

#### Scenario: The master aborts a worker
- **WHEN** the master sends SIGABRT to a worker that stopped heartbeating
- **THEN** the worker's log carries the stack of every one of its threads before the exit

#### Scenario: Sizing tunable without rebuild
- **WHEN** an operator changes `GUNICORN_GRACEFUL_TIMEOUT`, `GUNICORN_THREADS`, `GUNICORN_MAX_REQUESTS` or `GUNICORN_MAX_REQUESTS_JITTER` in the Render dashboard and restarts the service
- **THEN** gunicorn starts with the new values and no image rebuild is needed
