# Proposal: ops-repo-separation

## Why

This repository is public, and it had become the place where the business is run as well as
where the code lives. An audit on 2026-10-02 found, in tracked files on `master`:

- email addresses of about a dozen real people (creators, leads, students) in
  `openspec/backlog/` and `openspec/changes/`, next to their full names, platform usernames
  and what they told us in private correspondence (~95 files);
- GTM strategy, the 90-day plan, launch-channel research, a competitor analysis and an
  unpublished DPA draft, force-added under the otherwise gitignored `docs/` and `legal/`.

Untracked, the checkout also held ~300 MB of outreach dossiers, stories, cohorts and raw
notes with no version control and no backup, plus two outreach scripts and a skill that no
ignore rule covered — one `git add .` away from being published.

## What Changes

- A private repository `ganjasan/mapsurvey-ops` (checkout `../Mapsurvey-ops`, same layout as
  the old in-repo paths) now holds all operational material. Respondent data (exports, ZIPs,
  story datasets) stays out of git entirely, ops repo included.
- Removed from this repo: `docs/plans/`, `docs/concurents/`, `docs/resources/`,
  `docs/surveys/`, `legal/`, `scripts/build_dpa.sh`, `mobile-ux-audit-2026-08-23.md`.
  Kept: `docs/images/` (README) and `docs/research/survey-design-rules.md` (the AI prompt
  and the `newsurvey` skill cite it).
- People in `openspec/` are referred to by pseudonym `lead-NNN`. The key lives only in the
  ops repo (`redaction/redaction-map.json`), together with the replacement list that will
  also drive the history rewrite.
- `settings.OPS_DIR` (env `MAPSURVEY_OPS_DIR`, default `../Mapsurvey-ops`) is the one way
  code finds operational files; the cohort-file test reads it and skips when absent.
- `RepoHygieneTest` fails the suite when a real email address appears in tracked docs,
  specs or agent instructions.
- `.gitignore` patterns lose their trailing slash so they also match the convenience
  symlinks the main checkout keeps into the ops repo.
- `CLAUDE.md` gains a "Public repo vs. private ops repo" section; the `new-resource` and
  `newsurvey` skills write into the ops repo.

## Out of scope

Rewriting history. The removed files and addresses are still reachable in past commits.
That is a separate, one-off `git filter-repo` run (path-restricted replacements from the
ops repo, plus path removals) followed by a force-push, scheduled once the open PRs are
merged or closed so that branches only need rebasing once.

## Impact

No runtime behaviour changes. Tooling that read `docs/marketing/...` keeps working in the
main checkout through gitignored symlinks; other worktrees read the ops repo by path.
