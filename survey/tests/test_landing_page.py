"""Tests for the `landing-page` capability (openspec/specs/landing-page/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, Client, override_settings
from django.contrib.auth.models import User
from survey.models import SurveyHeader
import os
from django.conf import settings as dj_settings
from survey.tests.helpers import _make_org


class LandingPageViewTest(TestCase):
    """Tests for the landing page index view."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org()

    def test_anonymous_sees_landing_page(self):
        """
        GIVEN an unauthenticated user
        WHEN navigating to /
        THEN the system renders the landing page with sign-up CTA
        """
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing.html')
        self.assertContains(response, 'Sign Up Free')
        self.assertContains(response, 'Sign In')
        self.assertNotContains(response, 'Go to Dashboard')

    def test_authenticated_sees_dashboard_cta(self):
        """
        GIVEN an authenticated user
        WHEN navigating to /
        THEN the system renders the landing page with dashboard CTA
        """
        User.objects.create_user('testuser', password='pass')
        self.client.login(username='testuser', password='pass')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing.html')
        self.assertContains(response, 'Go to Dashboard')
        self.assertNotContains(response, 'Sign Up Free')

    def test_private_surveys_excluded_from_context(self):
        """
        GIVEN private, demo, and public surveys
        WHEN the landing page is rendered
        THEN only demo and public surveys appear in the surveys context
        """
        SurveyHeader.objects.create(name="priv", visibility="private", organization=self.org, status='published')
        SurveyHeader.objects.create(name="demo_s", visibility="demo", organization=self.org, status='published')
        SurveyHeader.objects.create(name="pub_s", visibility="public", organization=self.org, status='published')

        response = self.client.get('/')
        survey_names = [s.name for s in response.context['surveys']]
        self.assertNotIn('priv', survey_names)
        self.assertIn('demo_s', survey_names)
        self.assertIn('pub_s', survey_names)

    def test_seo_meta_tags_present(self):
        """
        GIVEN the landing page
        WHEN rendered
        THEN essential SEO meta tags are present in the HTML
        """
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('<meta name="description"', content)
        self.assertIn('<link rel="canonical"', content)
        self.assertIn('og:title', content)
        self.assertIn('twitter:card', content)
        self.assertIn('application/ld+json', content)

    def test_landing_page_sections_present(self):
        """
        GIVEN the landing page
        WHEN rendered
        THEN all major sections are present
        """
        SurveyHeader.objects.create(name="hidden", visibility="private", organization=self.org, status='published')
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('id="hero"', content)
        self.assertIn('id="use-cases"', content)
        self.assertIn('id="demo"', content)
        self.assertIn('id="features"', content)

    def test_github_link_present(self):
        """
        GIVEN the GITHUB_REPO_URL setting is configured
        WHEN the landing page is rendered
        THEN GitHub links appear in the page
        """
        response = self.client.get('/')
        self.assertContains(response, 'github.com')

    def test_navbar_links(self):
        """
        GIVEN the landing page
        WHEN rendered
        THEN the navbar contains correct anchor links
        """
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('href="/#features"', content)
        self.assertIn('href="/#demo"', content)
        # Pricing section removed — verify it's not in navbar
        self.assertNotIn('href="/#pricing"', content)

    def test_schema_org_structured_data(self):
        """
        GIVEN the landing page
        WHEN rendered
        THEN Schema.org SoftwareApplication structured data is present
        """
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('"@type": "SoftwareApplication"', content)
        self.assertIn('"name": "Mapsurvey"', content)


