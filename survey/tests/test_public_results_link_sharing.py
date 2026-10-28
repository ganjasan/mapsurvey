"""Tests for the `public-results-link-sharing` capability (openspec/specs/public-results-link-sharing/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from survey.models import SurveyHeader, SurveySection, Membership, PublicResultsPage
import uuid as _uuid_mod
from urllib.parse import unquote
from survey.tests.helpers import _make_org


class PublicResultsPreviewFallbackTest(TestCase):
    """A shared preview link must forward to the public page, not trap the visitor.

    Creators share results by copying the editor URL out of the address bar, which
    is this preview endpoint rather than /r/<slug>/. Before the fallback existed,
    every such visitor was bounced to login and — if they registered to get past
    it — met a 404, which manufactured registrations from people who only wanted
    to read results.

    The view no longer uses @survey_permission_required, so the guards that
    decorator provided are re-asserted here one by one.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        self.org = _make_org("PRF Org")
        self.owner = User.objects.create_user(username="prfowner", password="pw12345")
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="prf_survey", organization=self.org, status="published",
        )
        SurveySection.objects.create(survey_header=self.survey, name="s", code="S1", is_head=True)
        self.preview_url = "/editor/surveys/{}/public-results/preview/".format(self.survey.uuid)

    def _publish_page(self, visibility='public'):
        return PublicResultsPage.objects.create(
            survey=self.survey, slug="prf-results", is_published=True, visibility=visibility,
        )

    def test_anonymous_visitor_is_forwarded_to_the_public_page(self):
        """
        GIVEN a published results page
        WHEN an anonymous visitor follows a shared preview link
        THEN they are redirected to /r/<slug>/ rather than to the login page
        """
        self._publish_page()
        r = self.client.get(self.preview_url)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/r/prf-results/")

    def test_outsider_is_forwarded_instead_of_404(self):
        """
        GIVEN a published results page
        WHEN a signed-in user with no role on the survey follows the preview link
        THEN they are redirected to /r/<slug>/ rather than receiving 404
        """
        self._publish_page()
        User.objects.create_user(username="prfoutsider", password="pw12345")
        self.client.login(username="prfoutsider", password="pw12345")
        r = self.client.get(self.preview_url)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/r/prf-results/")

    def test_unlisted_page_still_forwards(self):
        """
        GIVEN a published but unlisted results page
        WHEN an anonymous visitor follows the preview link
        THEN they are still redirected, because an unlisted page is one handed out by link
        """
        self._publish_page(visibility='unlisted')
        r = self.client.get(self.preview_url)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/r/prf-results/")

    def test_unpublished_page_still_denies_the_outsider(self):
        """
        GIVEN a results page that is not published
        WHEN a signed-in outsider requests the preview
        THEN the previous denial stands (404) — there is nowhere public to send them
        """
        PublicResultsPage.objects.create(
            survey=self.survey, slug="prf-draft", is_published=False,
        )
        User.objects.create_user(username="prfoutsider2", password="pw12345")
        self.client.login(username="prfoutsider2", password="pw12345")
        r = self.client.get(self.preview_url)
        self.assertEqual(r.status_code, 404)

    def test_unpublished_page_sends_anonymous_to_login_with_next(self):
        """
        GIVEN a results page that is not published
        WHEN an anonymous visitor requests the preview
        THEN they go to the login page, carrying the requested path as ?next=
        """
        PublicResultsPage.objects.create(
            survey=self.survey, slug="prf-draft2", is_published=False,
        )
        r = self.client.get(self.preview_url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)
        self.assertIn(self.preview_url, unquote(r.url))

    def test_trashed_survey_never_forwards(self):
        """
        GIVEN a trashed survey whose results page is published
        WHEN anyone requests the preview
        THEN it is not reachable — the decorator's trash exclusion still holds
        """
        self._publish_page()
        self.survey.deleted_at = timezone.now()
        self.survey.save(update_fields=['deleted_at'])
        r = self.client.get(self.preview_url)
        self.assertEqual(r.status_code, 404)

    def test_unknown_uuid_is_404(self):
        """
        GIVEN a UUID matching no survey
        WHEN a signed-in user requests the preview for it
        THEN the response is 404
        """
        self.client.login(username="prfowner", password="pw12345")
        r = self.client.get(
            "/editor/surveys/{}/public-results/preview/".format(_uuid_mod.uuid4()))
        self.assertEqual(r.status_code, 404)

    def test_denial_never_creates_a_results_page(self):
        """
        GIVEN a survey with no PublicResultsPage row at all
        WHEN an anonymous visitor requests the preview
        THEN no page row is created — _get_or_create_page must stay off this path
        """
        self.assertEqual(PublicResultsPage.objects.filter(survey=self.survey).count(), 0)
        self.client.get(self.preview_url)
        self.assertEqual(PublicResultsPage.objects.filter(survey=self.survey).count(), 0)

    def test_owner_still_sees_the_preview_when_published(self):
        """
        GIVEN a published results page
        WHEN the owner opens the preview
        THEN it renders (200) and is still same-origin framable
        """
        self._publish_page()
        self.client.login(username="prfowner", password="pw12345")
        r = self.client.get(self.preview_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "noindex")
        self.assertEqual(r.headers.get("X-Frame-Options"), "SAMEORIGIN")

    def test_owner_still_sees_the_preview_when_unpublished(self):
        """
        GIVEN no results page yet
        WHEN the owner opens the preview
        THEN it renders (200) rather than redirecting anywhere
        """
        self.client.login(username="prfowner", password="pw12345")
        r = self.client.get(self.preview_url)
        self.assertEqual(r.status_code, 200)

    def test_viewer_role_is_not_an_editor(self):
        """
        GIVEN a user whose org role is viewer and a published results page
        WHEN they request the preview
        THEN they are forwarded to the public page, not shown the editor preview
        """
        self._publish_page()
        viewer = User.objects.create_user(username="prfviewer", password="pw12345")
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username="prfviewer", password="pw12345")
        r = self.client.get(self.preview_url)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/r/prf-results/")

    @override_settings(PUBLIC_RESULTS_PREVIEW_FALLBACK=False)
    def test_kill_switch_restores_the_old_denial(self):
        """
        GIVEN the fallback disabled and a published results page
        WHEN an anonymous visitor follows the preview link
        THEN they are sent to login, as before the change
        """
        self._publish_page()
        r = self.client.get(self.preview_url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)


