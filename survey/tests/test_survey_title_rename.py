"""Tests for the `survey-title-rename` capability (openspec/specs/survey-title-rename/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from survey.models import SurveyHeader, Membership, SurveyCollaborator
from survey.tests.helpers import _make_org


class SurveyInlineRenameTest(TestCase):
    """Renaming a survey from the editor header (openspec: inline-rename-survey-title)."""

    def setUp(self):
        self.org = _make_org('RenameOrg')
        self.owner = User.objects.create_user('renameowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.collaborator = User.objects.create_user('renameeditor', password='pass')
        Membership.objects.create(user=self.collaborator, organization=self.org, role='editor')
        self.survey = SurveyHeader.objects.create(
            name='demo_city_feedback', organization=self.org,
            created_by=self.owner, status='published',
        )
        SurveyCollaborator.objects.create(user=self.collaborator, survey=self.survey, role='editor')
        self.url = reverse('editor_survey_rename', args=[self.survey.uuid])

    def _login(self, user):
        self.client.login(username=user.username, password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    # ── the endpoint ────────────────────────────────────────────────────────

    def test_owner_renames_survey(self):
        """
        GIVEN a survey owner
        WHEN they POST a new name to the rename endpoint
        THEN the survey is renamed and the saved name comes back in the response
        """
        self._login(self.owner)
        resp = self.client.post(self.url, {'name': 'City feedback 2026'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'ok': True, 'name': 'City feedback 2026'})
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.name, 'City feedback 2026')

    def test_rename_writes_nothing_but_the_name(self):
        """
        GIVEN a survey with non-default languages, basemaps, visibility and redirect URL
        WHEN it is renamed
        THEN every one of those settings is unchanged

        The reason this endpoint exists instead of reusing the settings form:
        a one-field POST bound to SurveyHeaderForm would bind the absent
        fields and could wipe them.
        """
        self.survey.available_languages = ['en', 'de']
        self.survey.basemaps = ['streets', 'satellite']
        self.survey.default_basemap = 'satellite'
        self.survey.visibility = 'public'
        self.survey.redirect_url = 'https://example.org/thanks/'
        self.survey.save()
        self._login(self.owner)

        resp = self.client.post(self.url, {'name': 'Renamed'})

        self.assertEqual(resp.status_code, 200)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.name, 'Renamed')
        self.assertEqual(self.survey.available_languages, ['en', 'de'])
        self.assertEqual(self.survey.basemaps, ['streets', 'satellite'])
        self.assertEqual(self.survey.default_basemap, 'satellite')
        self.assertEqual(self.survey.visibility, 'public')
        self.assertEqual(self.survey.redirect_url, 'https://example.org/thanks/')

    def test_non_owner_cannot_rename(self):
        """
        GIVEN a collaborator with the 'editor' role, who may not edit survey settings
        WHEN they POST to the rename endpoint
        THEN the request is refused and the name is unchanged
        """
        self._login(self.collaborator)
        resp = self.client.post(self.url, {'name': 'Not allowed'})
        self.assertEqual(resp.status_code, 403)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.name, 'demo_city_feedback')

    def test_anonymous_cannot_rename(self):
        """
        GIVEN nobody logged in
        WHEN a rename is POSTed
        THEN it is redirected to login and the name is unchanged
        """
        resp = self.client.post(self.url, {'name': 'Not allowed'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp['Location'])
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.name, 'demo_city_feedback')

    def test_get_is_not_allowed(self):
        """
        GIVEN the rename endpoint
        WHEN it is fetched with GET
        THEN it refuses — renaming is a write, never a navigation
        """
        self._login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_over_length_name_is_rejected_not_truncated(self):
        """
        GIVEN a name longer than the field's maximum
        WHEN it is submitted
        THEN the request is rejected with a field error and the stored name is unchanged

        The silent truncation this replaces published a survey named
        "To what extent does the presence of Gatwick A" in production.
        """
        max_length = SurveyHeader._meta.get_field('name').max_length
        self._login(self.owner)

        resp = self.client.post(self.url, {'name': 'x' * (max_length + 1)})

        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertFalse(body['ok'])
        self.assertIn('name', body['errors'])
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.name, 'demo_city_feedback')

    def test_name_at_the_limit_is_accepted(self):
        """
        GIVEN a name of exactly the maximum length
        WHEN it is submitted
        THEN it is saved whole
        """
        max_length = SurveyHeader._meta.get_field('name').max_length
        self._login(self.owner)
        resp = self.client.post(self.url, {'name': 'y' * max_length})
        self.assertEqual(resp.status_code, 200)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.name, 'y' * max_length)

    def test_blank_name_is_rejected(self):
        """
        GIVEN a name that is blank or only whitespace
        WHEN it is submitted
        THEN it is rejected and the stored name is unchanged
        """
        self._login(self.owner)
        for value in ('', '   '):
            with self.subTest(value=repr(value)):
                resp = self.client.post(self.url, {'name': value})
                self.assertEqual(resp.status_code, 400)
                self.assertIn('name', resp.json()['errors'])
                self.survey.refresh_from_db()
                self.assertEqual(self.survey.name, 'demo_city_feedback')

    def test_name_without_letters_or_digits_is_rejected(self):
        """
        GIVEN a name of punctuation only
        WHEN it is submitted
        THEN the model's own validator rejects it, exactly as in Survey settings
        """
        self._login(self.owner)
        resp = self.client.post(self.url, {'name': '---'})
        self.assertEqual(resp.status_code, 400)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.name, 'demo_city_feedback')

    def test_name_with_spaces_and_cyrillic_is_accepted(self):
        """
        GIVEN a name with spaces and non-Latin characters
        WHEN it is submitted
        THEN it is saved — the field is a title, not a URL slug
        """
        self._login(self.owner)
        resp = self.client.post(self.url, {'name': 'Опрос о парках'})
        self.assertEqual(resp.status_code, 200)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.name, 'Опрос о парках')

    def test_draft_copy_cannot_be_renamed(self):
        """
        GIVEN the draft copy of a published survey
        WHEN a rename is POSTed for it
        THEN it is refused and both surveys keep their names

        A draft's header names the survey it is a draft OF; renaming happens
        on the canonical header and reaches respondents through publication.
        """
        draft = SurveyHeader.objects.create(
            name='draft_copy', organization=self.org, created_by=self.owner,
            status='draft', published_version=self.survey,
        )
        self._login(self.owner)

        resp = self.client.post(
            reverse('editor_survey_rename', args=[draft.uuid]), {'name': 'Renamed draft'})

        self.assertEqual(resp.status_code, 400)
        draft.refresh_from_db()
        self.survey.refresh_from_db()
        self.assertEqual(draft.name, 'draft_copy')
        self.assertEqual(self.survey.name, 'demo_city_feedback')

    # ── the affordance in the markup ────────────────────────────────────────

    def _editor_pages(self):
        return [
            reverse('editor_survey_detail', args=[self.survey.uuid]),
            reverse('editor_survey_settings', args=[self.survey.uuid]),
            reverse('editor_survey_share', args=[self.survey.uuid]),
            reverse('editor_survey_analytics', args=[self.survey.uuid]),
            reverse('editor_survey_public_results', args=[self.survey.uuid]),
        ]

    def test_every_editor_page_offers_the_rename_affordance_to_an_owner(self):
        """
        GIVEN a survey owner
        WHEN they open each editor page that shows the survey name
        THEN every one of them renders the editable title, not a dead span

        The point of the shared partial: the affordance cannot be present on
        one editor page and missing on the next.
        """
        self._login(self.owner)
        for url in self._editor_pages():
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                html = resp.content.decode()
                # data-rename-url, not the class name: the class also appears
                # in the stylesheet, where it proves nothing about the markup.
                self.assertIn(
                    'data-rename-url="%s"' % reverse('editor_survey_rename', args=[self.survey.uuid]),
                    html)
                self.assertIn(self.survey.name, html)

    def test_non_owner_pages_carry_no_editable_control(self):
        """
        GIVEN a collaborator who may not rename
        WHEN they open an editor page
        THEN the name is plain text and the markup holds no editable control

        Absent, not merely hidden: nothing to re-enable from the console.
        """
        self._login(self.collaborator)
        resp = self.client.get(reverse('editor_survey_detail', args=[self.survey.uuid]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn(self.survey.name, html)
        self.assertNotIn('data-rename-url', html)
        self.assertNotIn('/rename/', html)

    def test_draft_copy_header_is_not_editable(self):
        """
        GIVEN the draft copy of a published survey
        WHEN its owner opens the editor
        THEN the header names the published survey and offers no rename affordance
        """
        draft = SurveyHeader.objects.create(
            name='draft_copy', organization=self.org, created_by=self.owner,
            status='draft', published_version=self.survey,
        )
        self._login(self.owner)

        resp = self.client.get(reverse('editor_survey_detail', args=[draft.uuid]))

        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn(self.survey.name, html)
        self.assertNotIn('data-rename-url', html)

    def test_settings_field_shows_the_same_limit(self):
        """
        GIVEN the Survey settings page
        WHEN an owner opens it
        THEN the name field carries the field's maxlength and the counter marker,
             so both rename surfaces tell the creator the same thing
        """
        self._login(self.owner)
        resp = self.client.get(reverse('editor_survey_settings', args=[self.survey.uuid]))
        html = resp.content.decode()
        max_length = SurveyHeader._meta.get_field('name').max_length
        self.assertRegex(html, r'name="name"[^>]*maxlength="%d"' % max_length)
        self.assertIn('data-char-counter', html)
