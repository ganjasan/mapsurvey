# Tasks — expert help service page

- [x] Add `services` view in `survey/views.py` (calls `capture_signup_source`,
      renders `services.html`), mirroring `for_government`.
- [x] Add URL `path('services/', views.services, name='services')` in `survey/urls.py`.
- [x] Create `survey/templates/services.html` extending `base_landing.html`:
      hero (optional-help framing), two tiers (launch / done-with-you), how it
      works, reassurance that the platform stays free, mailto CTA.
- [x] Add `Allow: /services/` to the `robots_txt` view.
- [x] Test: `/services/` returns 200 with key copy; `/robots.txt` lists it.
- [x] `openspec validate expert-help-service-page`; run the new tests.
