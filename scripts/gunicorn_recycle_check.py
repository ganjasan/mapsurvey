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

Run it from a checkout with the database env of `run_tests.sh`
(SQL_HOST/SQL_PORT/...), for example:

    scripts/gunicorn_recycle_check.py --worker-class gthread
    scripts/gunicorn_recycle_check.py --worker-class mapsurvey.gunicorn_workers.DrainingThreadWorker

Exit code 1 when any request failed. This is the reproduction behind
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


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def start(port, worker_class, max_requests, keepalive):
    cmd = [sys.executable, '-m', 'gunicorn', '--bind', f'127.0.0.1:{port}', '--workers', '2', '--threads', '4',
           '--worker-class', worker_class, '--timeout', '60', '--graceful-timeout', '10',
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


def request(conn, url):
    conn.request('GET', url)
    r = conn.getresponse()
    r.read()
    return r.status


def run_client(port, url, n, mode, pause):
    ok = fail = 0
    errors = set()
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    for _ in range(n):
        if mode == 'fresh':
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        try:
            request(conn, url)
            ok += 1
        except Exception as exc:  # noqa: BLE001 — every failure is the finding
            fail += 1
            errors.add(type(exc).__name__)
            conn.close()
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        if mode == 'fresh':
            conn.close()
        time.sleep(pause)
    return ok, fail, sorted(errors)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--worker-class', default='gthread')
    ap.add_argument('--max-requests', type=int, default=4)
    ap.add_argument('--keep-alive', type=int, default=2)
    ap.add_argument('--requests', type=int, default=80)
    ap.add_argument('--url', default='/robots.txt')
    ap.add_argument('--pause', type=float, default=0.03)
    args = ap.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mapsurvey.settings')

    failed = 0
    for mode in ('keepalive', 'fresh', 'parallel'):
        port = free_port()
        proc = start(port, args.worker_class, args.max_requests, args.keep_alive)
        try:
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
                errors = sorted({e for r in results for e in r[2]})
            else:
                ok, fail, errors = run_client(port, args.url, args.requests, mode, args.pause)
        finally:
            proc.send_signal(signal.SIGTERM)
            out = proc.communicate(timeout=30)[0]
        recycles = out.count('Autorestarting worker')
        print(f'{mode:<9} worker={args.worker_class} max_requests={args.max_requests}: '
              f'ok={ok} fail={fail} recycles={recycles} errors={errors}')
        failed += fail

    # A deploy: SIGTERM to the master while requests are in flight.
    port = free_port()
    proc = start(port, args.worker_class, 10_000, args.keep_alive)
    ok = fail = 0
    errors = set()
    try:
        for i in range(args.requests):
            if i == args.requests // 2:
                proc.send_signal(signal.SIGTERM)
                sent_before_signal = ok + fail
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
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
            time.sleep(args.pause)
    finally:
        proc.communicate(timeout=30)
    print(f'sigterm   worker={args.worker_class}: ok={ok} fail={fail} errors={sorted(errors)} '
          f'(requests sent before the signal: {sent_before_signal})')
    failed += fail
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
