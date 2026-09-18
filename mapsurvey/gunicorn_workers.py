"""A gthread worker whose exit is bounded and that never leaves the service
without an acceptor (changes layer-memory-diet, worker-drain-hard-bound).

gunicorn's ThreadWorker (23.0) leaves its run loop when `alive` turns False —
after `--max-requests` requests, or on the SIGTERM a deploy sends — and then
does `tpool.shutdown(False)`, `poller.close()`, closes its listener copies and
waits only for the requests already running. Two kinds of connection fall
through that sequence and are reset without a response:

- connections the loop accepted during its last iteration: the acceptor runs
  inside `poller.select(1.0)` while `alive` is flipped by a request thread, so
  up to a second of accepts land in the poller and are never read;
- keep-alive connections the proxy reuses at that moment.

Measured locally with `--max-requests 4` (scripts/gunicorn_recycle_check.py):
8–11 resets per 60 requests, about one per recycle, with keep-alive on or off.
On production 2026-09-16 every worker recycle 502'd the creator whose request
happened to land on it, and every deploy's switch did the same. So this worker
stops accepting first — its listener copies leave the poller and close, so the
kernel hands new connections to the other worker and, once the arbiter spawns
it, the replacement — then keeps serving what it already accepted: readable
sockets are enqueued and answered with `Connection: close`, idle keep-alive
sockets are left to the keep-alive timeout, never closed early (the proxy may
already have written the next request on one), and a response that was built
while `alive` was still True keeps its connection registered too
(`finish_request`).

On 2026-09-18 that was not enough. Both workers spent their budgets two
seconds apart (jitter 60 keeps workers booted by one deploy aligned for life),
and each held a pool thread blocked in client-socket I/O: gthread's
`TConn.init()` makes the socket blocking with no timeout, so a peer that sends
half a request and goes silent parks a thread in `recv()` for the life of the
worker. The drain ran to `--graceful-timeout`, `futures.wait` ran another
`--graceful-timeout`, and the interpreter then hung in
`atexit → concurrent.futures._python_exit → t.join()` until the arbiter's
`WORKER TIMEOUT` and SIGKILL 60 s after the last heartbeat. The replacement is
spawned only when the old process is gone, so nothing accepted for ~90 s: the
health check failed, the proxy fast-failed 502, Render restarted the instance.
Stock gthread has the same hole (it also waits `graceful_timeout` on its
futures and then joins the pool); `--poison` in the reproduction script shows
it with two silent peers.

Four things bound the exit now:

- every connection handed to the pool carries a socket timeout of `--timeout`,
  so a silent peer costs one thread for that long, never the process;
- the drain and the final wait share one `--graceful-timeout` deadline, after
  which the worker logs how many request threads it abandons, dumps their
  stacks if any, and leaves with `os._exit(0)` — the interpreter shutdown that
  joined those threads never runs;
- workers recycle one at a time: a spent budget takes a per-master `flock`
  first, and a worker that cannot get it serves `RECYCLE_RECHECK_REQUESTS`
  more requests and asks again. A deploy's SIGTERM ignores the lock — every
  worker must go, the new instance serves;
- `handle_abort` dumps every thread's stack (`faulthandler`) before gunicorn's
  own SIGABRT handler runs, so a worker the arbiter aborts says where it was.
"""
import faulthandler
import fcntl
import os
import selectors
import sys
import tempfile
import time
from concurrent import futures
from functools import partial

from gunicorn.workers.gthread import ThreadWorker

# A worker whose budget is spent while another worker is leaving serves this
# many more requests before it asks for the recycle lock again. The holder is
# gone within --graceful-timeout, so the deferral is seconds, not a lifetime.
RECYCLE_RECHECK_REQUESTS = 25


