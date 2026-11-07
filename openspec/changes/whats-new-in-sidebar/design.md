## Decisions

### D1. One block, the same choice of entry
`{% with entry=whats_new.hero|default:whats_new.card %}` — the `whats_new` context processor already decides which single entry a creator should see (pending hero, else newest unseen card, nothing when cards are off or all seen). The block renders that entry; no new logic, no new query.

### D2. Placement
Between `</nav>` and `.app-side-foot` in `_app_sidebar.html`: `.app-nav` is `flex: 1`, so the block sits just above the footer, in the space the owner pointed at. `body.app-rail .app-wn { display: none }` — the rail has no room; the footer's What's new dot remains. On screens shorter than 640 px the picture is dropped.

### D3. Same actions, same endpoints
× → `how=close`; the hero's call to action → `how=cta` (navigates, POST with `keepalive`); *Don't show these* → cards off; *Read more* → the What's new page, which marks everything seen itself. The closed id is remembered in `localStorage['msWhatsNewClosed']` as before.

### D4. What hero entries lose
Chips, the note line, the art plate and the phone disclosure existed to sell inside a banner; a sidebar block carries a title and a link. The keys stay valid in entry files (the loader keeps parsing them) so old entries need no edit.
