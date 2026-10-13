## 1. Implementation

- [x] 1.1 `base_landing.html`: wrap navbar in `{% block nav %}`, footer in `{% block footer %}`
- [x] 1.2 `survey/demo_request.py`: `DEMO_TESTIMONIAL`, `customer_logos()`; views pass `testimonial`, `testimonial_story_live`, `logos`
- [x] 1.3 `demo.html`: focused split layout for all three states; overrides `nav` and `footer`
- [x] 1.4 `landing.css`: replace `demo-*` rules; ≥900px split, <900px stacked

## 2. Verification

- [x] 2.1 Tests: no navbar/footer on all states, wordmark link, new headings and "Next", quote + story link (published / unpublished), logo strip (published-with-logo only; omitted when none)
- [x] 2.2 `DemoRequestTest` and landing tests green; full suite once
- [x] 2.3 Screenshots at 1280 and 360 for step one, step two, done
