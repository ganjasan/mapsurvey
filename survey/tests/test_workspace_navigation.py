"""Tests for the `workspace-navigation` capability (openspec/changes/app-sidebar/specs/workspace-navigation/spec.md).

The application sidebar (change app-sidebar, #538): where it shows, what it lists, which item is
active, the plan chip, the two widths, and what left the header.
"""
import re

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import NoReverseMatch, reverse

from billing.tests.helpers import make_sub
from survey import app_nav
from survey.models import Membership
from survey.tests.helpers import _make_org, _make_survey_with_section

SIDEBAR = 'id="appSidebar"'


class _SidebarFixture(TestCase):
    def setUp(self):
        self.org = _make_org('NavOrg')
        self.owner = User.objects.create_user('navowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey, _ = _make_survey_with_section(self.org, 'nav_survey', owner=self.owner)
        self.client.login(username='navowner', password='pass')

    def html(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return response.content.decode()

    @staticmethod
    def active_keys(html):
        return re.findall(r'class="app-item active"[^>]*data-nav-key="([a-z_]+)"', html)


class SidebarPresenceTest(_SidebarFixture):

    def test_creator_pages_carry_the_sidebar(self):
        """
        GIVEN a signed-in workspace owner
        WHEN they open the dashboard, Members, Plan & billing, Preferences, API & connections,
             What's new and a survey's Build and Responses pages
        THEN every page carries the one sidebar
        """
        urls = [
            reverse('editor') + '?dashboard=1',
            reverse('org_members', args=[self.org.slug]),
            reverse('org_billing', args=[self.org.slug]),
            reverse('org_settings', args=[self.org.slug]),
            reverse('editor_account_preferences'),
            reverse('editor_account_connections'),
            reverse('whats_new'),
            reverse('editor_survey_detail', args=[self.survey.uuid]),
            reverse('editor_survey_analytics', args=[self.survey.uuid]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.html(url).count(SIDEBAR), 1)

    def test_never_outside_creator_paths(self):
        """
        GIVEN the same signed-in creator
        WHEN they open the sign-in page and their own survey as a respondent
        THEN neither page carries the sidebar
        """
        self.assertNotIn(SIDEBAR, self.client.get(reverse('login')).content.decode())
        respondent = self.client.get(reverse('survey', kwargs={'survey_slug': self.survey.uuid}), follow=True)
        self.assertNotIn(SIDEBAR, respondent.content.decode())

    def test_anonymous_sign_in_page_keeps_the_old_header(self):
        """
        GIVEN a visitor who is not signed in
        WHEN they open the sign-in page
        THEN it renders the pre-change site navbar and no sidebar
        """
        self.client.logout()
        html = self.client.get(reverse('login')).content.decode()
        self.assertIn('class="site-navbar"', html)
        self.assertNotIn(SIDEBAR, html)
        self.assertNotIn('app-burger', html)

    def test_shows_sidebar_is_a_path_rule(self):
        """
        GIVEN requests from a signed-in user
        WHEN app_nav.shows_sidebar is asked about creator and respondent paths
        THEN only /editor/, /org/ and /billing/ answer yes
        """
        rf = RequestFactory()
        for path, expected in [('/editor/', True), ('/org/x/members/', True), ('/billing/return/', True),
                               ('/surveys/abc/', False), ('/r/slug/', False), ('/oauth/authorize/', False),
                               ('/accounts/login/', False)]:
            request = rf.get(path)
            request.user = self.owner
            with self.subTest(path=path):
                self.assertEqual(app_nav.shows_sidebar(request), expected)


class SidebarContentsTest(_SidebarFixture):

    def test_items_in_order(self):
        """
        GIVEN an owner on the dashboard
        WHEN the sidebar renders
        THEN it lists Surveys, API, MCP, Map styles, Members, Plan & billing, General, What's new,
             in that order
        """
        html = self.html(reverse('editor') + '?dashboard=1')
        keys = re.findall(r'data-nav-key="([a-z_]+)"', html[html.index(SIDEBAR):])
        self.assertEqual(keys[:8], ['surveys', 'api', 'mcp', 'map_styles', 'members', 'billing', 'settings', 'whats_new'])

    def test_map_styles_for_every_member(self):
        """
        GIVEN a member with the viewer role
        WHEN they open the dashboard and then the library
        THEN the sidebar has a Map styles item under Library with the map_styles Pro mark,
             and the library page marks it active
        """
        viewer = User.objects.create_user('navviewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username='navviewer', password='pass')
        html = self.html(reverse('editor') + '?dashboard=1')
        self.assertIn('data-nav-key="map_styles"', html)
        library = html[html.index('data-nav-key="map_styles"') - 600:html.index('data-nav-key="map_styles"')]
        self.assertIn('Library', library)
        self.assertEqual(self.active_keys(self.html(reverse('org_map_styles', args=[self.org.slug]))), ['map_styles'])

    def test_active_item_follows_the_page(self):
        """
        GIVEN the owner
        WHEN they open Members, a survey's Responses page and the dashboard
        THEN Members, Surveys and Surveys are the active items
        """
        self.assertEqual(self.active_keys(self.html(reverse('org_members', args=[self.org.slug]))), ['members'])
        self.assertEqual(self.active_keys(self.html(reverse('editor_survey_analytics', args=[self.survey.uuid]))),
                         ['surveys'])
        self.assertEqual(self.active_keys(self.html(reverse('editor') + '?dashboard=1')), ['surveys'])

    def test_plan_and_billing_for_owners_and_admins_only(self):
        """
        GIVEN a member with the editor role
        WHEN they open the dashboard
        THEN the sidebar has no Plan & billing item
        """
        editor = User.objects.create_user('naveditor', password='pass')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        self.client.login(username='naveditor', password='pass')
        html = self.html(reverse('editor') + '?dashboard=1')
        self.assertIn('data-nav-key="members"', html)
        self.assertNotIn('data-nav-key="billing"', html)

    def test_every_module_resolves(self):
        """
        GIVEN the registry rows
        WHEN each URL name is reversed (with a slug where the row is workspace-scoped)
        THEN none fails
        """
        for item in app_nav.MODULES + app_nav.INTEGRATIONS + app_nav.WORKSPACE:
            with self.subTest(item=item.key):
                try:
                    reverse(item.url_name, args=['slug'] if item.org_scoped else [])
                except NoReverseMatch as exc:  # pragma: no cover - the failure message
                    self.fail(f'{item.key}: {exc}')

    def test_plan_chip_reads_the_entitlement(self):
        """
        GIVEN a Free workspace, then the same workspace with a live Pro subscription
        WHEN the dashboard renders
        THEN the workspace row shows no chip, then PRO
        """
        url = reverse('editor') + '?dashboard=1'
        self.assertNotIn('class="app-ws-plan"', self.html(url))
        make_sub(self.org)
        self.assertIn('<span class="app-ws-plan">PRO</span>', self.html(url))

    def test_plan_chip_for_a_live_trial(self):
        """
        GIVEN a Free workspace whose owner claimed the Pro trial
        WHEN plan_chip is asked
        THEN it answers 'trial'
        """
        from billing import trial
        trial.claim(self.org, self.owner)
        self.assertEqual(app_nav.plan_chip(self.org, self.owner), 'trial')

    def test_whats_new_dot_in_the_footer(self):
        """
        GIVEN a creator with unseen changelog entries
        WHEN the dashboard renders
        THEN the sidebar's What's new item carries the dot
        """
        from survey.models import CreatorPreferences
        CreatorPreferences.objects.update_or_create(user=self.owner, defaults={'changelog_seen': ''})
        html = self.html(reverse('editor') + '?dashboard=1')
        footer = html[html.index('data-nav-key="whats_new"'):]
        self.assertIn('wn-dot', footer[:footer.index('</a>')])


class HeaderTest(_SidebarFixture):
    #: The header gift: a wn-nav-icon link to What's new ("?" shares the class, not the href).
    GIFT = re.compile(r'<a class="wn-nav-icon[^"]*" href="/editor/whats-new/"')


    def test_dashboard_header_loses_only_what_moved(self):
        """
        GIVEN the owner on the dashboard
        WHEN the header renders
        THEN it has no gift icon and no workspace dropdown, and keeps "?", the language
             control, the username menu with Preferences, and Logout as a POST form
        """
        html = self.html(reverse('editor') + '?dashboard=1')
        self.assertNotRegex(html, self.GIFT)
        self.assertNotIn('fa-building', html)
        self.assertIn('help-nav-icon', html)
        self.assertIn('fa-globe', html)
        self.assertIn('app-user-menu', html)
        menu = html[html.index('app-user-menu'):]
        self.assertIn('href="%s"' % reverse('editor_account_preferences'), menu[:menu.index('</div>')])
        self.assertIn('action="%s"' % reverse('logout'), html)

    def test_workspace_pages_have_no_second_navigation(self):
        """
        GIVEN the owner
        WHEN they open Plan & billing, Members, General and the advice page
        THEN outside the sidebar no page links to the dashboard, and no page links to another
             of those pages from a button row of its own
        """
        dashboard = 'href="%s"' % reverse('editor')
        pages = {
            'org_billing': ('org_settings', 'org_members'),
            'org_members': ('org_settings',),
            'org_settings': ('org_members',),
            'org_help': ('org_billing',),
        }
        for name, siblings in pages.items():
            with self.subTest(page=name):
                html = self.html(reverse(name, args=[self.org.slug]))
                body = html[html.index('</aside>'):]
                self.assertNotIn(dashboard, body)
                for sibling in siblings:
                    self.assertNotIn('href="%s"' % reverse(sibling, args=[self.org.slug]), body)

    def test_editor_username_menu_has_the_confirmation_toggle(self):
        """
        GIVEN the owner on a survey's Build page
        WHEN the username menu renders
        THEN it carries Preferences and the confirmation toggle, and the header has no gift
        """
        html = self.html(reverse('editor_survey_detail', args=[self.survey.uuid]))
        menu = html[html.index('app-user-menu'):]
        menu = menu[:menu.index('d-md-none')]
        self.assertIn(reverse('editor_account_preferences'), menu)
        self.assertIn('editor-confirm-toggle', menu)
        self.assertNotRegex(html, self.GIFT)


class WidthTest(_SidebarFixture):
    BODY_RAIL = re.compile(r'<body[^>]*\bapp-rail app-rail-default\b')

    def test_survey_pages_open_as_a_rail(self):
        """
        GIVEN the owner
        WHEN they open a survey's Build page
        THEN <body> carries app-rail and app-rail-default
        """
        self.assertRegex(self.html(reverse('editor_survey_detail', args=[self.survey.uuid])), self.BODY_RAIL)

    def test_workspace_pages_open_expanded(self):
        """
        GIVEN the owner
        WHEN they open the dashboard and Preferences
        THEN <body> carries no rail class from the server
        """
        for url in (reverse('editor') + '?dashboard=1', reverse('editor_account_preferences')):
            with self.subTest(url=url):
                self.assertNotRegex(self.html(url), self.BODY_RAIL)