class LandingPageLifecycleTest(TestCase):
    """Tests for landing page lifecycle filtering."""

    def setUp(self):
        self.org = _make_org('LandingOrg')

    def test_draft_surveys_excluded(self):
        """
        GIVEN a draft survey with public visibility
        WHEN the landing page is rendered
        THEN the draft survey is not in the surveys context
        """
        SurveyHeader.objects.create(
            name='draft_pub', organization=self.org,
            visibility='public', status='draft',
        )
        response = self.client.get('/')
        survey_names = [s.name for s in response.context['surveys']]
        self.assertNotIn('draft_pub', survey_names)

    def test_published_surveys_shown(self):
        """
        GIVEN a published survey with public visibility
        WHEN the landing page is rendered
        THEN the survey is in the surveys context
        """
        SurveyHeader.objects.create(
            name='pub_survey', organization=self.org,
            visibility='public', status='published',
        )
        response = self.client.get('/')
        survey_names = [s.name for s in response.context['surveys']]
        self.assertIn('pub_survey', survey_names)


class LandingTwoPathsTest(TestCase):
    """The landing page ends in "How to start": build it yourself, or with us (landing-two-paths,
    request-demo-form)."""

    def test_hero_offers_get_free_and_request_demo(self):
        """
        GIVEN an anonymous visitor
        WHEN the landing page is rendered
        THEN the hero carries "Get Mapsurvey free" to registration and "Request a demo"
             to /demo/?src=hero in the same tab
        """
        html = Client().get("/").content.decode()
        hero = html[html.index('id="hero"'):html.index("</section>", html.index('id="hero"'))]
        self.assertIn('href="/accounts/register/" class="btn-primary-landing">Get Mapsurvey free', hero)
        self.assertIn('href="/demo/?src=hero" class="btn-secondary-landing">Request a demo', hero)
        self.assertNotIn('target="_blank"', hero.split('hero__demo-link')[0])
        self.assertNotIn("Create your Mapsurvey", hero)

    @override_settings(DEMO_SURVEY_URL="/surveys/demo/")
    def test_demo_is_a_text_link_not_a_hero_button(self):
        """
        GIVEN a configured demo survey
        WHEN the landing page is rendered
        THEN the demo is offered as a text link under the hero buttons
        """
        resp = Client().get("/")
        self.assertContains(resp, 'class="hero__demo-link"')
        self.assertContains(resp, "or try a 2-minute demo survey")
        self.assertNotContains(resp, "Try Demo Survey")

    def test_how_to_start_shows_both_paths(self):
        """
        GIVEN an anonymous visitor
        WHEN the landing page is rendered
        THEN "How to start" shows the free path with "Get Mapsurvey free" and the
             with-us path with "Request a demo" and a link to /services/
        """
        html = Client().get("/").content.decode()
        start = html.index('id="how-to-start"')
        section = html[start:html.index("</section>", start)]
        self.assertIn("Build it yourself", section)
        self.assertIn("Build it with us", section)
        self.assertIn("Get Mapsurvey free", section)
        self.assertIn('href="/demo/?src=how_to_start" class="btn-primary-landing btn-primary-landing--dark">Request a demo', section)
        self.assertIn('href="/services/" class="path-card__link"', section)

    def test_signed_in_user_goes_to_dashboard_from_the_free_path(self):
        """
        GIVEN a signed-in user
        WHEN the landing page is rendered
        THEN both the hero and the free path lead to the dashboard, not registration
        """
        user = User.objects.create_user("twopaths", password="pw")
        c = Client()
        c.force_login(user)
        html = c.get("/").content.decode()
        start = html.index('id="how-to-start"')
        section = html[start:html.index("</section>", start)]
        hero = html[html.index('id="hero"'):start]
        for part in (hero, section):
            self.assertIn('href="/editor/" class="btn-primary-landing">Go to Dashboard', part)
            self.assertNotIn("/accounts/register/", part)

    def test_no_discord_no_calendar_and_no_unbacked_hosting_claims(self):
        """
        GIVEN the landing (EN and RU), educators, services and Pro pages
        WHEN each is rendered
        THEN none links to Discord or to a booking calendar, none carries the old
             book_call_clicked listener, the footer offers "Request a demo", and the
             landing page makes no GDPR or "your infrastructure" claim
        """
        for url in ("/", "/ru/", "/for-educators/", "/services/", "/pro/"):
            resp = Client().get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertNotContains(resp, "discord", msg_prefix=url)
            self.assertNotContains(resp, "cal.com", msg_prefix=url)
            self.assertNotContains(resp, "book_call_clicked", msg_prefix=url)
            self.assertNotContains(resp, "data-book-call", msg_prefix=url)
            self.assertContains(resp, 'href="/demo/?src=footer"', msg_prefix=url)
        landing = Client().get("/")
        self.assertNotContains(landing, "GDPR-Friendly")
        self.assertNotContains(landing, "stays on your infrastructure")

    def test_educators_hero_offers_demo_request(self):
        """
        GIVEN the educators page
        WHEN /for-educators/ is rendered
        THEN its hero offers "Request a demo" to /demo/?src=educators
        """
        resp = Client().get("/for-educators/")
        self.assertContains(resp, 'href="/demo/?src=educators" class="btn-secondary-landing">Request a demo')

    def test_russian_homepage_translates_the_new_buttons(self):
        """
        GIVEN the Russian homepage
        WHEN /ru/ is rendered
        THEN the hero buttons, the footer quote and the footer labels are in Russian
        """
        resp = Client().get("/ru/")
        self.assertContains(resp, "Начать бесплатно")
        self.assertContains(resp, "Запросить демо")
        self.assertContains(resp, "Джейн Джекобс")
        self.assertContains(resp, "Вовлечение жителей")
        self.assertContains(resp, "Сравнение сервисов")
        self.assertNotContains(resp, "Get Mapsurvey free")


