---
name: verify
description: Run this repo's app locally to observe a change at its surface (marketing landings, editor pages, respondent survey) — the bootstrap a fresh worktree needs, how to start the dev server on this worktree's ports, and the HTTP/browser checks that work. Use for /verify, "подними dev и проверь страницу", "покажи, что изменение работает в приложении".
---

# Verify a change by running the app

## Fresh worktree bootstrap (all four, or the run hangs silently)

```bash
ln -s /home/artem/Documents/Projects/Mapsurvey/env env    # venv is gitignored; Python 3.9 / Django 4.2
cp ../Mapsurvey/.env .env                                   # docker-compose needs it; without it pg_isready loops forever with NO output
cp .env.ports.example .env.ports                            # then set a PORT_OFFSET nobody has bound:
used=$(docker ps --format "{{.Ports}}" | grep -oE "0.0.0.0:5[0-9]{3}" | grep -oE "[0-9]{4}$" | sort -u)
for off in $(seq 10 10 900); do echo "$used" | grep -q "^$((5434+off))$" || { echo "free: $off"; break; }; done
env/bin/python manage.py collectstatic --noinput            # manifest storage: every {% static %} 500s without it
```

Register the offset in `.env.ports.example` and set `COMPOSE_PROJECT_NAME=mapsurvey-<slug>`.

## Start and reach the app

```bash
nohup ./run_dev.sh > /tmp/dev.log 2>&1 &     # PostGIS + Redis containers, migrate, runserver on 8000+OFFSET, celery worker
sleep 18; curl -s -o /dev/null -w "%{http_code}\n" http://localhost:$((8000+OFFSET))/<path>/
```

Marketing pages need no login. Editor pages: admin/adminadmin (see memory `feedback_dev_admin_credentials`).

## Checks that worked

- Rendered page: `curl` it to a file, then Python over it — `<h1>`, `<title>`, meta description length (≤160), the `application/ld+json` blocks (`json.loads` each), links inside a block (`sed -n '/id="related"/,/<\/section>/p'`).
- Registry-derived surfaces: `/sitemap.xml` (`<loc>…</loc><lastmod>…</lastmod>` on one line) and `/robots.txt` (`Allow:` lines).
- Probes: path without trailing slash (301), capitalised path (404), `?utm_source=` (200), `HEAD` (200), sub-path (404).
- Data-dependent blocks (stories, topics): seed a row in the DEV database with `manage.py shell -c` using the same `SQL_*`/`REDIS_URL` env as `run_tests.sh`, check the page, delete the row afterwards.
- Browser (Claude in Chrome): `find` the heading, `scroll_to` the ref, screenshot at `scale: 0.6`, `read_console_messages` with an error pattern. The window is maximised and `resize_window` is a no-op on this machine, so a 390px check needs DevTools emulation, not resize.

## Stop only this worktree's processes

```bash
kill $(lsof -t -i :$((8000+OFFSET)) -sTCP:LISTEN)                      # runserver, by port
for p in $(pgrep -f "^/home/artem/Documents/Projects/Mapsurvey/env/bin/python.*celery"); do
  [ "$(readlink /proc/$p/cwd)" = "$PWD" ] && kill $p; done           # celery, by cwd — anchored so the shell itself never matches
```

Never `pkill -f <pattern>`: sibling worktrees run the same command lines. Leave the containers up; `docker compose down -v` only after the PR is merged.
