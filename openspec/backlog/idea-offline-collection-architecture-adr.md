# Decide the offline architecture before building any of it

**Type**: idea
**Priority**: high
**Area**: infra
**Created**: 2026-08-23

## Description

Offline collection is the single largest engineering commitment on the roadmap and the
unanimous #1 requirement of the field market ([[features-from-field-gis-feedback]]) — and
our current architecture is hostile to it: sections are server-rendered per request via
Django + HTMX, so there is no client-side form model to run without a network.

Write an ADR choosing between (a) a PWA layer over the existing app — service worker,
IndexedDB queue, cached tiles, replayed POSTs; and (b) a schema-driven field client that
consumes the survey.json we already produce for export/import and posts answers in batches.
Include sync-conflict rules, tile storage limits, and what "data loss" means when the
competitor everyone complains about (Field Maps) loses weeks of it.

## Notes

- Do not start FD-8 without this. A half-built offline mode that loses one crew's day
  costs more trust than not having offline at all.
- Decide explicitly whether offline is Pro-only. It is the clearest paid-tier line we have.
- Epic: field-data-collection (FD-7)
