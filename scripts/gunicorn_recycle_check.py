#!/usr/bin/env python
"""Does a gunicorn worker drop requests when it recycles or shuts down?

Starts gunicorn on a free port with a tiny request budget so workers recycle
every few requests, hammers it with three clients and counts the requests
that got a connection error instead of a response:

- keepalive: one persistent connection, the way a reverse proxy talks to us;
- fresh:     a new connection per request;
- parallel:  four clients at once, two persistent and two fresh — the
             case that exposed the keep-alive response built while `alive`
             was still True and then closed under the proxy's feet;
- sigterm:   fresh connections while the master gets SIGTERM mid-run (a
             deploy's graceful stop); only requests sent BEFORE the signal
             count — later ones may legitimately find nobody listening.

`--poison N` adds N silent peers to every scenario: connections that send half
a request header and then nothing. gthread reads client sockets with no
timeout, so each parks a pool thread in recv() for the life of the worker, and
a worker that recycles with such a thread cannot exit — the drain runs to
--graceful-timeout, then the interpreter joins the pool at shutdown, and the
arbiter kills it at --timeout. On 2026-09-18 both production workers recycled
in that state and nothing accepted for 90 s. A run fails on a failed request,
on a request slower than SLOW_SECONDS, and on any `WORKER TIMEOUT` in
gunicorn's output.

Run it from a checkout with the database env of `run_tests.sh`
(SQL_HOST/SQL_PORT/...), for example:

    scripts/gunicorn_recycle_check.py --worker-class gthread
    scripts/gunicorn_recycle_check.py --worker-class gthread --poison 2 --timeout 20
    scripts/gunicorn_recycle_check.py --worker-class mapsurvey.gunicorn_workers.DrainingThreadWorker --poison 8

Measured 2026-09-18 (2 workers × 4 threads, --max-requests 4, 80 requests per client):

    gthread   --poison 2 --timeout 20: keepalive fail=15, fresh fail=16,
              parallel ok=244 fail=76 slow=1 worst=5.0s WORKER TIMEOUT ×1, sigterm fail=1
    draining  --poison 2: every scenario fail=0 slow=0, worst 0.8 s
    draining  --poison 3: every scenario fail=0 slow=0, worst 1.2 s
    draining  --poison 0: every scenario fail=0 slow=0, worst 1.2 s (40 recycles in parallel)

Keep N below the threads per worker: N silent peers hold N threads for --timeout
seconds, so N ≥ 4 here is pool saturation, which no worker class can serve
through — that is a different finding from a recycle that cannot end.

Exit code 1 when any check failed. This is the reproduction behind
mapsurvey/gunicorn_workers.py; keep it green when touching the gunicorn
command line.
"""
import argparse
import http.client
import os
import signal
import socket
import subprocess
import sys
import time

SLOW_SECONDS = 5.0


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def start(port, worker_class, max_requests, keepalive, timeout):
    cmd = [sys.executable, '-m', 'gunicorn', '--bind', f'127.0.0.1:{port}', '--workers', '2', '--threads', '4',
           '--worker-class', worker_class, '--timeout', str(timeout), '--graceful-timeout', '10',
           '--max-requests', str(max_requests), '--max-requests-jitter', '0',
           '--keep-alive', str(keepalive), 'mapsurvey.wsgi:application']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return proc
        except OSError:
            if proc.poll() is not None:
                print(proc.stdout.read())
                raise SystemExit('gunicorn did not start')
            time.sleep(0.2)
    raise SystemExit('gunicorn did not start in 30 s')


def poison(port, n):
    """N peers that send half a request and go silent. Returned so the caller
    keeps them open for the run; whichever worker accepted one has a thread
    blocked in recv() until the socket timeout the worker class sets (or
    forever, in stock gthread)."""
    socks = []
    for _ in range(n):
        s = socket.create_connection(('127.0.0.1', port))
        s.sendall(b'GET /robots.txt HTTP/1.1\r\nHost: x\r\n')
        socks.append(s)
    time.sleep(0.5)     # let the workers pick them up before the real traffic
    return socks


def request(conn, url):
    conn.request('GET', url)
    r = conn.getresponse()
    r.read()
    return r.status


