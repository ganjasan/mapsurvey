## Context

`demo.html` extends `base_landing.html`, whose navbar and footer are hard-coded. The only attributed customer testimonial we have is in the published Pszów story; stories carry `credit`, `credit_logo` and `slug`, and `Story.in_showcase_order()` gives the order used on the landing carousel.

## Decisions

- **Opt-out blocks, not a second base template.** Wrap the navbar in `{% block nav %}` and the footer in `{% block footer %}` in `base_landing.html`. `demo.html` overrides both. Head, fonts, analytics and structured data stay shared, so `/demo/` cannot drift from the rest of the site.
- **Layout.** Full-height page, a white background, a 1.1fr / 1fr grid at ≥ 900px with the content vertically centred. The left column holds a 2.75rem question, the label, the field and a full-width primary button (Notion's "Next"). The right column holds the quote in the serif body font with attribution and "Read the Pszów story →". The logo strip sits on `--color-bg-warm` at the bottom, as Notion's does. Under 900px everything is one column: form, quote, logos.
- **Copy.**
  - Step 1: H1 "What's your work email?", button "Next", one line under it: "We'll reply within one working day with a walkthrough built around what you want to map. No calendar, no mailing list."
  - Step 2: H1 "Tell us a bit more", plus "Everything here is optional."
  - Done: "Thanks — we'll be in touch".
- **Quotes as a constant, shown as a carousel.** `DEMO_TESTIMONIALS` in `survey/demo_request.py` lists text, name, role, organisation, story slug, link label and an optional `photo`. Every text is verbatim from a published, author-approved story: Anna M. Pyziak (TUP, Pszów), plus Julian Thomas and Cliff Schraibman (Whitehouse Community Council). Julian's "completely free … €4,500" line is left out on purpose, because on the page where people ask for a demo of the paid service it argues the wrong way. A quote whose story is unpublished is dropped.
  - **Avatars.** Initials until the person approves a photo. Photos found on the council site were published for the council's page, not for our marketing, so we ask first.
  - **Mechanics.** All cards sit in one grid cell, so the column keeps the height of the longest quote and the form does not jump. Without JavaScript cards 2+ keep `hidden` and the dots stay hidden. The script rotates every 8 s, pauses on hover and focus, never autoplays under `prefers-reduced-motion`, and the dots act as a tablist with arrow-key support.
- **Logo strip.** `customer_logos()` returns published stories with a non-empty `credit_logo`, in `in_showcase_order`, at most 8. Each renders as `<a href="/stories/<slug>/"><img alt="<credit>"></a>` in greyscale at 60% opacity, full colour on hover. The strip is omitted when the list is empty.
- **Nothing else changes.** Fields, flow, honeypot, limits, mail and events are untouched.

## Risks / Trade-offs

- Without a navbar, a visitor who wants to leave uses the wordmark or Back. That is the point of a focused page, and Notion does the same.
- A hard-coded quote can go stale. It is tied to a story slug, so the link disappears if the story does.
