"""Tests for the `pricing` capability: plan cards, /pricing/, the nav entry, the cards on Plan & billing.

Spec: openspec/changes/pricing-page/specs/pricing/spec.md
(after archive: openspec/specs/pricing/spec.md). One module per capability -- see #273.
"""
import re

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from survey.models import Membership

from ..features import FEATURES, PLAN_PRO
from ..models import CheckoutIntent
from .helpers import PPG_SETTINGS, make_org, make_sub


def _card(html, heading_id):
    """The markup of one plan card, from its <section> to the next one."""
    start = html.rindex('<section', 0, html.index(f'id="{heading_id}"'))
    end = html.index('</section>', start)
    return html[start:end]


class PricingPageTest(TestCase):
    def test_anonymous_visitor_sees_three_cards(self):
        """
        GIVEN an anonymous visitor
        WHEN they open /pricing/
        THEN the page answers 200 with Free ($0), Pro ($49 / $490) and Done for you (no figure,
             a call), and the Free and Pro buttons lead to registration
        """
        resp = Client().get('/pricing/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        free = _card(html, 'pricing-plans-free')
        pro = _card(html, 'pricing-plans-pro')
        service = _card(html, 'pricing-plans-service')
        self.assertIn('$0', free)
        self.assertIn('$49', pro)
        self.assertIn('$490', pro)
        self.assertNotIn('$', service)
        self.assertIn('href="/demo/?src=pricing"', service)
        self.assertIn('href="/services/"', service)
        self.assertIn('/accounts/register/', free)
        self.assertIn('/accounts/register/', pro)

    def test_pro_bullets_follow_the_feature_registry(self):
        """
        GIVEN the Pro features declared in billing/features.py
        WHEN /pricing/ is rendered
        THEN every Pro feature label is a bullet on the Pro card
        """
        pro = _card(Client().get('/pricing/').content.decode(), 'pricing-plans-pro')
        labels = [str(f.label) for f in FEATURES.values() if PLAN_PRO in f.plans]
        self.assertTrue(labels)
        for label in labels:
            self.assertIn(label.replace('"', '&quot;'), pro)

    def test_period_switch_needs_no_script(self):
        """
        GIVEN the Pro card's monthly/yearly switch
        WHEN /pricing/ is rendered
        THEN it is two radios with labels, monthly checked, and the card carries both figures
        """
        html = Client().get('/pricing/').content.decode()
        self.assertRegex(html, r'id="pricing-plans-monthly"[^>]*checked')
        self.assertIn('id="pricing-plans-yearly"', html)
        self.assertIn('for="pricing-plans-yearly"', html)
        self.assertIn('plan-price--yearly', html)

    def test_payment_questions_and_questionnaire_link(self):
        """
        GIVEN a buyer who needs to know how payment works
        WHEN /pricing/ is rendered
        THEN it names PayPro Global, invoice / purchase order, that cancelling keeps the data,
             and links to /pro/
        """
        html = Client().get('/pricing/').content.decode()
        self.assertIn('PayPro Global', html)
        self.assertIn('purchase order', html)
        self.assertIn('Every survey, response and setting stays', html)
        self.assertIn('href="/pro/"', html)

    def test_owner_is_sent_to_plan_and_billing(self):
        """
        GIVEN a signed-in owner of a workspace
        WHEN they open /pricing/
        THEN the Pro button links to that workspace's Plan & billing page
        """
        org, _owner = make_org()
        c = Client()
        c.login(username='bill_owner', password='pass')
        pro = _card(c.get('/pricing/').content.decode(), 'pricing-plans-pro')
        self.assertIn(f'href="/org/{org.slug}/billing/"', pro)

    def test_in_sitemap_and_nav_instead_of_pro(self):
        """
        GIVEN pages built on base_landing.html
        WHEN the homepage and sitemap.xml are fetched
        THEN the navbar links "Pricing" to /pricing/ and not /pro/, and the sitemap lists /pricing/
        """
        html = Client().get('/').content.decode()
        nav = html[html.index('id="nav-links"'):html.index('</nav>')]
        self.assertIn('href="/pricing/"', nav)
        self.assertNotIn('href="/pro/"', nav)
        self.assertContains(Client().get('/sitemap.xml'), '/pricing/</loc>')

    def test_category_landing_renders_the_same_cards(self):
        """
        GIVEN the pricing block of the category landings
        WHEN /civic-engagement/ is rendered
        THEN it carries the three shared cards and links to /pricing/, with no "early access" tag
        """
        html = Client().get('/civic-engagement/').content.decode()
        for heading in ('landing-plans-free', 'landing-plans-pro', 'landing-plans-service'):
            self.assertIn(f'id="{heading}"', html)
        self.assertIn('href="/pricing/"', html)
        self.assertNotIn('early access', html)


@override_settings(**PPG_SETTINGS)
class BillingPlanCardsTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.admin = User.objects.create_user(username='bill_admin', password='pass', email='a@example.test')
        Membership.objects.create(user=self.admin, organization=self.org, role='admin')
        self.url = f'/org/{self.org.slug}/billing/'

    def _page(self, username):
        c = Client()
        c.login(username=username, password='pass')
        return c.get(self.url).content.decode()

    def test_free_owner_sees_prices_and_one_upgrade_button(self):
        """
        GIVEN the owner of a Free organisation
        WHEN they open Plan & billing
        THEN the Free card is the current plan, the Pro card shows $49 / $490 with one
             Upgrade to Pro form whose period radios belong to it, plus Get a quote (yearly, quote=1),
             and "Prices" leads to /pricing/
        """
        html = self._page('bill_owner')
        free = _card(html, 'billing-plans-free')
        pro = _card(html, 'billing-plans-pro')
        self.assertIn('Current plan', free)
        self.assertNotIn('Current plan', pro)
        self.assertIn('$49', pro)
        self.assertIn('$490', pro)
        self.assertIn('id="billing-plans-checkout"', pro)
        self.assertIn('Upgrade to Pro', pro)
        self.assertEqual(len(re.findall(r'name="period"[^>]*form="billing-plans-checkout"', html)), 2)
        self.assertIn('name="quote" value="1"', pro)
        self.assertIn('href="/pricing/"', html)
        self.assertIn('href="/demo/?src=billing"', _card(html, 'billing-plans-service'))
        self.assertNotIn('href="/#pricing"', html)

    def test_yearly_selection_starts_yearly_checkout(self):
        """
        GIVEN the owner chose yearly on the Pro card
        WHEN the checkout form posts the radio's value
        THEN the checkout starts for the yearly product
        """
        c = Client()
        c.login(username='bill_owner', password='pass')
        r = c.post(f'/org/{self.org.slug}/billing/checkout/', {'period': 'yearly'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CheckoutIntent.objects.get().product_key, 'pro_yearly')

    def test_admin_cannot_upgrade(self):
        """
        GIVEN an admin who is not the owner
        WHEN they open Plan & billing
        THEN the Pro card says only the owner can upgrade and carries no checkout form
        """
        pro = _card(self._page('bill_admin'), 'billing-plans-pro')
        self.assertIn('Only the organisation owner can upgrade.', pro)
        self.assertNotIn('<form', pro)

    def test_pro_organisation_marks_pro_current(self):
        """
        GIVEN an organisation with an active Pro subscription
        WHEN the owner opens Plan & billing
        THEN the Pro card is the current plan with no upgrade button
        """
        make_sub(self.org)
        html = self._page('bill_owner')
        pro = _card(html, 'billing-plans-pro')
        self.assertIn('Current plan', pro)
        self.assertNotIn('Upgrade to Pro', pro)
        self.assertNotIn('Current plan', _card(html, 'billing-plans-free'))

    @override_settings(PPG_PRODUCTS={})
    def test_nothing_on_sale_shows_no_checkout(self):
        """
        GIVEN no PayPro products configured (nothing sold)
        WHEN the owner opens Plan & billing
        THEN the cards render without a checkout form
        """
        pro = _card(self._page('bill_owner'), 'billing-plans-pro')
        self.assertIn('$49', pro)
        self.assertNotIn('<form', pro)
