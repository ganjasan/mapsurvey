"""Tests for the `survey-access-control` capability (openspec/specs/survey-access-control/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
import uuid
from survey.models import SurveyHeader, SurveySection, Membership, SurveyCollaborator
from survey.access_control import check_survey_access
from survey.tests.helpers import _make_org


class AccessControlTest(TestCase):
    """Tests for check_survey_access function."""

    def setUp(self):
        self.org = _make_org('AccessOrg')
        self.owner = User.objects.create_user(username='ac_owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')

    def _make_survey(self, status='draft', password=None):
        survey = SurveyHeader.objects.create(
            name=f'access_{status}', organization=self.org,
            status=status, created_by=self.owner,
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=survey, role='owner')
        if password:
            survey.set_password(password)
            survey.save()
        return survey

    def test_draft_returns_404_for_anonymous(self):
        """
        GIVEN a draft survey
        WHEN an anonymous user accesses it
        THEN Http404 is raised
        """
        from django.http import Http404
        survey = self._make_survey('draft')
        request = self.client.get('/').wsgi_request
        with self.assertRaises(Http404):
            check_survey_access(request, survey)

    def test_draft_allowed_for_editor(self):
        """
        GIVEN a draft survey
        WHEN an editor accesses it
        THEN access is allowed (returns None)
        """
        survey = self._make_survey('draft')
        self.client.login(username='ac_owner', password='pass')
        request = self.client.get('/').wsgi_request
        request.user = self.owner
        result = check_survey_access(request, survey)
        self.assertIsNone(result)

    def test_published_no_password_allowed(self):
        """
        GIVEN a published survey without password
        WHEN an anonymous user accesses it
        THEN access is allowed (returns None)
        """
        survey = self._make_survey('published')
        request = self.client.get('/').wsgi_request
        result = check_survey_access(request, survey)
        self.assertIsNone(result)

    def test_published_with_password_redirects(self):
        """
        GIVEN a published survey with password
        WHEN an anonymous user accesses it without session key
        THEN redirect to password page
        """
        survey = self._make_survey('published', password='secret')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('password', response.url)

    def test_closed_shows_closed_page(self):
        """
        GIVEN a closed survey
        WHEN an anonymous user accesses it
        THEN the survey_closed.html template is rendered
        """
        survey = self._make_survey('closed')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer accepting')

    def test_testing_with_valid_token(self):
        """
        GIVEN a testing survey with password
        WHEN a user accesses with valid token
        THEN access is allowed and token is stored in session
        """
        survey = self._make_survey('testing', password='secret')
        response = self.client.get(f'/surveys/{survey.uuid}/?token={survey.test_token}')
        # Should redirect to first section (survey_header behavior), not to password page
        self.assertNotIn('password', response.url if response.status_code == 302 else '')

    def test_testing_without_token_redirects_to_password(self):
        """
        GIVEN a testing survey
        WHEN a user accesses without token or session key
        THEN redirect to password page
        """
        survey = self._make_survey('testing', password='secret')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('password', response.url)


class SurveyNotFoundPageTest(TestCase):
    """A respondent 404 explains itself without saying which case applied."""

    def setUp(self):
        self.org = _make_org('NotFoundOrg')
        self.owner = User.objects.create_user(username='nf_owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')

    def _make_draft(self):
        survey = SurveyHeader.objects.create(
            name='notfound_draft', organization=self.org, status='draft',
            visibility='public', created_by=self.owner,
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=survey, role='owner')
        return survey

    def test_draft_returns_404_with_an_explanation(self):
        """
        GIVEN a draft survey
        WHEN an anonymous visitor requests its URL
        THEN the status is 404 and the body explains what to do
        """
        survey = self._make_draft()
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response.status_code, 404)
        # Typographic apostrophe: 404.html and survey_unavailable.html carried
        # the same sentence with different apostrophes, which bought two catalog
        # entries for one string. They were unified on the typographic one.
        self.assertContains(response, 'isn’t available', status_code=404)

    def test_the_page_does_not_name_the_survey(self):
        """
        GIVEN a draft survey
        WHEN an anonymous visitor requests its URL
        THEN the body contains neither its name nor its UUID
        """
        survey = self._make_draft()
        response = self.client.get(f'/surveys/{survey.uuid}/')
        body = response.content.decode()
        self.assertNotIn(survey.name, body)
        # The UUID does appear, in the navbar's login ?next= link -- it is the
        # path the visitor requested, not a fact about the survey. Anything
        # beyond that echo would be.
        self.assertEqual(body.count(str(survey.uuid)), 1)
        self.assertIn(f'next=/surveys/{survey.uuid}/', body)

    def test_a_draft_and_an_unknown_uuid_are_indistinguishable(self):
        """
        GIVEN a draft survey and a UUID that names no survey
        WHEN both URLs are requested
        THEN the responses match in status, body and noindex header

        A difference here would let anyone test whether a UUID names a real
        survey, which is the enumeration tenant-data-exposure closed.
        """
        survey = self._make_draft()
        other = uuid.uuid4()
        draft = self.client.get(f'/surveys/{survey.uuid}/')
        unknown = self.client.get(f'/surveys/{other}/')

        placeholder = 'UUID'
        draft_body = draft.content.decode().replace(str(survey.uuid), placeholder)
        unknown_body = unknown.content.decode().replace(str(other), placeholder)

        self.assertEqual(draft.status_code, unknown.status_code)
        self.assertEqual(draft_body, unknown_body)
        self.assertEqual(draft['X-Robots-Tag'], unknown['X-Robots-Tag'])

    def test_non_survey_paths_keep_djangos_default_404(self):
        """
        GIVEN a path outside /surveys/
        WHEN it 404s
        THEN the respondent page is not served
        """
        response = self.client.get('/no-such-page-anywhere/')
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "isn't available", status_code=404)
class PublicSurveyListingRemovedTest(TestCase):
    """The public /surveys/ listing exposed every survey in the database."""

    def setUp(self):
        self.org_a = _make_org('ListingOrgA')
        self.org_b = _make_org('ListingOrgB')

        self.private_survey = SurveyHeader.objects.create(
            name='private_one', organization=self.org_a,
            visibility='private', status='published',
        )
        self.public_draft = SurveyHeader.objects.create(
            name='public_draft', organization=self.org_b,
            visibility='public', status='draft',
        )
        self.public_published = SurveyHeader.objects.create(
            name='public_live', organization=self.org_b,
            visibility='public', status='published',
        )

    def test_listing_route_redirects_to_landing(self):
        """
        GIVEN the former public survey listing
        WHEN any visitor requests /surveys/
        THEN the response is a permanent redirect to /
        """
        response = self.client.get('/surveys/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/')

    def test_listing_route_leaks_no_survey_identifiers(self):
        """
        GIVEN surveys belonging to two different organizations
        WHEN an anonymous visitor requests /surveys/
        THEN the response body carries no survey name and no survey UUID
        """
        response = self.client.get('/surveys/')
        body = response.content.decode()
        for survey in (self.private_survey, self.public_draft, self.public_published):
            self.assertNotIn(survey.name, body)
            self.assertNotIn(str(survey.uuid), body)

    def test_private_survey_is_not_discoverable_anonymously(self):
        """
        GIVEN a survey with visibility='private'
        WHEN an anonymous visitor requests the landing page and /surveys/
        THEN neither response names it or exposes its UUID
        """
        for path in ('/', '/surveys/'):
            body = self.client.get(path).content.decode()
            self.assertNotIn(self.private_survey.name, body)
            self.assertNotIn(str(self.private_survey.uuid), body)

    def test_public_draft_is_not_discoverable_anonymously(self):
        """
        GIVEN a survey with visibility='public' but status='draft'
        WHEN an anonymous visitor requests the landing page
        THEN the response does not name it or expose its UUID
        """
        body = self.client.get('/').content.decode()
        self.assertNotIn(self.public_draft.name, body)
        self.assertNotIn(str(self.public_draft.uuid), body)

    def test_sitemap_drops_the_listing_but_keeps_survey_pages(self):
        """
        GIVEN the listing route now redirects
        WHEN /sitemap.xml is fetched
        THEN it has no bare /surveys/ entry but still lists /surveys/<uuid>/
        """
        body = self.client.get('/sitemap.xml').content.decode()
        self.assertNotIn('<loc>http://testserver/surveys/</loc>', body)
        self.assertIn(f'/surveys/{self.public_published.uuid}/', body)


class SurveyExportAuthorizationTest(TestCase):
    """`/surveys/<slug>/download` must check a role, not just authentication."""

    def setUp(self):
        self.org = _make_org('ExportOrg')
        self.other_org = _make_org('ExportOtherOrg')

        self.viewer = User.objects.create_user(username='exp_viewer', password='pass')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')

        self.outsider = User.objects.create_user(username='exp_outsider', password='pass')
        Membership.objects.create(
            user=self.outsider, organization=self.other_org, role='owner',
        )

        self.collaborator = User.objects.create_user(username='exp_collab', password='pass')

        self.survey = SurveyHeader.objects.create(
            name='export_survey', organization=self.org, status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )

    def test_user_with_viewer_role_can_export(self):
        """
        GIVEN a signed-in user whose effective survey role is viewer
        WHEN they request the survey export
        THEN the export is returned
        """
        self.client.login(username='exp_viewer', password='pass')
        response = self.client.get(f'/surveys/{self.survey.uuid}/download')
        self.assertEqual(response.status_code, 200)

    def test_signed_in_user_from_another_org_is_denied(self):
        """
        GIVEN a signed-in user who belongs to a different organization and holds
              no collaborator role on the survey
        WHEN they request the survey export
        THEN they get 404 and no export payload
        """
        self.client.login(username='exp_outsider', password='pass')
        response = self.client.get(f'/surveys/{self.survey.uuid}/download')
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(response.get('Content-Type'), 'application/zip')

    def test_anonymous_visitor_gets_no_export(self):
        """
        GIVEN an anonymous visitor
        WHEN they request the survey export
        THEN they are not served the export
        """
        response = self.client.get(f'/surveys/{self.survey.uuid}/download')
        self.assertNotEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Content-Type'), 'application/zip')

    def test_denial_does_not_disclose_whether_the_survey_exists(self):
        """
        GIVEN a signed-in user with no role on the target organization
        WHEN they request the export for a real survey and for a random UUID
        THEN both responses carry the same status
        """
        self.client.login(username='exp_outsider', password='pass')
        real = self.client.get(f'/surveys/{self.survey.uuid}/download')
        missing = self.client.get(f'/surveys/{uuid.uuid4()}/download')
        self.assertEqual(real.status_code, missing.status_code)
        self.assertEqual(real.status_code, 404)

    def test_collaborator_on_canonical_survey_can_export_all_versions(self):
        """
        GIVEN an org editor -- whose org role grants no baseline survey access --
              holding a collaborator row on the canonical survey only, with no row
              on its archived version headers
        WHEN they export with ?version=all
        THEN the export succeeds, because the role is checked once on the survey
             the URL names rather than per version header
        """
        Membership.objects.create(
            user=self.collaborator, organization=self.org, role='editor',
        )
        SurveyCollaborator.objects.create(
            user=self.collaborator, survey=self.survey, role='viewer',
        )
        archived = SurveyHeader.objects.create(
            name='export_survey', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey, version_number=1,
        )
        SurveySection.objects.create(
            survey_header=archived, name='sec1', code='S1', is_head=True,
        )

        self.client.login(username='exp_collab', password='pass')
        response = self.client.get(f'/surveys/{self.survey.uuid}/download?version=all')
        self.assertEqual(response.status_code, 200)


class PrivatePublishedSurveyStaysLinkAccessibleTest(TestCase):
    """visibility governs discovery, not access -- deliberately preserved."""

    def setUp(self):
        self.org = _make_org('LinkAccessOrg')

    def test_private_published_survey_opens_by_link(self):
        """
        GIVEN a private, published survey with no password
        WHEN an anonymous visitor opens its link
        THEN they are admitted rather than turned away
        """
        survey = SurveyHeader.objects.create(
            name='unlisted_live', organization=self.org,
            visibility='private', status='published',
        )
        SurveySection.objects.create(
            survey_header=survey, name='sec1', code='S1', is_head=True,
        )
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('sec1', response['Location'])

    def test_public_draft_survey_stays_closed(self):
        """
        GIVEN a public survey still in draft
        WHEN an anonymous visitor opens its link
        THEN they get 404
        """
        survey = SurveyHeader.objects.create(
            name='public_draft_link', organization=self.org,
            visibility='public', status='draft',
        )
        SurveySection.objects.create(
            survey_header=survey, name='sec1', code='S1', is_head=True,
        )
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response.status_code, 404)
