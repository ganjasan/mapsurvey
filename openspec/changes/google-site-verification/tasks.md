# Tasks — google-site-verification

## 1. Implementation
- [x] 1.1 `GOOGLE_SITE_VERIFICATION` setting (env, default '') + analytics context processor
- [x] 1.2 Meta tag in `base_landing.html` and `base.html` (guarded, empty ⇒ absent)
- [x] 1.3 Tests: absent by default; rendered when configured

## 2. Owner follow-up (no code)
- [ ] 2.1 Create GSC property for mapsurvey.org and verify (DNS TXT preferred, or set the env var on Render and redeploy)
- [ ] 2.2 Submit https://mapsurvey.org/sitemap.xml; request indexing for /for-educators/
