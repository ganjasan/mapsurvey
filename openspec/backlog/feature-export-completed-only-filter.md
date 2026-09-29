# Export filter: completed surveys only

**Type**: feature
**Priority**: high
**Area**: backend
**Created**: 2026-03-30

## Description

Добавить в экспорт данных опроса галочку "Только прошедшие опрос полностью" (completed sessions only). При включении — экспортировать только ответы из сессий, где респондент дошёл до последней секции и отправил её. По умолчанию — выключена (экспортируются все ответы, как сейчас).

## Notes

- Определение "прошёл полностью": `SurveySession` имеет ответы на вопросы из последней секции опроса (по `order`)
- Галочка на странице экспорта (`download_data` view) или как query-параметр `?completed_only=1`
- Важно для качества данных — частичные ответы могут искажать результаты

- **2026-09-29 — BUILT** in change `responses-export-formats` (branch
  `feature/responses-export-formats`, PR pending). `?completed_only=1` and the dialog switch "Completed responses only"; the predicate is `analytics.completed_session_filter`, shared with the Responses overview so the two counts agree.
