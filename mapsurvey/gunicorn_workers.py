"""A gthread worker that drains before it exits (change layer-memory-diet).

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
happened to land on it, and every deploy's switch did the same.

This worker changes only the exit. It stops accepting first — its listener
copies leave the poller and close, so the kernel hands new connections to the
other worker and, once the arbiter spawns it, the replacement — then keeps
serving what it already accepted: readable sockets are enqueued and answered
with `Connection: close` (gthread does that itself once `alive` is False),
idle keep-alive sockets are left to the keep-alive timeout, never closed early
(the proxy may already have written the next request on one). A response that
was built while `alive` was still True went out without `Connection: close`,
so its connection stays registered too instead of being closed under the
proxy's feet (`finish_request`). It leaves when nothing is left, when
accepted-but-silent sockets have been silent for the keep-alive timeout, or
when `--graceful-timeout` runs out.
"""
import selectors
import time
from concurrent import futures
from functools import partial

from gunicorn.workers.gthread import ThreadWorker


class DrainingThreadWorker(ThreadWorker):

    def run(self):
        for sock in self.sockets:
            sock.setblocking(False)
            server = sock.getsockname()
            self.poller.register(sock, selectors.EVENT_READ, partial(self.accept, server))

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

        self.drain()

        self._torn_down = True
        self.tpool.shutdown(False)
        self.poller.close()
        futures.wait(self.futures, timeout=self.cfg.graceful_timeout)

    _torn_down = False

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

    def stop_accepting(self):
        for sock in self.sockets:
            try:
                self.poller.unregister(sock)
            except (KeyError, ValueError, OSError):
                pass
            sock.close()

    def drain(self):
        # Idle keep-alive sockets are NOT closed early: the proxy may already
        # have written the next request on one, and closing it then is exactly
        # the reset this class exists to prevent. They are served if they turn
        # readable and closed by the keep-alive timeout otherwise, as always.
        self.stop_accepting()
        quiet_for = self.cfg.keepalive or 1
        deadline = time.monotonic() + self.cfg.graceful_timeout
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
