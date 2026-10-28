"""Tests for the `survey-thanks-page` capability (openspec/specs/survey-thanks-page/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from io import BytesIO
import contextlib
import json
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, Membership, PublicResultsPage
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from io import StringIO
from survey.tests.helpers import _make_org


class SurveyThanksPageTest(TestCase):
    """Tests for the built-in survey thanks page."""

    def setUp(self):
        org = Organization.objects.create(name="Thanks Org")
        self.survey = SurveyHeader.objects.create(
            name="thanks_survey",
            organization=org,
            redirect_url="#",
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="only_section",
            title="Only Section",
            code="S1",
            is_head=True,
            start_map_postion=Point(30.0, 60.0),
            start_map_zoom=14,
        )
        self.question = Question.objects.create(
            survey_section=self.section,
            name="Name",
            input_type="text_line",
            order_number=1,
        )

        self.custom_survey = SurveyHeader.objects.create(
            name="custom_redirect_survey",
            organization=org,
            redirect_url="https://example.com/done",
            status='published',
        )
        self.custom_section = SurveySection.objects.create(
            survey_header=self.custom_survey,
            name="only_section",
            title="Only Section",
            code="S1",
            is_head=True,
            start_map_postion=Point(30.0, 60.0),
            start_map_zoom=14,
        )
        Question.objects.create(
            survey_section=self.custom_section,
            name="Name",
            input_type="text_line",
            order_number=1,
        )

    def test_thanks_page_returns_200_and_clears_session(self):
        """
        GIVEN a survey with a completed session
        WHEN the user visits the thanks page
        THEN status is 200 and session keys are cleared
        """
        # Create a session by visiting the section
        self.client.get('/surveys/thanks_survey/only_section/')
        self.assertIn('survey_session_id', self.client.session)

        response = self.client.get('/surveys/thanks_survey/thanks/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('survey_session_id', self.client.session)
        self.assertNotIn('survey_language', self.client.session)

    def test_thanks_page_nonexistent_survey_returns_404(self):
        """
        GIVEN no survey with the given name
        WHEN the user visits the thanks page
        THEN the server returns 404
        """
        response = self.client.get('/surveys/nonexistent/thanks/')
        self.assertEqual(response.status_code, 404)

    def test_last_section_post_redirects_to_thanks_page(self):
        """
        GIVEN a single-section survey with default redirect_url="#"
        WHEN the user submits the last section
        THEN the response redirects to the thanks page (using UUID)
        """
        self.client.get('/surveys/thanks_survey/only_section/')
        response = self.client.post('/surveys/thanks_survey/only_section/', {
            self.question.code: 'Alice',
        })
        self.assertRedirects(response, f'/surveys/{self.survey.uuid}/thanks/', fetch_redirect_response=False)

    def test_last_section_post_with_custom_redirect(self):
        """
        GIVEN a single-section survey with custom redirect_url
        WHEN the user submits the last section
        THEN the response redirects to the custom URL
        """
        self.client.get('/surveys/custom_redirect_survey/only_section/')
        response = self.client.post('/surveys/custom_redirect_survey/only_section/', {
            self.custom_section.questions()[0].code: 'Bob',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://example.com/done')

    def test_thanks_page_empty_thanks_html_shows_default(self):
        """
        GIVEN a survey with empty thanks_html
        WHEN the user visits the thanks page
        THEN the default message block is displayed and share URL uses UUID
        """
        response = self.client.get('/surveys/thanks_survey/thanks/')
        # Share URL in JS uses UUID-based survey URL
        self.assertContains(response, f'/surveys/{self.survey.uuid}/')

    def test_thanks_page_multilingual_renders_correct_language(self):
        """
        GIVEN a survey with multilingual thanks_html
        WHEN the user completed the survey in Russian
        THEN the thanks page renders the Russian HTML
        """
        self.survey.thanks_html = {
            'en': '<h1>Thanks!</h1>',
            'ru': '<h1>Спасибо!</h1>',
        }
        self.survey.save()

        session = self.client.session
        session['survey_language'] = 'ru'
        session.save()

        response = self.client.get('/surveys/thanks_survey/thanks/')
        self.assertContains(response, '<h1>Спасибо!</h1>')
        self.assertNotContains(response, 'Thanks!')

    def test_thanks_page_falls_back_to_en(self):
        """
        GIVEN a survey with thanks_html that has only "en" key
        WHEN the user completed the survey in French
        THEN the thanks page falls back to English content
        """
        self.survey.thanks_html = {'en': '<p>Thank you very much!</p>'}
        self.survey.save()

        session = self.client.session
        session['survey_language'] = 'fr'
        session.save()

        response = self.client.get('/surveys/thanks_survey/thanks/')
        self.assertContains(response, 'Thank you very much!')

    def test_thanks_page_plain_string_renders_directly(self):
        """
        GIVEN a survey with thanks_html as a plain string
        WHEN the user visits the thanks page
        THEN the string is rendered directly
        """
        self.survey.thanks_html = '<h2>Merci!</h2>'
        self.survey.save()

        response = self.client.get('/surveys/thanks_survey/thanks/')
        self.assertContains(response, '<h2>Merci!</h2>')


class ThanksPageEditorTest(TestCase):
    """WYSIWYG thanks-page editor panel: rendering, per-language sanitized save."""

    def setUp(self):
        self.org = _make_org("ThanksOrg")
        self.user = User.objects.create_user(username="thx_owner", password="pass")
        Membership.objects.create(user=self.user, organization=self.org, role="owner")
        self.survey = SurveyHeader.objects.create(
            name="thx_survey", organization=self.org, status="published",
            available_languages=["en", "de"],
        )
        SurveySection.objects.create(name="s1", survey_header=self.survey, is_head=True)
        self.client.login(username="thx_owner", password="pass")

    def test_thanks_panel_renders_editor(self):
        """
        GIVEN an owner
        WHEN they GET the thanks panel
        THEN the WYSIWYG editor and the mandatory branding preview render
        """
        r = self.client.get(f"/editor/surveys/{self.survey.uuid}/thanks-panel/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "thanks-quill")
        self.assertContains(r, "Thanks page")
        self.assertContains(r, "Made with")

    def test_panel_thanks_loads_editor(self):
        """
        GIVEN an owner
        WHEN they open the survey with ?panel=thanks
        THEN the pinned Thanks entry is active and the thanks panel is wired to load
        """
        r = self.client.get(f"/editor/surveys/{self.survey.uuid}/?panel=thanks")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "thanksPinnedItem")
        self.assertContains(r, "thanks-panel")
        # the live-preview iframe points at the thanks preview
        self.assertContains(r, "thanks-preview")

    def test_thanks_preview_renders_saved_content(self):
        """
        GIVEN saved thanks content
        WHEN the editor thanks-preview is rendered
        THEN it shows the content in the requested language plus the branding
        """
        self.survey.thanks_html = {"en": "<h2>Cheers</h2>", "de": "<h2>Danke</h2>"}
        self.survey.save(update_fields=["thanks_html"])
        r = self.client.get(f"/editor/surveys/{self.survey.uuid}/thanks-preview/?lang=de")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Danke")
        self.assertContains(r, "Made with")

    def test_save_stores_per_language_and_sanitizes(self):
        """
        GIVEN an owner editing a two-language survey
        WHEN they save thanks content with disallowed markup — the primary
             language through the panel, the other through the Translations tab
             (the panel's other-language tabs are links there since change
             translation-table; a posted thanks_de is ignored)
        THEN each language's HTML is stored sanitized (scripts/handlers stripped)
        """
        from survey import translation_table as tt
        from survey.services.context import Actor

        r = self.client.post(
            f"/editor/surveys/{self.survey.uuid}/thanks-panel/",
            {"thanks_en": "<h2>Thanks</h2><script>bad()</script>",
             "thanks_de": '<p>Posted, not written</p>'},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200)
        self.assertJSONEqual(r.content, {"ok": True})
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.thanks_html["en"], "<h2>Thanks</h2>")
        self.assertNotIn("de", self.survey.thanks_html)
        tt.apply(Actor(user=self.user), self.survey, "de",
                 {tt.THANKS_KEY: '<p>Danke <a href="/x" onclick="y()">Link</a></p>'})
        self.survey.refresh_from_db()
        th = self.survey.thanks_html
        self.assertNotIn("onclick", th["de"])
        self.assertIn('rel="noopener noreferrer"', th["de"])

    def test_plain_post_redirects(self):
        """
        GIVEN a non-XHR submit
        WHEN thanks content is saved
        THEN the response redirects back to the thanks panel
        """
        r = self.client.post(f"/editor/surveys/{self.survey.uuid}/thanks-panel/", {"thanks_en": "<p>Ty</p>"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("panel=thanks", r.url)

    def test_settings_panel_has_no_thanks_field(self):
        """
        GIVEN the thanks page moved to its own editor
        WHEN the Survey settings panel is rendered
        THEN it no longer contains the raw thanks_html field
        """
        r = self.client.get(f"/editor/surveys/{self.survey.uuid}/?panel=settings")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "id_thanks_html")

    def test_sanitize_helper(self):
        """
        GIVEN raw WYSIWYG HTML
        WHEN sanitize_thanks_html runs
        THEN allow-listed tags stay and scripts/event-handlers are stripped
        """
        from survey.views import sanitize_thanks_html
        out = sanitize_thanks_html('<h1>H</h1><script>x</script><a href="/a" onclick="e">L</a>')
        self.assertIn("<h1>H</h1>", out)
        self.assertNotIn("<script>", out)
        self.assertNotIn("onclick", out)

    def test_sanitize_keeps_media_strips_untrusted(self):
        """
        GIVEN thanks HTML with alignment, an image, and video iframes
        WHEN sanitized
        THEN centre alignment, image, and a trusted-host video survive while a
             non-align style and an untrusted iframe src are stripped
        """
        from survey.views import sanitize_thanks_html
        out = sanitize_thanks_html(
            '<p style="text-align:center;color:red">c</p>'
            '<img src="/mediafiles/a.png" alt="x" onerror="e">'
            '<iframe src="https://www.youtube.com/embed/ID"></iframe>'
            '<iframe src="https://evil.example/x"></iframe>'
        )
        self.assertIn("text-align:center", out)
        self.assertNotIn("color", out)
        self.assertIn("/mediafiles/a.png", out)
        self.assertNotIn("onerror", out)
        self.assertIn("youtube.com/embed/ID", out)
        self.assertNotIn("evil.example", out)

    def test_thanks_image_upload(self):
        """
        GIVEN an owner
        WHEN they upload a PNG to the thanks-image endpoint
        THEN it returns a URL; a non-image is rejected with 400
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        png = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
               b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00'
               b'\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
        r = self.client.post(
            f"/editor/surveys/{self.survey.uuid}/thanks-image/",
            {"image": SimpleUploadedFile("a.png", png, content_type="image/png")},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("url", r.json())
        bad = self.client.post(
            f"/editor/surveys/{self.survey.uuid}/thanks-image/",
            {"image": SimpleUploadedFile("a.txt", b"hi", content_type="text/plain")},
        )
        self.assertEqual(bad.status_code, 400)

    def test_results_button_on_thanks_preview_toggle(self):
        """
        GIVEN a published results page
        WHEN show_on_thanks is on
        THEN the thanks page shows a "See the results" button linking to it;
             turning it off hides the button
        """
        from survey.models import PublicResultsPage
        p = PublicResultsPage.objects.create(
            survey=self.survey, slug="thx-res", is_published=True, show_on_thanks=True,
        )
        r = self.client.get(f"/editor/surveys/{self.survey.uuid}/thanks-preview/")
        self.assertContains(r, "See the results")
        self.assertContains(r, "/r/thx-res/")
        p.show_on_thanks = False
        p.save()
        r2 = self.client.get(f"/editor/surveys/{self.survey.uuid}/thanks-preview/")
        self.assertNotContains(r2, "See the results")

    def test_thanks_panel_saves_results_toggle(self):
        """
        GIVEN a results page and the thanks editor's results toggle
        WHEN the thanks form is saved with the toggle marker
        THEN show_on_thanks follows the checkbox; without the marker (stale form)
             it is left unchanged
        """
        from survey.models import PublicResultsPage
        p = PublicResultsPage.objects.create(
            survey=self.survey, slug="thx-res2", is_published=True, show_on_thanks=True,
        )
        url = f"/editor/surveys/{self.survey.uuid}/thanks-panel/"
        # marker present, checkbox unchecked (absent) -> off
        self.client.post(url, {"thanks_en": "<p>x</p>", "has_results_toggle": "1"},
                         HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        p.refresh_from_db(); self.assertFalse(p.show_on_thanks)
        # marker present, checkbox on -> on
        self.client.post(url, {"thanks_en": "<p>x</p>", "has_results_toggle": "1", "show_on_thanks": "on"},
                         HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        p.refresh_from_db(); self.assertTrue(p.show_on_thanks)
        # no marker (stale form) -> unchanged
        self.client.post(url, {"thanks_en": "<p>x</p>"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        p.refresh_from_db(); self.assertTrue(p.show_on_thanks)


# =============================================================================
# Redirect after the last page (change fix-redirect-url-validation, #271)
# =============================================================================

class CleanRedirectUrlTest(SimpleTestCase):
    """`survey.redirects.clean_redirect_url`: "#" or a valid http(s) URL."""

    def test_unusable_values_mean_the_thanks_page(self):
        """
        GIVEN values creators actually stored: hashtags, messages, relative paths
        WHEN they are cleaned
        THEN each one becomes "#" (the built-in thank-you page)
        """
        from survey.redirects import clean_redirect_url
        for value in ['#', '', None, '   ', '#projectname', '#thanks', '#/bedankt/',
                      '/obrigada', '-', 'Test1', 'Wat is je naam', 'project#',
                      'Lieliska vērība!', 'javascript:alert(1)', 'ftp://example.org/x']:
            with self.subTest(value=value):
                self.assertEqual(clean_redirect_url(value), '#')

    def test_a_url_typed_after_the_default_anchor_is_kept(self):
        """
        GIVEN a URL typed after the pre-filled "#"
        WHEN it is cleaned
        THEN the "#" is dropped and the link the creator meant survives
        """
        from survey.redirects import clean_redirect_url
        self.assertEqual(clean_redirect_url('#https://www.example.org/about'),
                         'https://www.example.org/about')
        self.assertEqual(clean_redirect_url('##http://example.org'), 'http://example.org')

    def test_scheme_case_and_bare_www_are_fixed(self):
        """
        GIVEN "Https://…" and "www.…"
        WHEN they are cleaned
        THEN the scheme is lowercased and a bare www address gets https://
        """
        from survey.redirects import clean_redirect_url
        self.assertEqual(clean_redirect_url('Https://example.org/A'), 'https://example.org/A')
        self.assertEqual(clean_redirect_url('www.example.org/x'), 'https://www.example.org/x')

    def test_a_valid_url_is_unchanged(self):
        """
        GIVEN a valid absolute https URL
        WHEN it is cleaned
        THEN it comes back unchanged
        """
        from survey.redirects import clean_redirect_url
        url = 'https://docs.example.org/forms/d/e/abc/viewform?usp=sf_link'
        self.assertEqual(clean_redirect_url(url), url)

    def test_too_long_after_tidying_means_the_thanks_page(self):
        """
        GIVEN a 247-character www address (250 once https:// is added would overflow)
        WHEN it is cleaned
        THEN it becomes "#" rather than a value the column cannot hold
        """
        from survey.redirects import clean_redirect_url
        value = 'www.example.org/' + 'a' * 231
        self.assertEqual(len(value), 247)
        self.assertEqual(clean_redirect_url(value), '#')


class FinishRedirectTest(TestCase):
    """Where the last section sends a respondent, whatever redirect_url holds."""

    def _survey(self, name, redirect_url):
        org = Organization.objects.create(name=f'{name} org')
        survey = SurveyHeader.objects.create(
            name=name, organization=org, redirect_url=redirect_url, status='published')
        section = SurveySection.objects.create(
            survey_header=survey, name='only_section', title='Only', code='S1', is_head=True,
            start_map_postion=Point(30.0, 60.0), start_map_zoom=14)
        question = Question.objects.create(
            survey_section=section, name='Name', input_type='text_line', order_number=1)
        return survey, question

    def _finish(self, survey, question, htmx=False):
        base = f'/surveys/{survey.name}/only_section/'
        self.client.get(base)
        extra = {'HTTP_HX_REQUEST': 'true'} if htmx else {}
        return self.client.post(base, {question.code: 'Alice'}, **extra)

    def test_an_anchor_sends_the_respondent_to_the_thanks_page(self):
        """
        GIVEN a survey whose redirect_url is a project hashtag
        WHEN the respondent submits the last section
        THEN they are redirected to the thanks page, not to "#projectname"
        """
        survey, question = self._survey('anchor_survey', '#projectname')
        response = self._finish(survey, question)
        self.assertRedirects(response, f'/surveys/{survey.uuid}/thanks/', fetch_redirect_response=False)

    def test_an_anchor_over_htmx_sends_the_respondent_to_the_thanks_page(self):
        """
        GIVEN a survey whose redirect_url is a project hashtag
        WHEN the respondent submits the last section through HTMX
        THEN HX-Redirect names the thanks page
        """
        survey, question = self._survey('htmx_anchor_survey', '#projectname')
        response = self._finish(survey, question, htmx=True)
        self.assertEqual(response['HX-Redirect'], f'/surveys/{survey.uuid}/thanks/')

    def test_a_link_typed_after_the_anchor_is_followed(self):
        """
        GIVEN a survey whose redirect_url is "#https://example.com" (typed after the old "#")
        WHEN the respondent submits the last section through HTMX
        THEN HX-Redirect is the link the creator meant
        """
        survey, question = self._survey('htmx_salvaged_survey', '#https://example.com')
        response = self._finish(survey, question, htmx=True)
        self.assertEqual(response['HX-Redirect'], 'https://example.com')

    def test_relative_paths_and_text_send_the_respondent_to_the_thanks_page(self):
        """
        GIVEN surveys whose redirect_url is "/obrigada" or "-"
        WHEN the respondent submits the last section
        THEN they are redirected to the thanks page instead of a 404
        """
        for i, value in enumerate(['/obrigada', '-']):
            with self.subTest(value=value):
                survey, question = self._survey(f'relative_survey_{i}', value)
                response = self._finish(survey, question)
                self.assertRedirects(response, f'/surveys/{survey.uuid}/thanks/',
                                     fetch_redirect_response=False)

    def test_a_valid_link_still_wins(self):
        """
        GIVEN a survey whose redirect_url is a valid https URL
        WHEN the respondent submits the last section, plain and over HTMX
        THEN they are sent to that URL
        """
        survey, question = self._survey('link_survey', 'https://example.com/done')
        self.assertEqual(self._finish(survey, question)['Location'], 'https://example.com/done')
        self.assertEqual(self._finish(survey, question, htmx=True)['HX-Redirect'],
                         'https://example.com/done')


class SettingsFinishActionTest(TestCase):
    """Survey settings: "After the last page" choice and the address check."""

    def setUp(self):
        self.user = User.objects.create_user(username='finish_owner', password='pass')
        self.org = _make_org('FinishOrg')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name='finish_survey', organization=self.org)
        self.client.login(username='finish_owner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.url = reverse('editor_survey_settings_panel', args=[self.survey.uuid])

    def _save(self, **fields):
        data = {'name': 'finish_survey', 'visibility': 'private'}
        data.update(fields)
        return self.client.post(self.url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_default_survey_shows_the_thank_you_option(self):
        """
        GIVEN a survey with the default redirect_url "#"
        WHEN the owner opens Survey settings
        THEN "Show the thank-you page" is checked and the address box is hidden and empty
        """
        html = self.client.get(self.url).content.decode()
        self.assertRegex(html, r'<input[^>]*value="thanks"[^>]*checked')
        self.assertRegex(html, r'data-finish-link\s+hidden')
        self.assertNotRegex(html, r'name="redirect_url"[^>]*value="#"')

    def test_a_stored_link_shows_the_address_option(self):
        """
        GIVEN a survey whose redirect_url is a valid link
        WHEN the owner opens Survey settings
        THEN "Open a web address" is checked and the box holds the link
        """
        self.survey.redirect_url = 'https://example.com/x'
        self.survey.save()
        html = self.client.get(self.url).content.decode()
        self.assertRegex(html, r'<input[^>]*value="link"[^>]*checked')
        self.assertIn('value="https://example.com/x"', html)
        self.assertNotRegex(html, r'data-finish-link\s+hidden')

    def test_a_stored_broken_value_shows_the_thank_you_option(self):
        """
        GIVEN a survey still holding "#projectname"
        WHEN the owner opens Survey settings
        THEN it reads as the thank-you page, which is where respondents go
        """
        self.survey.redirect_url = '#projectname'
        self.survey.save()
        html = self.client.get(self.url).content.decode()
        self.assertRegex(html, r'<input[^>]*value="thanks"[^>]*checked')
        self.assertNotIn('#projectname', html)

    def test_a_valid_address_is_saved(self):
        """
        GIVEN the owner chose "Open a web address"
        WHEN they enter a valid URL and the panel autosaves
        THEN redirect_url holds that URL
        """
        response = self._save(finish_action='link', redirect_url='https://www.example.org/project')
        self.assertEqual(response.status_code, 200)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.redirect_url, 'https://www.example.org/project')

    def test_typing_slips_are_fixed_on_save(self):
        """
        GIVEN "#https://…" and "www.…" typed into the address box
        WHEN the panel autosaves
        THEN the stored value is the clean https URL
        """
        for typed, stored in [('#https://www.example.org/p', 'https://www.example.org/p'),
                              ('www.example.org/p', 'https://www.example.org/p')]:
            with self.subTest(typed=typed):
                self.assertEqual(self._save(finish_action='link', redirect_url=typed).status_code, 200)
                self.survey.refresh_from_db()
                self.assertEqual(self.survey.redirect_url, stored)

    def test_an_invalid_address_is_refused(self):
        """
        GIVEN a hashtag, a relative path or a message typed into the address box
        WHEN the panel autosaves
        THEN the response is 400 with an error on redirect_url and nothing changes
        """
        self.survey.redirect_url = 'https://example.org/keep'
        self.survey.save()
        for typed in ['#projectname', '/thanks', 'Thank you!']:
            with self.subTest(typed=typed):
                response = self._save(finish_action='link', redirect_url=typed)
                self.assertEqual(response.status_code, 400)
                self.assertIn('redirect_url', response.json()['errors'])
                self.survey.refresh_from_db()
                self.assertEqual(self.survey.redirect_url, 'https://example.org/keep')

    def test_choosing_the_thank_you_page_clears_the_address(self):
        """
        GIVEN a survey with a link
        WHEN the owner switches to "Show the thank-you page" (the box still holds the link)
        THEN redirect_url becomes "#"
        """
        self.survey.redirect_url = 'https://example.org/keep'
        self.survey.save()
        self.assertEqual(self._save(finish_action='thanks', redirect_url='https://example.org/keep').status_code, 200)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.redirect_url, '#')

    def test_an_empty_address_saves_as_the_thank_you_page(self):
        """
        GIVEN the owner just picked "Open a web address" and has typed nothing yet
        WHEN the panel autosaves on that change
        THEN the save succeeds with redirect_url "#" and no error
        """
        response = self._save(finish_action='link', redirect_url='')
        self.assertEqual(response.status_code, 200)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.redirect_url, '#')

    def test_a_post_without_the_choice_still_works(self):
        """
        GIVEN an older client that posts redirect_url without finish_action
        WHEN it saves a valid link, then "#"
        THEN both saves succeed as before
        """
        self.assertEqual(self._save(redirect_url='https://example.org/a').status_code, 200)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.redirect_url, 'https://example.org/a')
        self.assertEqual(self._save(redirect_url='#').status_code, 200)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.redirect_url, '#')


class RedirectUrlImportTest(TestCase):
    """ZIP import (also the AI-generation path) normalises redirect_url."""

    def _import_with(self, redirect_url):
        org = Organization.objects.create(name='ImportRedirectOrg')
        survey = SurveyHeader.objects.create(name='import_redirect_src', organization=org)
        output = BytesIO()
        export_survey_to_zip(survey, output, mode='structure')
        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            data = json.loads(zf.read('survey.json'))
        data['survey']['name'] = 'import_redirect_dst'
        data['survey']['redirect_url'] = redirect_url
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            zf.writestr('survey.json', json.dumps(data))
        buffer.seek(0)
        imported, _warnings = import_survey_from_zip(buffer)
        return imported

    def test_a_hashtag_is_imported_as_the_thanks_page(self):
        """
        GIVEN an archive with "redirect_url": "#thanks"
        WHEN it is imported
        THEN the survey's redirect_url is "#"
        """
        self.assertEqual(self._import_with('#thanks').redirect_url, '#')

    def test_an_anchored_link_is_imported_without_the_anchor(self):
        """
        GIVEN an archive with "redirect_url": "#https://example.org"
        WHEN it is imported
        THEN the survey's redirect_url is "https://example.org"
        """
        self.assertEqual(self._import_with('#https://example.org').redirect_url, 'https://example.org')


class NormalizeRedirectUrlMigrationTest(TestCase):
    """Migration 0094 rewrites stored redirect_url values."""

    def test_forward_mapping(self):
        """
        GIVEN surveys holding the shapes found in production
        WHEN the migration's forward function runs
        THEN links behind "#" are kept, schemes lowercased, the rest becomes "#"
        """
        import importlib
        from django.apps import apps as django_apps
        migration = importlib.import_module('survey.migrations.0094_normalize_redirect_url')
        org = Organization.objects.create(name='MigrationRedirectOrg')
        cases = {
            '#https://www.example.org/about': 'https://www.example.org/about',
            'Https://Project-AK.example.org': 'https://Project-AK.example.org',
            '#tag': '#',
            '/obrigada': '#',
            '-': '#',
            'Wat is je naam': '#',
            '#': '#',
            'https://ok.example.org/x': 'https://ok.example.org/x',
        }
        surveys = {
            old: SurveyHeader.objects.create(name=f'mig_{i}', organization=org, redirect_url=old)
            for i, old in enumerate(cases)
        }
        with contextlib.redirect_stdout(StringIO()):
            migration.forwards(django_apps, None)
        for old, expected in cases.items():
            with self.subTest(old=old):
                surveys[old].refresh_from_db()
                self.assertEqual(surveys[old].redirect_url, expected)
