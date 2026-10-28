"""Tests for the `template-hygiene` capability (openspec/specs/template-hygiene/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import SimpleTestCase
import re


class TemplateCommentSyntaxTest(SimpleTestCase):
    """Django's {# #} comment is single-line; a multi-line one renders as page text."""

    def test_no_multi_line_hash_comments_in_templates(self):
        """
        GIVEN every template shipped with the survey app
        WHEN each `{#` is checked for a closing `#}` on the same line
        THEN none is left open, because Django would render the block as visible text
        """
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent / 'templates'
        offenders = []
        for path in root.rglob('*.html'):
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if '{#' in line and '#}' not in line.split('{#', 1)[1]:
                    offenders.append(f'{path.relative_to(root)}:{number}')

        self.assertEqual(
            offenders, [],
            'Multi-line {# #} comments render as visible text — use '
            '{% comment %}/{% endcomment %} instead: ' + ', '.join(offenders),
        )

    def test_every_template_parses(self):
        """
        GIVEN every template shipped with the survey app
        WHEN Django is asked to load each one
        THEN none raises a syntax error, because a template that cannot parse
             takes down every view that includes it — an automated i18n pass
             once left 60 template tags mangled here and 40 tests failed on one
             unparseable partial
        """
        import pathlib

        from django.template.loader import get_template
        from django.template import TemplateSyntaxError

        root = pathlib.Path(__file__).resolve().parent.parent / 'templates'
        offenders = []
        for path in sorted(root.rglob('*.html')):
            try:
                get_template(str(path.relative_to(root)))
            except TemplateSyntaxError as exc:
                offenders.append(f'{path.relative_to(root)}: {exc}')

        self.assertEqual(offenders, [], 'Templates that will not parse:\n  '
                         + '\n  '.join(offenders))

    #: Bare form strings that are format examples or CSS, not prose. Kept as an
    #: explicit list rather than a heuristic: 'fas fa-map-marker-alt' contains
    #: spaces, so "has a space therefore prose" would misfire on it.
    UNTRANSLATED_FORM_LITERALS = {'survey_name', 'https://', 'fas fa-map-marker-alt'}

    def test_creator_facing_form_strings_are_translatable(self):
        """
        GIVEN the form modules
        WHEN every label, help_text and placeholder is inspected
        THEN each is wrapped for translation, because these reach the creator
             but live in Python — the template sweep never touched them, and a
             German creator saw an English placeholder on the create page until
             it was reported from a phone
        """
        import ast
        import pathlib

        keys = {'placeholder', 'label', 'help_text', 'labels', 'help_texts'}
        offenders = []
        app = pathlib.Path(__file__).resolve().parent.parent
        for module in ('editor_forms.py', 'forms.py'):
            tree = ast.parse((app / module).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                found = []
                # label='...' / placeholder='...' passed as a keyword
                if (isinstance(node, ast.keyword) and node.arg in keys
                        and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, str)):
                    found.append((node.value.lineno, node.arg, node.value.value))
                # {'placeholder': '...'} inside a widget's attrs, or Meta dicts
                if isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if (isinstance(key, ast.Constant) and key.value in keys
                                and isinstance(value, ast.Constant)
                                and isinstance(value.value, str)):
                            found.append((value.lineno, key.value, value.value))
                for line, key, value in found:
                    if value in self.UNTRANSLATED_FORM_LITERALS or not value.strip():
                        continue
                    offenders.append(f'{module}:{line} {key}={value[:50]!r}')

        self.assertEqual(
            offenders, [],
            'Creator-facing form string is not wrapped for translation. Use '
            'gettext_lazy as _, or add it to UNTRANSLATED_FORM_LITERALS if it '
            'is a format example rather than prose:\n  ' + '\n  '.join(offenders),
        )

    def test_no_form_meta_assigns_the_same_key_twice(self):
        """
        GIVEN the form modules
        WHEN each ModelForm's Meta is scanned for repeated assignments
        THEN none assigns the same name twice, because the later one silently
             discards the earlier — SurveySectionForm.Meta had two `labels`
             dicts, so three of its five fields had no label at all and reached
             the creator in English whatever their interface language
        """
        import ast
        import collections
        import pathlib

        offenders = []
        app = pathlib.Path(__file__).resolve().parent.parent
        for module in ('editor_forms.py', 'forms.py'):
            tree = ast.parse((app / module).read_text(encoding='utf-8'))
            for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
                for meta in (n for n in cls.body
                             if isinstance(n, ast.ClassDef) and n.name == 'Meta'):
                    names = [t.id for stmt in meta.body if isinstance(stmt, ast.Assign)
                             for t in stmt.targets if isinstance(t, ast.Name)]
                    for key, count in collections.Counter(names).items():
                        if count > 1:
                            offenders.append(f'{module} {cls.name}.Meta: {key} assigned {count}x')

        self.assertEqual(offenders, [], 'Duplicate Meta assignment:\n  '
                         + '\n  '.join(offenders))

    def test_no_translation_tag_is_nested_in_a_blocktrans(self):
        """
        GIVEN every template shipped with the survey app
        WHEN each {% blocktrans %} body is inspected
        THEN it contains no further translation tag, because Django rejects
             that outright ("Translation blocks must not include other block
             tags") and the page 500s rather than degrading
        """
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent / 'templates'
        offenders = []
        for path in root.rglob('*.html'):
            text = path.read_text(encoding='utf-8')
            for match in re.finditer(
                    r'\{%\s*blocktrans.*?\{%\s*endblocktrans\s*%\}', text, re.S):
                body = match.group(0)[12:]
                if re.search(r'\{%\s*(?:trans|blocktrans)\b', body):
                    line = text[:match.start()].count('\n') + 1
                    offenders.append(f'{path.relative_to(root)}:{line}')

        self.assertEqual(offenders, [], 'Nested translation tag: '
                         + ', '.join(offenders))

    def test_no_msgid_carries_html_entities(self):
        """
        GIVEN every translatable string in the templates
        WHEN its msgid is inspected
        THEN it holds no HTML entity, because the msgid is what a translator
             reads — `Questions &amp; Responses` invites a dropped semicolon,
             and a bare `&` before a space is valid HTML5 anyway
        """
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent / 'templates'
        offenders = []
        for path in root.rglob('*.html'):
            text = path.read_text(encoding='utf-8')
            for match in re.finditer(
                    r'\{%\s*trans\s+"([^"]*(?:&[a-zA-Z]+;|&#\d+;)[^"]*)"', text):
                line = text[:match.start()].count('\n') + 1
                offenders.append(f'{path.relative_to(root)}:{line} {match.group(1)[:40]}')

        self.assertEqual(offenders, [], 'HTML entity inside a msgid:\n  '
                         + '\n  '.join(offenders))

    def test_no_translation_tag_contains_a_newline(self):
        """
        GIVEN every template shipped with the survey app
        WHEN each {% trans %} / {% blocktrans %} opening tag is checked
        THEN none contains a newline, because Django does not parse such a tag
             and prints it to the page verbatim -- creators saw the literal
             `{% trans "Write this in whatever language…" %}` on the create page
        """
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent / 'templates'
        offenders = []
        for path in root.rglob('*.html'):
            text = path.read_text(encoding='utf-8')
            for match in re.finditer(
                    r'\{%\s*(?:trans|blocktrans)\b[^%]*?\n[^%]*?%\}', text):
                line = text[:match.start()].count('\n') + 1
                offenders.append(f'{path.relative_to(root)}:{line}')

        self.assertEqual(
            offenders, [],
            'A translation tag spanning several lines renders as visible text '
            'rather than being translated — keep the tag on one line: '
            + ', '.join(offenders),
        )

    def test_comment_text_does_not_reach_a_rendered_page(self):
        """
        GIVEN partials whose comments used to render as page text
        WHEN they are rendered with an empty context
        THEN no wording from their comments appears in the output
        """
        from django.template.loader import render_to_string

        faq = render_to_string('partials/_faq_section.html', {})
        jsonld = render_to_string('partials/_landing_structured_data.html', {})

        self.assertNotIn('seo_landings registry', faq)
        self.assertNotIn('Visible FAQ section', faq)
        self.assertNotIn('pre-serialized', jsonld)
        self.assertNotIn('Per-page structured data', jsonld)
