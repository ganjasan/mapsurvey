# Group the question type list — display blocks are not input types

**Type**: improvement
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-09

## Description

`INPUT_TYPE_CHOICES` is a flat list of thirteen entries offered in one undifferentiated dropdown,
and it mixes three genuinely different things:

- **Display blocks** that collect nothing: `image`, `html`. These are not input types at all — a
  respondent cannot answer them — yet they sit in the middle of the list between `polygon` and
  `text_line` as though they were.
- **Ordinary questions**: `text`, `text_line`, `number`, `choice`, `multichoice`, `range`, `rating`,
  `datetime`.
- **Geo questions**: `point`, `line`, `polygon` — the ones that put something on the map, and the
  only ones for which colour and icon mean anything.

The ordering has also drifted: `text_line` ("Single Line Text") sits after `image`, far from `text`,
which it belongs beside.

Grouping them — `<optgroup>` in the dropdown, or a sectioned picker — makes the distinction the
model already relies on visible to the author.

## Notes

- Reported 2026-08-09 alongside
  [Color/Icon/Image shown on every type](bug-question-fields-shown-for-every-type.md): "в списке
  вопросов нет разделения на блоки… на вопросы, которые не вопросы, а просто тексты, картинки,
  видео, звуковые дорожки… на простые вопросы, на гео вопросы."
- Small on its own, but it props up
  [Media upload question type](feature-audio-upload.md) (#41): once video and audio arrive the flat
  list becomes unreadable, and the display-block group is exactly where they belong — as does the
  naming collision noted there, where the existing `image` type *shows* an image rather than
  accepting one.
- The grouping is the natural place to state which types support which settings, which is the same
  information the field-hiding fix carries. Doing them together would be coherent; doing this one
  first would make that fix easier to explain.
- Purely presentational: `INPUT_TYPE_CHOICES` values stay as they are, so no migration and no
  stored data changes.