class PublicResultsCopyLinkControlTest(TestCase):
    """The editor must offer the public link, so the address bar is not the source."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        self.org = _make_org("Copy Org")
        self.user = User.objects.create_user(username="copyowner", password="pw12345")
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="copy_survey", organization=self.org, status="published",
        )
        SurveySection.objects.create(survey_header=self.survey, name="s", code="S1", is_head=True)
        self.config_url = "/editor/surveys/{}/public-results/".format(self.survey.uuid)
        self.client.login(username="copyowner", password="pw12345")

    def test_copy_control_offered_when_published(self):
        """
        GIVEN a published results page
        WHEN the editor opens the configuration tab
        THEN a control to copy the /r/<slug>/ URL is present
        """
        page = PublicResultsPage.objects.create(
            survey=self.survey, slug="copy-results", is_published=True,
        )
        r = self.client.get(self.config_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "prCopyPublicLink")
        self.assertContains(r, "/r/{}/".format(page.slug))

    def test_no_copy_control_before_publishing(self):
        """
        GIVEN a results page that is not published
        WHEN the editor opens the configuration tab
        THEN no copy-public-link control is offered
        """
        r = self.client.get(self.config_url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'id="prCopyPublicLink"')

    def test_nav_tabs_use_the_disambiguated_labels(self):
        """
        GIVEN the survey editor navigation
        WHEN it renders the three workspace tabs
        THEN they read "Survey", "Responses", "Public results" — not the old
             "Build", "Results", "Publish", which collided with each other and
             with the survey's own "Publish — open for responses" action
        """
        r = self.client.get(self.config_url)
        self.assertEqual(r.status_code, 200)
        # New labels, keyed to their icons so we match the nav tabs specifically.
        self.assertContains(r, 'fa-hammer"></i> Survey')
        self.assertContains(r, 'fa-chart-bar"></i> Responses')
        self.assertContains(r, 'fa-globe"></i> Public results')
        # Old labels must be gone from the nav.
        self.assertNotContains(r, 'fa-hammer"></i> Build')
        self.assertNotContains(r, 'fa-chart-bar"></i> Results')
        self.assertNotContains(r, "Publish <span class=\"badge-beta\">")


class BrandedNotFoundTest(TestCase):
    """The 404 page explains a missing survey, and stays generic elsewhere.

    Django serves survey/templates/404.html only when DEBUG is False, which is
    the test default; these assertions therefore exercise the real handler path.
    """

    def setUp(self):
        self.client = Client()

    def test_missing_results_page_explains_itself(self):
        """
        GIVEN a slug that matches no published results page
        WHEN a visitor opens /r/<slug>/
        THEN the 404 body names the likely causes rather than a bare error
        """
        r = self.client.get("/r/does-not-exist/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "isn", status_code=404)  # "This survey isn’t available"
        self.assertContains(r, "published", status_code=404)

    def test_missing_survey_path_explains_itself(self):
        """
        GIVEN a survey name that does not resolve
        WHEN a visitor opens /surveys/<name>/
        THEN the survey-specific 404 copy is shown
        """
        r = self.client.get("/surveys/no-such-survey-xyz/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "survey", status_code=404)

    def test_non_survey_path_stays_generic(self):
        """
        GIVEN a non-survey path that does not exist
        WHEN a visitor opens it
        THEN the 404 renders without survey-specific wording
        """
        r = self.client.get("/definitely-not-a-real-page-xyz/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "Page not found", status_code=404)
        self.assertNotContains(r, "hasn’t been published", status_code=404)


class EditorLoginRedirectNextTest(TestCase):
    """Anonymous access to editor URLs must not discard where the visitor was going."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org("Next Org")
        self.survey = SurveyHeader.objects.create(
            name="next_survey", organization=self.org, status="published",
        )

    def test_survey_scoped_editor_url_keeps_next(self):
        """
        GIVEN an anonymous visitor
        WHEN they request a survey-scoped editor URL
        THEN the login redirect carries the requested path as ?next=
        """
        url = "/editor/surveys/{}/".format(self.survey.uuid)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)
        self.assertIn(url, unquote(r.url))

    def test_signing_in_returns_to_the_requested_url(self):
        """
        GIVEN an anonymous visitor redirected from an editor URL
        WHEN they log in as a user who may open it
        THEN they land on that URL rather than on the dashboard
        """
        user = User.objects.create_user(username="nextuser", password="pw12345")
        Membership.objects.create(user=user, organization=self.org, role='owner')
        url = "/editor/surveys/{}/".format(self.survey.uuid)
        login_redirect = self.client.get(url).url
        r = self.client.post(
            login_redirect, {"username": "nextuser", "password": "pw12345"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, url)