class DrainingThreadWorker(ThreadWorker):

    _terminating = False    # SIGTERM/SIGQUIT: leave whatever the lock says
    _torn_down = False
    _drain_lock_fd = None

    # -- setup -------------------------------------------------------------

    def init_process(self):
        # One lock per master: the fd is opened after the fork, so each worker
        # holds its own open file description and flock() arbitrates between
        # them. The kernel releases it when the holder dies, SIGKILL included.
        path = os.path.join(tempfile.gettempdir(), 'gunicorn-drain-%d.lock' % os.getppid())
        try:
            self._drain_lock_fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        except OSError as exc:
            self.log.warning("Recycle lock unavailable (%s): workers may recycle together", exc)
        super().init_process()

    # -- signals -------------------------------------------------------------

    def handle_exit(self, sig, frame):
        self._terminating = True
        super().handle_exit(sig, frame)

    def handle_abort(self, sig, frame):
        # The arbiter aborts a worker that stopped heartbeating (SIGABRT, then
        # SIGKILL). Print every thread's stack first, then gunicorn's handler
        # (worker_abort hook, sys.exit). A Python-level handler is enough: on
        # 2026-09-18 it ran inside the lock.acquire() the main thread was stuck
        # in — faulthandler.register() refuses SIGABRT, and enable() would
        # replace gunicorn's handler instead of preceding it.
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
        sys.stderr.flush()
        super().handle_abort(sig, frame)

    def handle_quit(self, sig, frame):
        # SIGQUIT/SIGINT: leave now. Stock ends in sys.exit(0), which still
        # joins the pool threads at interpreter shutdown.
        self._terminating = True
        self.alive = False
        self.cfg.worker_int(self)
        self.tpool.shutdown(False)
        time.sleep(0.1)
        self._exit()

    # -- serving -------------------------------------------------------------

    def enqueue_req(self, conn):
        conn.init()
        # init() made the socket blocking with no timeout; a peer that sends
        # half a request and goes silent would hold this thread for the life
        # of the worker (2026-09-18). Bound every read and write instead.
        if self.cfg.timeout:
            conn.sock.settimeout(self.cfg.timeout)
        fs = self.tpool.submit(self.handle, conn)
        self._wrap_future(fs, conn)

    def run(self):
        for sock in self.sockets:
            sock.setblocking(False)
            server = sock.getsockname()
            self.poller.register(sock, selectors.EVENT_READ, partial(self.accept, server))

        while True:
            self._serve_until_stopped()
            if not self.is_parent_alive():
                self._terminating = True
            if self._terminating or self._acquire_recycle_lock():
                break
            # Another worker is on its way out; recycling now would leave the
            # service with no acceptor. Serve a few more and ask again.
            self.alive = True
            self.nr = self.max_requests - RECYCLE_RECHECK_REQUESTS

        deadline = time.monotonic() + self.cfg.graceful_timeout
        self.drain(deadline)
        self._torn_down = True
        self.tpool.shutdown(False)
        self.poller.close()
        futures.wait(self.futures, timeout=max(0.0, deadline - time.monotonic()))
        self._exit()

    def _serve_until_stopped(self):
        while self.alive:
            self.notify()
            if self.nr_conns < self.worker_connections:
                events = self.poller.select(1.0)
                for key, _ in events:
                    key.data(key.fileobj)
                result = futures.wait(self.futures, timeout=0, return_when=futures.FIRST_COMPLETED)
            else:
                result = futures.wait(self.futures, timeout=1.0, return_when=futures.FIRST_COMPLETED)
            for fut in result.done:
                self.futures.remove(fut)
            if not self.is_parent_alive():
                break
            self.murder_keepalived()

    def _acquire_recycle_lock(self):
        if self._drain_lock_fd is None:
            return True
        try:
            fcntl.flock(self._drain_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def finish_request(self, fs):
        """gthread's version closes a keep-alive connection when `alive` is
        already False — but that response went out WITHOUT `Connection: close`
        (the flag was still True when the response was built), so the proxy
        reuses the connection and meets a closed socket. Keep it registered
        until teardown instead: the next request on it is served during the
        drain (then with `Connection: close`) or the keep-alive timeout ends it."""
        if fs.cancelled():
            self.nr_conns -= 1
            fs.conn.close()
            return
        try:
            (keepalive, conn) = fs.result()
            if keepalive and not self._torn_down:
                conn.sock.setblocking(False)
                conn.set_timeout()
                with self._lock:
                    self._keep.append(conn)
                    self.poller.register(conn.sock, selectors.EVENT_READ,
                                         partial(self.on_client_socket_readable, conn))
            else:
                self.nr_conns -= 1
                conn.close()
        except Exception:
            self.nr_conns -= 1
            fs.conn.close()

    # -- leaving -------------------------------------------------------------

    def stop_accepting(self):
        for sock in self.sockets:
            try:
                self.poller.unregister(sock)
            except (KeyError, ValueError, OSError):
                pass
            sock.close()

    def drain(self, deadline):
        # Idle keep-alive sockets are NOT closed early: the proxy may already
        # have written the next request on one, and closing it then is exactly
        # the reset this class exists to prevent. They are served if they turn
        # readable and closed by the keep-alive timeout otherwise, as always.
        self.stop_accepting()
        quiet_for = self.cfg.keepalive or 1
        last_activity = time.monotonic()
        while (self.nr_conns > 0 or self.futures) and time.monotonic() < deadline:
            self.notify()
            events = self.poller.select(0.05)
            for key, _ in events:
                key.data(key.fileobj)
            result = futures.wait(self.futures, timeout=0, return_when=futures.FIRST_COMPLETED)
            for fut in result.done:
                self.futures.remove(fut)
            if events or result.done:
                last_activity = time.monotonic()
            elif not self.futures and time.monotonic() - last_activity > quiet_for:
                # Only accepted sockets that never sent a byte are left: a
                # proxy writes right after connecting, so these carry nothing.
                break
            self.murder_keepalived()

    def _exit(self):
        """Leave without the interpreter shutdown: that is where a pool thread
        blocked in socket I/O held the whole process on 2026-09-18. Abandoned
        threads die with the process; their peers see the reset they would
        have seen from the arbiter's SIGKILL 60 s later, with the service up
        in the meantime."""
        abandoned = sum(1 for fs in self.futures if not fs.done())
        try:
            from django.db import connections
            connections.close_all()
        except Exception:  # noqa: BLE001 — leaving anyway
            pass
        self.log.info("Worker exiting (pid: %s), %d request threads abandoned", os.getpid(), abandoned)
        if abandoned:
            faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
