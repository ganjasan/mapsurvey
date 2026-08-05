# Data Management

**Slug**: data-management
**Created**: 2026-04-05
**Tier (2026-07-29)**: **Free** — the whole suite stays free. Cleaning and validating your
own data is table stakes; gating it would break the "your data is yours" promise that is
our wedge against Maptionnaire / Citizen Space / Open Point. The single exception is
[Audit Trail](../feature-audit-trail.md) (#59), which is **Pro** because it exists to prove
integrity to a third party rather than to help you fix your own dataset. See
[pro-tier.md](pro-tier.md).

## Description

IDE-style Data workspace внутри Analytics: четыре dock-able resizable панели (Map, Table, Charts, Anomalies) связанные через FilterManager. Валидация/модерация сессий (4 статуса), inline editing ответов (включая geo), answer-level linting (errors/warnings), auto-validation rules, настраиваемые thresholds, clean export. Корзина с soft delete/restore.

## Vision & Scope

`docs/plans/epic-data-management-vision-and-scope.md`

## Scope

- FE-1: Attribute Table (Table tab in Analytics)
- FE-2: IDE-style Panel Layout (Map, Table, Charts, Anomalies)
- FE-3: Session Validation & Moderation (4 statuses, trash/restore)
- FE-4: Inline Editing (text, choice, number, geo)
- FE-5: Tags & Notes
- FE-6: Clean Export (excludes rejected/deleted)
- FE-7: Audit Trail
- FE-8: Bulk Operations
- FE-9: Auto-Validation Rules (7 rules)
- FE-10: Anomalies Panel
- FE-11: Answer-level Linting (errors/warnings)
- FE-12: Validation Settings (configurable thresholds)
