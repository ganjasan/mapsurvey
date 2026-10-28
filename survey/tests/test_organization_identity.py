"""Tests for the `organization-identity` capability (openspec/specs/organization-identity/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import Organization, SurveyHeader, Membership
from survey.tests.helpers import _make_org


class OrganizationSlugRoutabilityTest(TestCase):
    """An organization slug must always reverse through `org/<slug>/...`.

    Two production rows held slugs with spaces and an apostrophe ("CBPR Summer
    26' PM"), written straight from the settings form. `{% url 'org_settings'
    active_org.slug %}` is in the account dropdown of every base template, so
    those owners got a 500 on every page of the editor -- including the settings
    page that would have let them fix it.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username='slug_owner', password='pass')
        self.org = _make_org('SlugOrg')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        # The dashboard redirects an empty org straight to the create wizard, so
        # it never renders the account dropdown -- and the dropdown is where the
        # `{% url %}` crash lives. One survey keeps the dashboard on screen.
        SurveyHeader.objects.create(name='slug_survey', organization=self.org)
        self.client.login(username='slug_owner', password='pass')

    def test_settings_rejects_unroutable_slug(self):
        """
        GIVEN an org owner on the settings page
        WHEN they submit a slug containing spaces and an apostrophe
        THEN the page re-renders with a field error and the org is unchanged
        """
        response = self.client.post(f'/org/{self.org.slug}/settings/', {
            'name': 'SlugOrg',
            'slug': "CBPR Summer 26' PM",
        })
        self.assertEqual(response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.slug, 'slugorg')
        self.assertContains(response, 'text-danger')

    def test_settings_stores_a_valid_slug_verbatim(self):
        """
        GIVEN an org owner
        WHEN they submit a slug that is already routable
        THEN it is stored exactly as typed
        """
        response = self.client.post(f'/org/{self.org.slug}/settings/', {
            'name': 'SlugOrg',
            'slug': 'cbpr-summer-26',
        })
        self.assertEqual(response.status_code, 302)
        self.org.refresh_from_db()
        self.assertEqual(self.org.slug, 'cbpr-summer-26')

    def test_settings_refuses_duplicate_slug(self):
        """
        GIVEN a second organization already holding a slug
        WHEN the owner submits that same slug
        THEN the form errors and the org keeps its own slug
        """
        _make_org('TakenOrg')
        response = self.client.post(f'/org/{self.org.slug}/settings/', {
            'name': 'SlugOrg',
            'slug': 'takenorg',
        })
        self.assertEqual(response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.slug, 'slugorg')

    def test_model_normalises_an_unroutable_slug(self):
        """
        GIVEN code assigning an unroutable slug outside the settings form
        WHEN the organization is saved
        THEN the stored slug is routable
        """
        org = Organization(name='Shell Written', slug='Mount Vernon Studio Spring 2026')
        org.save()
        org.refresh_from_db()
        self.assertRegex(org.slug, r'^[-.\w]+\Z')
        self.assertEqual(org.slug, 'mount-vernon-studio-spring-2026')

    def test_model_keeps_normalised_slugs_unique(self):
        """
        GIVEN an organization already holding the normalised slug
        WHEN a second one normalises to the same value
        THEN the second gets a distinct slug
        """
        Organization(name='A', slug='Same Name Here').save()
        second = Organization(name='B', slug='Same  Name Here')
        second.save()
        self.assertEqual(Organization.objects.filter(slug='same-name-here').count(), 1)
        self.assertNotEqual(second.slug, 'same-name-here')
        self.assertRegex(second.slug, r'^[-.\w]+\Z')

    def _break_slug(self, value="CBPR Summer 26' PM"):
        """Put the row in the pre-guard broken state a straight UPDATE allows."""
        Organization.objects.filter(pk=self.org.pk).update(slug=value)
        self.org.refresh_from_db()

    def test_editor_is_broken_by_an_unroutable_slug(self):
        """
        GIVEN an organization row holding an unroutable slug
        WHEN its owner opens the editor dashboard
        THEN reversing the account-dropdown URL fails

        Pins the defect itself, so the repair below is measured against a
        reproduction rather than an assumption.
        """
        from django.urls import NoReverseMatch

        self._break_slug()
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        with self.assertRaises(NoReverseMatch):
            self.client.get('/editor/')

    def test_repair_migration_normalises_only_broken_rows(self):
        """
        GIVEN one organization with an unroutable slug and one with a valid slug
        WHEN the repair migration's data function runs
        THEN the broken slug becomes routable, the valid one is untouched, and
             the owner's editor renders again

        Drives the real template at the end rather than asserting on the model,
        because the crash was in `{% url %}` resolution, not in view Python.
        """
        from django.apps import apps as global_apps
        from importlib import import_module

        migration = import_module('survey.migrations.0065_repair_organization_slugs')
        untouched = _make_org('UntouchedOrg')
        self._break_slug()

        migration.repair_slugs(global_apps, None)

        self.org.refresh_from_db()
        untouched.refresh_from_db()
        self.assertEqual(self.org.slug, 'cbpr-summer-26-pm')
        self.assertEqual(untouched.slug, 'untouchedorg')

        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.assertEqual(self.client.get('/editor/').status_code, 200)
