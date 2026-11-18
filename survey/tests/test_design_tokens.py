"""Spec: design-tokens — one file of design tokens for the creator app, and a ratchet on colours
written outside it."""
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

REPO = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name('colour_baseline.json')

CREATOR_CSS = (
    'app_sidebar', 'comments', 'editor-mobile', 'loading-feedback', 'map_style_editor', 'paper_inbox',
    'paper_review', 'plan_cards', 'pro_badge', 'pro_trial', 'report_builder', 'responses-v2',
    'site_builder', 'translation_table', 'whats-new',
)
CREATOR_TEMPLATE_ROOTS = (
    'survey/templates/base.html', 'survey/templates/editor.html', 'survey/templates/editor',
    'survey/templates/org', 'survey/templates/comments', 'survey/templates/sites',
    'reports/templates', 'data/templates', 'billing/templates', 'api/templates',
)
COLOUR_RE = re.compile(r'#[0-9a-fA-F]{6}\b|\brgba?\(')

# Every creator file is on the tokens (change tokens-editor-shell): no colour in a CSS declaration
# outside a <script> block. Colours inside scripts are data (map palettes, colour inputs, an iframe's
# srcdoc). These files render where css/tokens.css is NOT loaded, so they keep their own colours.
WITHOUT_TOKENS = {
    'survey/templates/org/invitation_email.html': 'an email: mail clients load no stylesheet of ours',
    'survey/templates/comments/notify.html': 'an email: mail clients load no stylesheet of ours',
    'survey/templates/editor/partials/group_preview_frame.html': 'an iframe with the respondent stylesheet',
    'survey/templates/sites/public.html': 'the public site page /p/<slug>/',
    'survey/assets/css/plan_cards.css': (
        'also drawn on the marketing pricing page: the app token first, the landing name and a '
        'literal as fallbacks'),
}
SCRIPT_RE = re.compile(r'<script\b.*?</script>', re.S | re.I)
DECLARED_COLOUR_RE = re.compile(r'[a-z-]+\s*:\s*[^;{}"\'<>]*?(#[0-9a-fA-F]{6}\b|\brgba?\()')


def declared_colours(text):
    """Colours written in CSS declarations of a template or stylesheet, scripts left out."""
    return [m.group(1) for m in DECLARED_COLOUR_RE.finditer(SCRIPT_RE.sub('', text))]


def creator_files():
    for name in CREATOR_CSS:
        yield REPO / 'survey/assets/css' / f'{name}.css'
    for root in CREATOR_TEMPLATE_ROOTS:
        path = REPO / root
        if path.is_file():
            yield path
        else:
            yield from sorted(path.rglob('*.html'))


def colour_counts():
    """{repo-relative path: number of colour literals} for creator styles and templates."""
    counts = {}
    for path in creator_files():
        found = len(COLOUR_RE.findall(path.read_text(encoding='utf-8')))
        if found:
            counts[str(path.relative_to(REPO))] = found
    return counts


class ColourRatchetTest(SimpleTestCase):
    def test_no_file_gains_colour_literals(self):
        """
        GIVEN the recorded number of colour literals in every creator stylesheet and template
        WHEN the files are counted again
        THEN no file holds more than recorded and a new file holds none: a new colour is a token
        """
        allowed = json.loads(BASELINE.read_text())
        over = {path: (found, allowed.get(path, 0))
                for path, found in colour_counts().items() if found > allowed.get(path, 0)}
        self.assertEqual(over, {}, (
            'Colour literals were added outside css/tokens.css (found, allowed). Use a token; '
            'after REMOVING literals, lower the numbers with scripts/colour_baseline.py.'))

    def test_baseline_names_only_existing_files(self):
        """
        GIVEN the baseline
        WHEN a file it names is gone
        THEN the test fails, so the list only shrinks with the code
        """
        allowed = json.loads(BASELINE.read_text())
        self.assertEqual([p for p in allowed if not (REPO / p).is_file()], [])


class TokenisedModulesTest(SimpleTestCase):
    def test_creator_files_hold_no_colour_literals(self):
        """
        GIVEN every creator stylesheet and template that renders under css/tokens.css
        WHEN their CSS declarations are read, scripts left out
        THEN none writes a colour of its own
        """
        found = {}
        for path in creator_files():
            rel = str(path.relative_to(REPO))
            if rel not in WITHOUT_TOKENS and (colours := declared_colours(path.read_text(encoding='utf-8'))):
                found[rel] = colours
        self.assertEqual(found, {}, (
            'A creator file writes a colour of its own. Use a token from css/tokens.css '
            '(scripts/tokenise_colours.py maps colours to tokens).'))

    def test_exceptions_name_existing_files(self):
        """
        GIVEN the files that render without the tokens
        WHEN one of them is gone
        THEN the test fails, so the list only shrinks with the code
        """
        self.assertEqual([p for p in WITHOUT_TOKENS if not (REPO / p).is_file()], [])

    def test_a_returned_literal_is_caught_but_script_data_is_not(self):
        """
        GIVEN a style rule with a grey and a script handing a colour to Leaflet
        WHEN the colours are read
        THEN the grey counts and the script's colour does not
        """
        text = ('<style>.x { color: #6b7280; border: 1px solid var(--color-border); }</style>'
                '<div style="background:#f3f4f6"></div>'
                "<script>L.polyline(p, {color: '#0d6efd'}); el.style.cssText = 'color:#fff';</script>")
        self.assertEqual(declared_colours(text), ['#6b7280', '#f3f4f6'])


class TokensWiringTest(SimpleTestCase):
    def read(self, path):
        return (REPO / path).read_text(encoding='utf-8')

    def test_both_creator_bases_load_the_tokens_after_bootstrap(self):
        """
        GIVEN the two base templates of the creator app
        WHEN their head is read
        THEN each links css/tokens.css after Bootstrap, so the tokens' button and modal rules win
        """
        for base in ('survey/templates/base.html', 'survey/templates/editor/editor_base.html'):
            html = self.read(base)
            self.assertIn("css/tokens.css", html, base)
            self.assertLess(html.index('bootstrap.min.css'), html.index('css/tokens.css'), base)

    def test_respondent_and_marketing_bases_do_not_load_them(self):
        """
        GIVEN the respondent page base and the marketing base
        WHEN their source is read
        THEN neither links css/tokens.css: the creator app's look stays in the creator app
        """
        for base in ('survey/templates/base_survey_template.html', 'survey/templates/base_landing.html'):
            self.assertNotIn('css/tokens.css', self.read(base), base)

    def test_older_variables_refer_to_the_tokens(self):
        """
        GIVEN the editor's and the builder's own variable names
        WHEN their definitions are read
        THEN the accent of both is the action token, not a colour of its own
        """
        self.assertIn('--accent: var(--color-action)', self.read('survey/assets/css/tokens.css'))
        self.assertIn('--accent:var(--color-action)', self.read('survey/assets/css/site_builder.css'))

    def test_the_action_colour_is_indigo(self):
        """
        GIVEN the tokens file
        WHEN the action colour is read
        THEN it is the indigo of the palette (owner decision 2026-11-18)
        """
        css = self.read('survey/assets/css/tokens.css')
        self.assertIn('--color-action: var(--indigo-600)', css)
        self.assertIn('--indigo-600: #4f46e5', css)
