# Default map in survey settings cannot be None

**Type**: bug
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-25

## Description

В настройках опроса всегда должен быть выбран Default map (базовая карта по умолчанию) — это значение не может быть None / пустым. Сейчас, по-видимому, возможно сохранить настройки без установленного default, что приводит к некорректному состоянию.

## Notes

— Связано с feature/satellite-basemap-options (поля basemaps на SurveyHeader, миграции 0027–0029).
— Нужно: на уровне формы/валидации в `editor_forms.py` и/или модели гарантировать, что один из basemap всегда отмечен как default; при удалении/смене активного default — автоматически назначать другой.
