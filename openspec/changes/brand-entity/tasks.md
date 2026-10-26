## 1. Registry and builders

- [x] 1.1 `survey/brand.py`: `PROFILES` registry (Participedia today), `same_as()` adding `settings.GITHUB_REPO_URL`, and builders for the Organization, SoftwareApplication and WebSite nodes with the `@id`s from the design
- [x] 1.2 `survey/templatetags/brand_tags.py`: `{% brand_jsonld %}` and `{% website_jsonld %}` that serialise the nodes into `<script type="application/ld+json">` with `<`, `>`, `&` escaped

## 2. Templates

- [x] 2.1 Replace the two hand-written JSON-LD blocks in `base_landing.html` with `{% brand_jsonld %}`
- [x] 2.2 Emit `{% website_jsonld %}` from `landing.html` (serves `/` and `/ru/`) only

## 3. Tests

- [x] 3.1 GIVEN/WHEN/THEN tests that parse the rendered JSON-LD on `/`, `/ru/` and `/for-planners/`: linked Organization/SoftwareApplication, WebSite only on the homepage pair, BusinessApplication category
- [x] 3.2 Registry test: every profile is absolute `https://`, not on mapsurvey.org, no duplicates; a registry entry reaches `sameAs`
- [ ] 3.3 Run the landing/SEO test classes, then the full `survey` suite once

## 4. Off-repo kit (ops repo, owner submits)

- [x] 4.1 Wikidata item draft (labels, description, statements with property ids, references) in `../Mapsurvey-ops/docs/marketing/brand-entity.md`
- [x] 4.2 Profile checklist in the same file: G2 claim, AlternativeTo, Product Hunt, LinkedIn, SaaSHub, OpenAlternative — each with "add the URL to `survey/brand.py` once live"
- [x] 4.3 Fix `directory-listings.md`: drop the "hosted (EU, Frankfurt)" claims (hosting is the United States)
