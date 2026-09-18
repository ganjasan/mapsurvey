## 1. Worker

- [x] 1.1 `enqueue_req`: after `conn.init()`, `conn.sock.settimeout(self.cfg.timeout)` before the pool submit (D1)
- [x] 1.2 `handle_exit` override sets `_terminating`; budget recycle acquires the per-master `flock` non-blocking, otherwise defers (`alive = True`, `nr = max_requests - 25`) and re-enters the loop (D3)
- [x] 1.3 `drain()` and the final `futures.wait` share one `graceful_timeout` deadline; after it, close the main thread's Django connections, log `Worker exiting (pid: N), M request threads abandoned`, `os._exit(0)` (D2)
- [x] 1.4 `handle_abort` override dumps every thread's stack (`faulthandler`) before gunicorn's handler (D4)
- [x] 1.5 Module docstring: the 2026-09-18 mechanism and the four behaviours, numbers from the harness

## 2. Reproduction harness

- [x] 2.1 `scripts/gunicorn_recycle_check.py`: `--poison N` opens N half-request connections before the parallel run and holds them; pass criteria add "no `WORKER TIMEOUT`" and "no request over 5 s" (D6)
- [x] 2.2 Run `--worker-class gthread --poison 2 --timeout 20` (expected red: failures, a `WORKER TIMEOUT`) and `--worker-class mapsurvey.gunicorn_workers.DrainingThreadWorker --poison 2` and `--poison 3` (must be green; N ≥ threads per worker is pool saturation, not a recycle test); record the numbers in the script docstring
- [x] 2.3 Run the existing four scenarios on the draining worker — still zero failures

## 3. Configuration

- [x] 3.1 `Dockerfile` CMD: `--graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-10}`
- [x] 3.2 `render.yaml`: `GUNICORN_GRACEFUL_TIMEOUT=10`, `GUNICORN_THREADS=8`, `GUNICORN_MAX_REQUESTS=1500`, `GUNICORN_MAX_REQUESTS_JITTER=1500`; rewrite the comment block (why recycling, what the worker class guarantees, the 2026-09-18 incident, rollback)
- [x] 3.3 `CLAUDE.md` layer-memory paragraph: the worker's guarantees and the harness's `--poison` run as the check after touching the gunicorn command line

## 4. Verification

- [x] 4.1 `./run_tests.sh survey` green (no Django code changes expected; guards against an import-time effect of the worker module)
- [x] 4.2 Review the diff against the spec scenarios; `openspec validate --strict`