def run_client(port, url, n, mode, pause):
    ok = fail = slow = 0
    worst = 0.0
    errors = set()
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    for _ in range(n):
        if mode == 'fresh':
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        started = time.monotonic()
        try:
            request(conn, url)
            ok += 1
        except Exception as exc:  # noqa: BLE001 — every failure is the finding
            fail += 1
            errors.add(type(exc).__name__)
            conn.close()
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        took = time.monotonic() - started
        worst = max(worst, took)
        if took > SLOW_SECONDS:
            slow += 1
        if mode == 'fresh':
            conn.close()
        time.sleep(pause)
    return ok, fail, slow, worst, sorted(errors)


def report(label, ok, fail, slow, worst, errors, out):
    timeouts = out.count('WORKER TIMEOUT')
    print(f'{label}: ok={ok} fail={fail} slow={slow} worst={worst:.1f}s '
          f'recycles={out.count("Autorestarting worker")} worker_timeouts={timeouts} errors={errors}')
    return fail + slow + timeouts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--worker-class', default='gthread')
    ap.add_argument('--max-requests', type=int, default=4)
    ap.add_argument('--keep-alive', type=int, default=2)
    ap.add_argument('--timeout', type=int, default=60, help='gunicorn --timeout (also the socket timeout)')
    ap.add_argument('--requests', type=int, default=80)
    ap.add_argument('--url', default='/robots.txt')
    ap.add_argument('--pause', type=float, default=0.03)
    ap.add_argument('--poison', type=int, default=0, help='silent half-request peers held open during every scenario')
    args = ap.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mapsurvey.settings')

    failed = 0
    for mode in ('keepalive', 'fresh', 'parallel'):
        port = free_port()
        proc = start(port, args.worker_class, args.max_requests, args.keep_alive, args.timeout)
        poisoned = []
        try:
            poisoned = poison(port, args.poison)
            if mode == 'parallel':
                import threading
                results = []
                def worker(client_mode):
                    results.append(run_client(port, args.url, args.requests, client_mode, args.pause))
                threads = [threading.Thread(target=worker, args=(m,))
                           for m in ('keepalive', 'keepalive', 'fresh', 'fresh')]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                ok = sum(r[0] for r in results)
                fail = sum(r[1] for r in results)
                slow = sum(r[2] for r in results)
                worst = max(r[3] for r in results)
                errors = sorted({e for r in results for e in r[4]})
            else:
                ok, fail, slow, worst, errors = run_client(port, args.url, args.requests, mode, args.pause)
        finally:
            for s in poisoned:
                s.close()
            proc.send_signal(signal.SIGTERM)
            out = proc.communicate(timeout=120)[0]
        failed += report(f'{mode:<9} worker={args.worker_class} max_requests={args.max_requests} poison={args.poison}',
                         ok, fail, slow, worst, errors, out)

    # A deploy: SIGTERM to the master while requests are in flight.
    port = free_port()
    proc = start(port, args.worker_class, 10_000, args.keep_alive, args.timeout)
    ok = fail = slow = 0
    worst = 0.0
    errors = set()
    poisoned = []
    sent_before_signal = 0
    try:
        poisoned = poison(port, args.poison)
        for i in range(args.requests):
            if i == args.requests // 2:
                proc.send_signal(signal.SIGTERM)
                sent_before_signal = ok + fail
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            started = time.monotonic()
            try:
                request(conn, args.url)
                ok += 1
            except ConnectionRefusedError:
                break   # the server is gone: every request from here on is moot
            except Exception as exc:  # noqa: BLE001
                fail += 1
                errors.add(type(exc).__name__)
            finally:
                conn.close()
            took = time.monotonic() - started
            worst = max(worst, took)
            if took > SLOW_SECONDS:
                slow += 1
            time.sleep(args.pause)
    finally:
        for s in poisoned:
            s.close()
        out = proc.communicate(timeout=120)[0]
    failed += report(f'sigterm   worker={args.worker_class} poison={args.poison} '
                     f'(requests sent before the signal: {sent_before_signal})',
                     ok, fail, slow, worst, sorted(errors), out)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
