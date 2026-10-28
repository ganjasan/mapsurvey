## Why

Stories are built before the customer's written OK (three on 2026-10-01).
Until now publishing on production meant running `seed_story` there at the moment of the OK, and
every run of the command published the story. We want to install prepared stories on
production as drafts, check them there, and publish each one with a click when its customer
says yes.

## What Changes

- `seed_story` no longer decides publication by default: a NEW story is installed unpublished,
  a re-run keeps the current state. `--publish` publishes, `--draft` unpublishes (both explicit).
- `seed_story --from DIR` reads the story from a directory outside the repo. The repo is
  public: a story whose customer has not approved it is copied to the server and seeded from
  there, never pushed.
- Admin: `is_published` is editable in the Story list, plus "Publish" / "Unpublish" actions.
  Publishing sets `published_date` when it is empty.
- Staff can open an unpublished story at its normal URL to check it on production: the page
  carries a "Draft — not public" banner and `noindex`. Everyone else still gets 404; drafts stay
  out of the landing, `/stories/` and the sitemap.

## Impact

- `survey/management/commands/seed_story.py`, `survey/admin.py`, `survey/views.py::story_detail`,
  `story_detail.html`, tests, `CLAUDE.md`, the `customer-story` skill.
- BREAKING for the Olney habit "seed = publish": publishing is now `--publish` or the admin.
