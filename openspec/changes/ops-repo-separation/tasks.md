# Tasks: ops-repo-separation

## 1. Private ops repository
- [x] 1.1 Create `ganjasan/mapsurvey-ops` (private) and move docs, raw, requirements,
      backlog, designs, user_surveys, legal, ops scripts and the ai-visibility skill into it
- [x] 1.2 Keep respondent data (exports, ZIPs, story datasets) out of git there too
- [x] 1.3 Gitignored symlinks from the main checkout into the ops repo

## 2. Public repository
- [x] 2.1 Remove plans, competitor notes, resources, survey drafts, DPA draft, UX audit
- [x] 2.2 Pseudonymise people in `openspec/` (`lead-NNN`), key kept in the ops repo
- [x] 2.3 `settings.OPS_DIR`; cohort-file test and comments read it
- [x] 2.4 `RepoHygieneTest` guard against real email addresses
- [x] 2.5 `.gitignore` patterns that match the symlinks; `CLAUDE.md` section; skill paths

## 3. History (separate run, after open PRs are merged or closed)
- [ ] 3.1 `git filter-repo`: drop removed paths and the leaked config files from history,
      apply the ops repo's replacement list to `openspec/`, `docs/`, `.claude/` only
- [ ] 3.2 Force-push, re-create remaining branches and worktrees, ask GitHub support to
      purge cached views of the old commits