class LandingFooterTest(TestCase):
    """Footer after Notion's (request-demo-form): brand + quote, five columns, bottom row."""

    def _footer(self, url="/"):
        html = Client().get(url).content.decode()
        return html[html.index('<footer class="landing-footer">'):html.index("</footer>")]

    def test_five_columns_in_order(self):
        """
        GIVEN any page built on the landing base template
        WHEN its footer is rendered
        THEN it shows Product, Mapsurvey for, Use cases, Resources and Company, in that order
        """
        footer = self._footer("/for-planners/")
        titles = ["Product", "Mapsurvey for", "Use cases", "Resources", "Company"]
        positions = [footer.index('landing-footer__col-title">%s<' % t) for t in titles]
        self.assertEqual(positions, sorted(positions))

    def test_keeps_every_internal_marketing_link(self):
        """
        GIVEN the regrouped footer
        WHEN it is rendered
        THEN every internal marketing page it linked before is still linked, plus /demo/
        """
        footer = self._footer()
        for href in ("#features", "#demo", "/pricing/", "/services/", "/demo/?src=footer",
                     "/for-planners/", "/for-government/", "/for-researchers/", "/for-educators/",
                     "/for-consultants/", "/community-engagement-platform/",
                     "/public-consultation-software/", "/civic-engagement/",
                     "/participatory-budgeting/", "/stories/", "/participatory-mapping-tools/",
                     "/alternatives/maptionnaire/", "/alternatives/social-pinpoint/",
                     "/alternatives/metroquest/", "/trust/", 'href="/ru/"'):
            self.assertIn(href, footer, href)

    def test_brand_block_with_quote(self):
        """
        GIVEN the footer
        WHEN it is rendered
        THEN the brand block carries the wordmark and the Jane Jacobs quote with attribution
        """
        footer = self._footer()
        self.assertIn('class="landing-footer__brand"', footer)
        self.assertIn("they are created by everybody", footer)
        self.assertIn("Jane Jacobs", footer)

    def test_legal_links_and_owner_survive_the_redesign(self):
        """
        GIVEN the legal links and owner line added for the DPGA application (#290)
        WHEN the redesigned footer is rendered
        THEN Company links Terms of use and Privacy & Trust, and the copyright names the owner
        """
        footer = self._footer()
        company = footer[footer.index('landing-footer__col-title">Company<'):]
        self.assertIn('href="/terms/">Terms of use<', company)
        self.assertIn('href="/trust/">Privacy & Trust<', company)
        self.assertIn("2021&ndash;", footer)
        self.assertIn("Artem Koniukhov", footer)

    def test_no_auth_links(self):
        """
        GIVEN the footer
        WHEN it is rendered
        THEN it has no login or registration links
        """
        footer = self._footer()
        self.assertNotIn("/accounts/login/", footer)
        self.assertNotIn("/accounts/register/", footer)

