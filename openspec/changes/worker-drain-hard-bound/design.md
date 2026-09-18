# Design: worker-drain-hard-bound

## Context

`mapsurvey.gunicorn_workers.DrainingThreadWorker` (PR #188) subclasses gunicorn 23.0's
`ThreadWorker`. Its `run()` copies the stock loop, then `drain()` stops accepting (closes the
worker's listener copies), serves what it already holds, and finally does what stock does:
`tpool.shutdown(False)`, `poller.close()`, `futures.wait(graceful_timeout)`, return. Stock
gthread's `TConn.init()` sets the client socket blocking with no timeout; a thread that entered
`handle()` for a socket that never completes its request sits in `recv()` for the life of the
worker. On 2026-09-18 both workers had such a thread when they recycled together:

| t (UTC) | worker 120 | worker 108 |
|---|---|---|
| 12:08:18 / :20 | budget spent, drain starts | budget spent, drain starts |
| +30 s | drain deadline (`graceful_timeout`) | same |
| +60 s | `futures.wait` deadline, "Worker exiting" | same |
| +91 s | arbiter `WORKER TIMEOUT` (60 s after last `notify()`), SIGABRT inside `t.join()`, SIGKILL | same |

The last `notify()` is the drain loop's; the atexit join never heartbeats. From 12:08:20 to
12:09:50 no process accepted on the listening socket: the proxy queued connections in the
kernel backlog (499 after ~50 s), the health check failed at 12:08:45, the proxy fast-failed
502 for a minute, Render restarted the instance at 12:10:53.

Constraints: Python 3.9 / gunicorn 23.0 (pinned in `Pipfile`); prod is one Standard instance
(1 CPU, 2 GB) with `WEB_CONCURRENCY=2`; PR previews run one worker on Starter; Render's proxy
health-checks `/` with a 5 s timeout and turns a failure into 502s and a restart.

## Goals / Non-Goals

**Goals:**
- A worker's lifetime after `alive` turns False is bounded by `--graceful-timeout`, whatever
  its threads are doing.
- At least one worker is accepting at every moment of a recycle.
- A silent peer costs a bounded amount of one thread's time, and the event is visible in logs.
- The next unexplained hang is diagnosable from the Render log (thread stacks).
- The reproduction harness is red on the defect and green on the fix.

**Non-Goals:**
- Serving layer bytes outside gunicorn (backlog #183).
- Identifying what sends half-requests in production; the proxy is the suspect and the fix is
  indifferent to the source.
- A third worker, async workers, or a different server. The memory story
  (`layer-memory-diet`) chose gthread on purpose.

## Decisions

**D1. Socket timeout per pooled connection, equal to `--timeout`.** `enqueue_req` is
reimplemented (four lines: `conn.init()`, `conn.sock.settimeout(cfg.timeout)`, submit, wrap)
because stock submits before the caller can touch the socket; `finish_request` later puts a
kept connection back to non-blocking for the poller, and the next `init()` + our line restore
the timeout. One value for read and write: a 60 s read budget does not cut off a respondent
uploading a photo on a slow mobile link, and a 60 s write budget does not cut off a slow
proxy on a 2.5 MB layer body. `socket.timeout` is an `OSError` without an errno, so stock
`handle()` logs it as `Socket error processing request.` with a traceback — kept on purpose:
it is the evidence the 2026-09-18 log did not have. *Alternative:* a shorter read timeout
(10 s) — rejected: uploads. *Alternative:* `SO_RCVTIMEO` on the listening socket — inherited
by accepted sockets, but stock code resets modes with `setblocking()`, which clears it.

**D2. Bounded exit ending in `os._exit(0)`.** `drain()` computes one deadline
(`monotonic() + graceful_timeout`) and both the drain loop and the final `futures.wait` use
what is left of it. Then: close this thread's Django connections (`connections.close_all()`),
log `Worker exiting (pid), N request threads abandoned` with N = threads still busy, and
`os._exit(0)`. `os._exit` skips the interpreter shutdown that joins pool threads
(`concurrent.futures`'s atexit hook) — that join is where the process hung. Abandoned threads
die with the process; their peers see a reset, which they would have seen from the SIGKILL
anyway, 60 s later and with the whole service down. `worker.tmp.close()` and the arbiter's own
"Worker exiting" line in the child's `finally` are skipped too; our log line replaces the
latter and says more. *Alternative:* `tpool.shutdown(cancel_futures=True)` — cancels queued
futures only, cannot interrupt a thread in `recv()`. *Alternative:* daemon threads for the
pool — `ThreadPoolExecutor` threads are non-daemon by design in 3.9 and the join is in
`threading._shutdown` regardless.

**D3. One recycle at a time, by `flock`.** `handle_exit` (SIGTERM) is overridden to set
`_terminating`; when the run loop ends and `_terminating` is False the exit is a budget
recycle, and the worker tries `flock(LOCK_EX | LOCK_NB)` on
`<tmpdir>/gunicorn-drain-<master pid>.lock`. Success → drain. Failure → another worker is
leaving: set `alive = True`, `nr = max_requests - 25`, and re-enter the loop; the next 25
requests are served normally and the check repeats. The kernel releases the lock when the
holder dies, so a holder that gets SIGKILLed cannot wedge the other. The lock file is opened
once in `init_process`; a failure to open it (read-only tmp) logs a warning and disables the
mutual exclusion rather than the worker. SIGTERM bypasses the lock: on a deploy every worker
leaves and the new instance serves. With `WEB_CONCURRENCY=1` (previews) the lock is always
free. *Alternative:* larger jitter — statistical, and workers booted by one deploy stay
aligned for their whole life (today's were 2 s apart with jitter 60). *Alternative:* a
shared-memory counter — more code for the same guarantee.

**D4. `handle_abort` dumps every thread's stack.** The override calls
`faulthandler.dump_traceback(all_threads=True)` and then gunicorn's handler (`worker_abort`
hook, `sys.exit(1)`). A Python-level signal handler is enough: on 2026-09-18 gunicorn's own
`handle_abort` ran inside the `lock.acquire()` the main thread was stuck in (that is where
the `SystemExit: 1` in the log came from), so the dump would have run there too.
`faulthandler.register()` refuses SIGABRT (reserved for `enable()`), and `enable()` would
replace gunicorn's handler rather than precede it. No `-c gunicorn.conf.py`: the worker class
already carries the worker-side behaviour and the Dockerfile command line stays one line. The
dump is what would have named the blocked call on 2026-09-18 within a minute.

**D5. Numbers.** `graceful_timeout` 30 → 10: with D2 this is the longest a worker with a
blocked thread takes to leave (the drain cannot tell a blocked future from a slow one, so it
waits the whole budget) and the other worker serves meanwhile; and a request that has not finished in 10 s after the worker stopped accepting is
one of the heavy-layer serves (≤1.7 s measured) or already dead. `GUNICORN_THREADS` 4 → 8:
16 slots so two tabs of one creator with eight layers do not take the service; threads are
cheap in this I/O-bound process and the DB holds 16 persistent connections against a limit of
97. `GUNICORN_MAX_REQUESTS` 300 → 1500 and jitter 60 → 1500: an eight-layer preview open is
~20 requests, so 300 was 15 opens; prod is on 2 GB now and the gzip storage cut retention; the
jitter spread keeps two workers from ever having the same budget. All four stay env-tunable
from the dashboard without a rebuild (the `render-deployment` spec's existing rule).

**D6. Harness is the test.** The worker is not Django code; the reproduction script is the
verification, as for #188. It gains `--poison N` (N connections that send
`GET /small HTTP/1.1\r\nHost: x\r\n` and go silent) and two pass criteria beyond "no failed
requests": no `WORKER TIMEOUT` in gunicorn's output and no request slower than 5 s. Stock
`gthread` with `--poison 2` is the red run (76 failed requests in the parallel scenario, a
`WORKER TIMEOUT`, worst 5 s at `--timeout 20`); the draining worker with `--poison 2` and
`--poison 3` must be green. N must stay below the threads per worker: N silent peers hold N
threads for `--timeout` seconds, so N ≥ 4 in the harness is pool saturation — not the defect
this change fixes, and not something any worker class can serve through.

## Risks / Trade-offs

- [`os._exit` skips Python-level cleanup] → Django connections of the main thread are closed
  explicitly first; other threads' connections are closed by the kernel and Postgres logs
  "unexpected EOF on client connection" for each — cosmetic, and only for abandoned threads,
  which the log line counts.
- [Socket timeout turns a slow legitimate client into an error after 60 s] → 60 s equals the
  request timeout the arbiter already enforces on the worker; a client slower than that was
  never going to get a response.
- [A deferred recycle keeps a worker with a spent budget alive] → at most 25 requests per
  retry, and the holder is gone within `graceful_timeout` (10 s), so the deferral is
  seconds; memory growth in that window is one request's.
- [8 threads share one CPU] → gthread threads block on I/O most of the time; the load test
  from `web-concurrency` sized CPU at 2×4 with headroom; if CPU shows saturation the knob is
  in the dashboard.
- [Lock file under `/tmp` inside the container] → per-master pid, created at worker start,
  unlinked never (tmpfs dies with the container); a stale file from a previous master is a
  different name.

## Migration Plan

1. Merge; the image rebuilds with the new CMD; `render.yaml` sync applies the env values.
2. Watch the first recycles in the Render log: `Worker exiting (pid), 0 request threads
   abandoned` is the healthy line; a non-zero count names a silent peer that D1 timed out.
3. Rollback is environment only: `GUNICORN_WORKER_CLASS=gthread` restores stock behaviour,
   the four numbers restore the old sizing; no image change needed.

## Open Questions

- None blocking. Whether Render's proxy is the source of half-requests can be checked later
  from the `Socket error processing request` lines (their timing against 499s).
