"""Tests for the `creator-loading-feedback` capability (openspec/specs/creator-loading-feedback/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import SimpleTestCase


# ---------------------------------------------------------------------------
# Export formats (spec responses-export-formats)
# ---------------------------------------------------------------------------

class LoadingFeedbackTest(SimpleTestCase):
    """Loading feedback on creator pages (change creator-loading-feedback, #337):
    one partial with the top progress bar and the busy state of submit buttons,
    included by the two creator bases and by nothing a respondent sees. These
    canaries read the template and static sources; the behaviour itself is
    verified in a browser (tasks 4.x of the change)."""

    PARTIAL = 'partials/_loading_feedback.html'
    SCRIPT = 'js/loading_feedback.js'
    STYLE = 'css/loading-feedback.css'

    @staticmethod
    def _app_root():
        import pathlib

        return pathlib.Path(__file__).resolve().parent.parent

    def _template(self, name):
        return (self._app_root() / 'templates' / name).read_text()

    def _asset(self, name):
        return (self._app_root() / 'assets' / name).read_text()

    def test_creator_bases_include_the_partial_once(self):
        """
        GIVEN the two creator base templates
        WHEN their source is inspected
        THEN each includes partials/_loading_feedback.html exactly once, so every
             dashboard, account, organisation and editor page gets the bar
        """
        for base in ('base.html', 'editor/editor_base.html'):
            with self.subTest(base=base):
                self.assertEqual(self._template(base).count(self.PARTIAL), 1)

    def test_respondent_and_marketing_bases_do_not(self):
        """
        GIVEN the respondent base and the marketing base
        WHEN their source is inspected
        THEN neither includes the partial nor the script: respondent pages are out
             of scope (#337) and must not grow a creator-facing bar by accident
        """
        for base in ('base_survey_template.html', 'base_landing.html'):
            with self.subTest(base=base):
                source = self._template(base)
                self.assertNotIn(self.PARTIAL, source)
                self.assertNotIn(self.SCRIPT, source)

    def test_partial_loads_the_stylesheet_and_the_script(self):
        """
        GIVEN the partial
        WHEN rendered
        THEN it references the stylesheet and the script, both of which exist
        """
        source = self._template(self.PARTIAL)
        self.assertIn(self.STYLE, source)
        self.assertIn(self.SCRIPT, source)
        self.assertTrue((self._app_root() / 'assets' / self.STYLE).is_file())
        self.assertTrue((self._app_root() / 'assets' / self.SCRIPT).is_file())

    def test_script_contract(self):
        """
        GIVEN the loading feedback script
        WHEN its source is inspected
        THEN it pairs htmx:beforeSend with htmx:afterRequest (beforeRequest can be
             cancelled and then afterRequest never fires), resets on pageshow for the
             back/forward cache, skips polling triggers, honours data-no-progress,
             and disables a busy button on the next tick only — so a native
             submitter's name/value still reach the server and jQuery's delegated
             click (Bootstrap data-toggle) still sees the button — and gives HTMX
             GET buttons the bar but no busy state
        """
        source = self._asset(self.SCRIPT)
        self.assertIn("'htmx:beforeSend'", source)
        self.assertIn("'htmx:afterRequest'", source)
        self.assertNotIn("'htmx:beforeRequest'", source)
        self.assertIn("'pageshow'", source)
        self.assertIn('e.persisted', source)
        self.assertIn(r'/\bevery\b/', source)
        self.assertIn('[data-no-progress]', source)
        self.assertIn('if (!rec.released) btn.disabled = true;', source)
        self.assertEqual(source.count('btn.disabled = true'), 1)
        self.assertIn("if (verb !== 'get') btn = elt;", source)
        self.assertIn('window.LoadingFeedback', source)

    def test_rendered_editor_page_carries_the_assets(self):
        """
        GIVEN the editor base rendered through the template engine
        WHEN the HTML is produced
        THEN it links the stylesheet and the script by their static paths
        """
        from django.template.loader import render_to_string

        html = render_to_string('partials/_loading_feedback.html', {'debug': False})
        self.assertIn('loading-feedback', html)
        self.assertIn('loading_feedback', html)