class LandingRevealProgressiveTest(SimpleTestCase):
    """Landing scroll-reveal must be progressive enhancement (landing-page spec)."""

    def test_reveal_visible_by_default_in_css(self):
        """
        GIVEN the landing stylesheet
        WHEN the .reveal rules are read
        THEN the hidden starting state is scoped to html.js-reveal only,
             so a no-JS render shows every section
        """
        import pathlib
        css = pathlib.Path('survey/assets/css/landing.css').read_text()
        base_rule = css.split('.reveal {', 1)[1].split('}', 1)[0]
        self.assertIn('opacity: 1', base_rule)
        self.assertIn('html.js-reveal .reveal', css)

    def test_head_gate_respects_reduced_motion(self):
        """
        GIVEN the landing base template
        WHEN the head gate script is read
        THEN it checks IntersectionObserver support and prefers-reduced-motion
             before enabling the hidden reveal state
        """
        import pathlib
        html = pathlib.Path('survey/templates/base_landing.html').read_text()
        self.assertIn("classList.add('js-reveal')", html)
        self.assertIn('prefers-reduced-motion', html)
        self.assertIn('IntersectionObserver', html)


class LandingShowcaseRefreshTest(TestCase):
    """See it in action + Capabilities rebuilt from the Copenhagen demo (landing-showcase-refresh)."""

    def test_showcase_has_four_steps_with_screenshots(self):
        """
        GIVEN the landing page
        WHEN it is rendered
        THEN the showcase has BUILD, COLLECT, ANALYZE and SHARE rows, and every inline
             and full-size screenshot it references exists in the assets
        """
        import os
        from django.conf import settings as dj_settings
        html = Client().get('/').content.decode()
        start = html.index('id="showcase"')
        showcase = html[start:html.index('</section>', start)]
        for step in ('01 &middot; BUILD', '02 &middot; COLLECT', '03 &middot; ANALYZE', '04 &middot; SHARE'):
            self.assertIn(step, showcase)
        assets = os.path.join(dj_settings.BASE_DIR, 'survey', 'assets', 'img', 'landing')
        for key in ('build', 'collect', 'analyze', 'share'):
            for stem in (key, f'{key}-full'):
                # {% static %} renders a hashed name (build.1a2b3c.webp) under the manifest storage.
                self.assertRegex(showcase, rf'img/landing/{stem}\.(?:[0-9a-f]+\.)?webp')
                self.assertTrue(os.path.exists(os.path.join(assets, f'{stem}.webp')), stem)

    def test_capabilities_are_the_six_new_cards_without_stale_claims(self):
        """
        GIVEN the landing page
        WHEN it is rendered
        THEN the capabilities grid holds exactly the six new cards, and the stale
             "13 question types" and "GeoJSON + CSV" claims are gone
        """
        html = Client().get('/').content.decode()
        start = html.index('id="features"')
        features = html[start:html.index('</section>', start)]
        titles = ['Questions made for maps', 'Your data on the map', 'A map people build together',
                  'Built to be answered', 'Clean and analyse', 'Export and publish']
        self.assertEqual(features.count('class="feature-card__title"'), 6)
        for title in titles:
            self.assertIn(title, features)
        self.assertNotIn('13 question types', html)
        self.assertNotIn('GeoJSON + CSV', html)
