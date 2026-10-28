"""Tests for the `landing-page-localization` capability (openspec/specs/landing-page-localization/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
import re


class RussianLandingHreflangTest(TestCase):
    """Russian homepage at /ru/, hreflang alternates, https sitemap (change ru-landing-hreflang, #248).

    Google dropped mapsurvey.org from brand results for Russian-interface searchers in CIS
    countries: the site declared no language beyond lang="en". These tests pin the Russian twin
    of the homepage, the hreflang graph that ties the two together, and the sitemap/robots URLs
    that used to say http:// behind the TLS proxy.
    """

    HREFLANG = re.compile(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">')
    HOME_ALTERNATES = {
        ('en', 'https://mapsurvey.org/'),
        ('ru', 'https://mapsurvey.org/ru/'),
        ('x-default', 'https://mapsurvey.org/'),
    }

    def _alternates(self, response):
        return set(self.HREFLANG.findall(response.content.decode()))

    # --- the page itself -------------------------------------------------------------

    def test_ru_homepage_renders_in_russian(self):
        """
        GIVEN an anonymous visitor
        WHEN /ru/ is requested
        THEN the page is Russian: lang="ru", Content-Language ru, Russian title and hero,
             and its canonical is https://mapsurvey.org/ru/
        """
        response = Client().get('/ru/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Language'], 'ru')
        body = response.content.decode()
        self.assertIn('<html lang="ru">', body)
        self.assertIn('<title>Mapsurvey — опросы на карте', body)
        self.assertIn('Самый простой способ собирать геоданные', body)
        self.assertIn('<link rel="canonical" href="https://mapsurvey.org/ru/">', body)
        self.assertNotIn('The easiest way to collect geographic data', body)

    def test_ru_homepage_for_a_signed_in_creator(self):
        """
        GIVEN a signed-in creator
        WHEN /ru/ is requested
        THEN it renders in Russian with the dashboard link instead of the sign-up one
        """
        user = User.objects.create_user('ru_landing_creator', password='pw-12345678')
        client = Client()
        client.force_login(user)
        response = client.get('/ru/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Перейти в панель управления')

    def test_english_homepage_ignores_a_russian_browser(self):
        """
        GIVEN a visitor whose Accept-Language and language cookie are both Russian
        WHEN / is requested
        THEN the page stays English, because only /ru/ is Russian
        """
        from django.conf import settings as dj_conf
        client = Client(HTTP_ACCEPT_LANGUAGE='ru-RU,ru;q=0.9')
        client.cookies[dj_conf.LANGUAGE_COOKIE_NAME] = 'ru'
        body = client.get('/').content.decode()
        self.assertIn('<html lang="en">', body)
        self.assertIn('The easiest way to collect geographic data', body)

    def test_ru_homepage_ignores_an_english_browser(self):
        """
        GIVEN a visitor whose Accept-Language is English
        WHEN /ru/ is requested
        THEN the page is Russian anyway
        """
        body = Client(HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9').get('/ru/').content.decode()
        self.assertIn('<html lang="ru">', body)
        self.assertIn('Самый простой способ собирать геоданные', body)

    # --- hreflang --------------------------------------------------------------------

    def test_homepage_pair_declares_reciprocal_alternates(self):
        """
        GIVEN the English and the Russian homepage
        WHEN each is rendered
        THEN both carry exactly the same en / ru / x-default alternates
        """
        client = Client()
        self.assertEqual(self._alternates(client.get('/')), self.HOME_ALTERNATES)
        self.assertEqual(self._alternates(client.get('/ru/')), self.HOME_ALTERNATES)

    def test_audience_page_declares_itself_as_english_and_default(self):
        """
        GIVEN an English-only marketing page
        WHEN /for-planners/ is rendered
        THEN it declares en and x-default pointing at itself and no ru alternate
        """
        url = 'https://mapsurvey.org/for-planners/'
        self.assertEqual(self._alternates(Client().get('/for-planners/')),
                         {('en', url), ('x-default', url)})

    def test_every_marketing_page_carries_hreflang(self):
        """
        GIVEN every page built on base_landing.html that has a fixed URL
        WHEN it is rendered
        THEN it declares an x-default alternate equal to its canonical URL
        """
        canonical = re.compile(r'<link rel="canonical" href="([^"]+)">')
        paths = ['/', '/ru/', '/services/', '/pro/', '/trust/', '/stories/',
                 '/for-planners/', '/for-government/', '/for-researchers/',
                 '/for-educators/', '/for-consultants/',
                 '/community-engagement-platform/', '/public-consultation-software/',
                 '/civic-engagement/', '/participatory-budgeting/',
                 '/alternatives/maptionnaire/', '/alternatives/social-pinpoint/',
                 '/alternatives/metroquest/', '/participatory-mapping-tools/']
        client = Client()
        for path in paths:
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                body = response.content.decode()
                alternates = dict(self.HREFLANG.findall(body))
                self.assertEqual(alternates.get('x-default'),
                                 'https://mapsurvey.org/' if path == '/ru/'
                                 else canonical.search(body).group(1))

    # --- switcher and in-page links ---------------------------------------------------

    def test_switcher_on_the_english_homepage(self):
        """
        GIVEN the English homepage
        WHEN it is rendered
        THEN the navbar marks EN as current and links RU to /ru/
        """
        body = Client().get('/').content.decode()
        self.assertIn('<span class="lang-switch__current" aria-current="page">EN</span>', body)
        self.assertRegex(body, r'<a href="/ru/" class="lang-switch__btn"[^>]*>RU</a>')

    def test_switcher_on_the_russian_homepage(self):
        """
        GIVEN the Russian homepage
        WHEN it is rendered
        THEN the navbar marks RU as current and links EN to /
        """
        body = Client().get('/ru/').content.decode()
        self.assertIn('<span class="lang-switch__current" aria-current="page">RU</span>', body)
        self.assertRegex(body, r'<a href="/" class="lang-switch__btn"[^>]*>EN</a>')

    def test_no_switcher_on_english_only_pages(self):
        """
        GIVEN a marketing page without a Russian twin
        WHEN /trust/ is rendered
        THEN the navbar shows no EN / RU switcher, but the footer links to /ru/ as "Русский"
        """
        body = Client().get('/trust/').content.decode()
        self.assertNotIn('lang-switch__current', body)
        self.assertRegex(body, r'<a href="/ru/" hreflang="ru" lang="ru">Русский</a>')

    def test_in_page_links_stay_on_the_russian_homepage(self):
        """
        GIVEN the Russian homepage
        WHEN it is rendered
        THEN the brand and the Features / Demo links point at /ru/, not at the English page
        """
        body = Client().get('/ru/').content.decode()
        self.assertIn('<a href="/ru/" class="landing-nav__brand">', body)
        self.assertIn('href="/ru/#features"', body)
        self.assertIn('href="/ru/#demo"', body)
        self.assertNotIn('href="/#features"', body)

    def test_in_page_links_elsewhere_point_at_the_english_homepage(self):
        """
        GIVEN an English-only marketing page
        WHEN /for-planners/ is rendered
        THEN Features points at /#features and the brand at /
        """
        body = Client().get('/for-planners/').content.decode()
        self.assertIn('href="/#features"', body)
        self.assertIn('<a href="/" class="landing-nav__brand">', body)

    # --- catalog ---------------------------------------------------------------------

    def test_every_homepage_string_has_a_russian_translation(self):
        """
        GIVEN every msgid the homepage templates mark for translation
        WHEN the compiled `ru` catalog of this app is read directly
        THEN each one is there, because msgfmt drops empty and fuzzy entries and a missing
             one would put an English sentence on /ru/
        """
        import ast
        import gettext as gettext_module
        import pathlib
        from django.utils.translation.template import templatize

        app = pathlib.Path(__file__).resolve().parent.parent
        literal = re.compile(r"gettext\((u?'(?:[^'\\]|\\.)*')\)")
        msgids = set()
        for name in ('landing.html', 'base_landing.html', 'partials/_story_card.html'):
            source = (app / 'templates' / name).read_text(encoding='utf-8')
            for match in literal.finditer(templatize(source, origin=name)):
                msgids.add(ast.literal_eval(match.group(1)))
        self.assertGreater(len(msgids), 100)

        with open(app / 'locale' / 'ru' / 'LC_MESSAGES' / 'django.mo', 'rb') as fh:
            catalog = gettext_module.GNUTranslations(fh)._catalog
        missing = sorted(m for m in msgids if not catalog.get(m))
        self.assertEqual(missing, [], 'English left on /ru/:\n  ' + '\n  '.join(missing))

    # --- sitemap and robots ----------------------------------------------------------

    @override_settings(ALLOWED_HOSTS=['mapsurvey.org', 'testserver'])
    def test_sitemap_uses_the_forwarded_https_scheme(self):
        """
        GIVEN production behind the TLS proxy, which sends X-Forwarded-Proto: https
        WHEN /sitemap.xml is requested on mapsurvey.org
        THEN every <loc> starts with https://mapsurvey.org/
        """
        body = Client().get('/sitemap.xml', HTTP_HOST='mapsurvey.org',
                            HTTP_X_FORWARDED_PROTO='https').content.decode()
        locs = re.findall(r'<loc>([^<]+)</loc>', body)
        self.assertTrue(locs)
        self.assertEqual([l for l in locs if not l.startswith('https://mapsurvey.org/')], [])

    @override_settings(ALLOWED_HOSTS=['mapsurvey.org', 'testserver'],
                       SITE_URL='https://mapsurvey.org')
    def test_robots_falls_back_to_site_url_scheme_on_the_canonical_host(self):
        """
        GIVEN a request to the SITE_URL host that arrives without X-Forwarded-Proto
        WHEN /robots.txt is requested
        THEN the Sitemap line takes SITE_URL's https scheme
        """
        body = Client().get('/robots.txt', HTTP_HOST='mapsurvey.org').content.decode()
        self.assertIn('Sitemap: https://mapsurvey.org/sitemap.xml', body)

    @override_settings(ALLOWED_HOSTS=['localhost', 'testserver'],
                       SITE_URL='https://mapsurvey.org')
    def test_local_development_keeps_plain_http(self):
        """
        GIVEN a developer's server on localhost over plain HTTP
        WHEN /sitemap.xml is requested
        THEN entries keep http://localhost, because that host is not SITE_URL's
        """
        body = Client().get('/sitemap.xml', HTTP_HOST='localhost').content.decode()
        self.assertIn('<loc>http://localhost/</loc>', body)

    def test_sitemap_lists_the_russian_homepage_with_alternates(self):
        """
        GIVEN the homepage pair
        WHEN /sitemap.xml is fetched
        THEN it is well-formed, declares the xhtml namespace, lists /ru/, and both homepage
             entries carry en / ru / x-default alternates matching the pages
        """
        import xml.etree.ElementTree as ET
        body = Client().get('/sitemap.xml').content
        root = ET.fromstring(body)
        sm = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
        xhtml = '{http://www.w3.org/1999/xhtml}'
        entries = {u.find(sm + 'loc').text: u for u in root.findall(sm + 'url')}
        self.assertIn('http://testserver/ru/', entries)
        expected = {('en', 'http://testserver/'), ('ru', 'http://testserver/ru/'),
                    ('x-default', 'http://testserver/')}
        for loc in ('http://testserver/', 'http://testserver/ru/'):
            with self.subTest(loc=loc):
                links = {(l.get('hreflang'), l.get('href'))
                         for l in entries[loc].findall(xhtml + 'link')}
                self.assertEqual(links, expected)

    def test_robots_allows_the_russian_homepage(self):
        """
        GIVEN the robots.txt allow-list
        WHEN /robots.txt is fetched
        THEN it allows /ru/
        """
        self.assertContains(Client().get('/robots.txt'), 'Allow: /ru/')
