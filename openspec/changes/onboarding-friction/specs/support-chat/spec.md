## MODIFIED Requirements

### Requirement: Bubble placement follows the editor navigation flag
`base.html` and `editor/editor_base.html` SHALL include the widget in editor-bubble mode
(change `onboarding-friction`): the floating chat bubble SHALL be shown on viewports wider than
767.98 px and SHALL NOT be shown on narrower ones, where it covers the panel's controls; on a
desktop the bubble SHALL carry a small "×" ("Hide the chat button") that hides it and remembers
the choice in the browser (`localStorage['msSupportBubble'] = 'hidden'`), and while it is hidden
the "?" help menu SHALL list "Show chat button", which brings it back and forgets the choice.
The chat SHALL keep opening through `openSupportChat` from the "?" / "Help & support" entry
points in every case. `base_landing.html` SHALL always show the bubble, with no "×".

#### Scenario: Editor page on a desktop
- **WHEN** a signed-in creator opens an editor page on a desktop and has not hidden the bubble
- **THEN** the widget is configured with the message bubble shown, the "×" is drawn beside it, and "Help & support" opens the chat

#### Scenario: Editor page on a phone
- **WHEN** a signed-in creator opens an editor page on a viewport narrower than 768 px
- **THEN** the widget is configured with the message bubble hidden and no "×" is drawn

#### Scenario: The creator hides the bubble
- **WHEN** the creator presses the "×"
- **THEN** the bubble disappears, the next editor page in that browser opens without it, and the "?" menu shows "Show chat button"

#### Scenario: The creator brings it back
- **WHEN** the creator picks "Show chat button" in the "?" menu
- **THEN** the bubble and its "×" reappear and the menu item is hidden again

#### Scenario: Landing page
- **WHEN** the landing page is rendered
- **THEN** the widget is configured with the message bubble shown

### Requirement: The hidden widget never speaks first
On editor pages the widget SHALL NOT show its unread-messages pop-up or pop-out button, whether
the bubble is shown or hidden. A reply received while the chat is closed SHALL be signalled by an
unread dot on the help entry points (and, when the bubble is shown, by the widget's own dot on
it), cleared when the chat opens.

#### Scenario: Agent reply while the chat is closed
- **WHEN** the widget reports an unread count above zero on an editor page
- **THEN** every `.support-unread` marker is shown, no unread pop-up opens, and the markers are hidden again once the chat is opened
