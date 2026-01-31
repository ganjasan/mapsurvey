# TODO / Feature Requests

## Bugs
- [x] Option group показывается как обязательное поле в админке (должно быть optional, нужно только для choice/multichoice)
- [x] Required geo-поля вызывают ошибку "An invalid form control is not focusable" (заменили required на data-required + JS валидация)
- [ ] Иконки не отображаются на карте
- [ ] Не загружаются картинки

## Survey Editor
- [ ] Add a web-based survey editor interface for creating and editing surveys
  - Currently surveys are created via Django Admin, which is not user-friendly
  - Need a drag-and-drop interface for sections and questions
  - Support for all question types including GIS (point, line, polygon)
  - Preview functionality
  - Option group management

## Multilingual Surveys
- [ ] Support for multiple languages in surveys
  - Translations for question text, subtext, option choices
  - Language selector for respondents
  - Admin interface for managing translations

## Map UX
- [ ] Центрирование карты на локацию пользователя
  - Использовать Geolocation API браузера
  - Кнопка "Locate me" или автоматическое определение при загрузке
  - Кейс: пользователь открывает Demo опрос и заполняет его на своём городе
  - Fallback на дефолтную позицию из SurveySection если геолокация недоступна

## Import/Export
- [ ] Survey structure import/export (JSON/YAML)
  - Export survey with all sections, questions, option groups
  - Import to recreate survey on another instance
  - Useful for backup and sharing survey templates
- [ ] Survey responses export improvements
  - Currently exports GeoJSON + CSV
  - Add more formats (Excel, Shapefile)
