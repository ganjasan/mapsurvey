## Why

On a phone the What's new hero (change `changelog-hero`, #423) stacks into one column: plate,
eyebrow, title, body, chips, call to action, "How it works", note and "Don't show these". It
fills the whole first screen of the dashboard and pushes the survey list below the fold, so a
creator who opened the dashboard to reach a survey has to scroll past an advert first (#514).

## What Changes

- Below 768 px the hero renders **collapsed**: one row with the "New" badge, the title and a
  chevron, above the survey list. Tapping the row expands the full card (plate, body, chips,
  call to action, "How it works", note, "Don't show these"); tapping again collapses it.
- The × stays visible on the collapsed row, so the banner can be dismissed without expanding.
- The desktop banner is unchanged. The collapsed state is presentation only: the watermark,
  the closed-id memory and the events behave exactly as before; `changelog_card_shown` still
  fires once per render, and expanding fires `changelog_card_expanded` so we can see whether
  phone creators open it at all.
- Rejected: moving the banner below the survey list on phones. With one card per row, a
  creator with five surveys would never scroll to it.

## Capabilities

### New Capabilities

### Modified Capabilities
- `changelog-hero-banner`: the dashboard requirement gains a phone layout — the hero is
  collapsed to one row until tapped.

## Impact

- `survey/templates/editor/partials/_whats_new_hero.html` (a toggle row and a few lines of JS).
- `survey/assets/css/whats-new.css` (the `max-width: 767.98px` rules).
- `survey/tests/test_changelog_hero_banner.py` (markup of the collapsed row).
- No model, migration, view or setting.
