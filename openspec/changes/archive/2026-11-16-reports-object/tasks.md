## 1. Model and migration
- [x] 1.1 `reports` app, `Report`, `ReportBlock`, `0001_initial`
- [x] 1.2 `0002` copies pages and blocks with ids, resolves datasets, resets sequences
- [x] 1.3 `survey/0131`: `CommentThread.block` → `reports.ReportBlock`; delete the old models
- [x] 1.4 Migration test: a page with chart, map, text and orphan blocks before → the same report after

## 2. Rendering and writes
- [x] 2.1 `reports/render.py` (from `survey/public_results.py`), `reports/sources.py`
- [x] 2.2 `reports/services.py` with `Actor`; editor views call it
- [x] 2.3 `/r/<slug>/` with workspace-only visibility; sitemap and listing skip it
- [x] 2.4 Every other reader moved: sites, share, comments, basemaps, admin, commands, templates

## 3. Reports in the workspace
- [x] 3.1 Reports list page and navigation item
- [x] 3.2 Used by: dataset page, delete page, catalogue counts; a view in a block cannot be deleted
- [x] 3.3 A report with blocks over two surveys renders both

## 4. Close
- [x] 4.1 Tests green (`survey billing api mcp newsletter`); new strings go into the catalogs once, with the epic's last UI change (#704 rewrites these screens)
- [x] 4.2 CLAUDE.md
